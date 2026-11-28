"""Behind the build lines of `aerie status` on a node (bb_stamps in aerie):
which image the controller is on, asked over /api/meta, said softly, and
the node's agent. A session is always on a node, where BB_IMAGE_REV and
BB_VERSION are empty, and the which-build rule sends it to aerie status to
learn the build, so this has to work there. A controller that is down, or a
session with no token, is a state the line reports rather than dies on.

BB_NODE_ID is the node. The auth header is bbapi's own (BB_AUTH_HEADER, from
api_py in aerie). Two lines, the second the agent's or empty, the last with
no newline.
"""
import os
import urllib.parse

import bbapi


# request rather than call, because the two failures want different
# answers and call cannot tell them apart: a refusal the server worded and a
# refused connection both come back as {"error": sentence}. Reporting an
# expired token as "the controller is down" is the mistake bb-gate already
# made once, and the first version of this line made it again.
# Short timeout: aerie status is run often, and a controller that is down should
# cost a line rather than a 30-second wait.
# One ask for both lines: the controller's build, then, on a
# line of its own, this node's agent with when it was built, or
# nothing after the newline when it cannot be had. aerie status ran this
# twice, two pythons and two requests.
NODE = os.environ.get("BB_NODE_ID", "")
try:
    st, m = bbapi.request("/api/meta" + (f"?node={urllib.parse.quote(NODE)}" if NODE else ""),
                          timeout=5)
except Exception:
    st, m = None, {}


def controller_line():
    if st is None:
        return "unreachable: the controller did not answer"
    if st >= 400 or not isinstance(m, dict) or m.get("error"):
        why = (m or {}).get("error") or f"HTTP {st}"
        return f"the controller refused this session: {why}"
    ver = (m.get("version") or "").strip()
    rev = (m.get("image") or "").strip()
    built = (m.get("built") or "").strip()
    if not ver and not rev:
        return "unstamped: the controller's image was built outside CI"
    out = ver or rev[:7]
    if rev and rev[:7] not in out:
        out += f" ({rev[:7]})"
    if built:
        out += f" (built {built})"
    return out


def agent_line():
    ag = (m or {}).get("agent") if isinstance(m, dict) and NODE else None
    if isinstance(ag, dict) and ag.get("version"):
        return ag["version"] + (f" (built {ag['built'][:10]})" if ag.get("built") else "")
    return ""


print(controller_line() + "\n" + agent_line(), end="")
