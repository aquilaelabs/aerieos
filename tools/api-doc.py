#!/usr/bin/env python3
"""docs/api.md, written from server.py: every /api/ path in the
route record, its method and how it is matched, the first sentence of
its handler's docstring, and the permissions the handler refuses on. Read
with ast rather than by running the server, so a route that is added and
not described shows up as a row with no words, which aerie lint's check turns
into a failure by holding the page equal to this output. --check compares
and says what differs."""
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import routegates  # noqa: E402
SRC = ROOT / "scripts" / "dashboard" / "server.py"
OUT = ROOT / "docs" / "api.md"


def routes(tree, method):
    """A method's routes in the order they are matched, off the route record
    (ROUTES): each Route's first four fields, and none of the doors, which
    are answered ahead of the routes."""
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "ROUTES" for t in node.targets):
            for el in node.value.elts:
                did, how, path, fn = (ast.literal_eval(e) for e in el.args[:4])
                if did == method and how != "door":
                    yield how, path, fn


def handlers(tree):
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Handler":
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef):
                    out[fn.name] = fn
    return out


def first_sentence(fn):
    doc = ast.get_docstring(fn) or ""
    doc = " ".join(doc.split())
    m = re.match(r"(.{0,220}?[.!?])(\s|$)", doc)
    return m.group(1) if m else doc[:220]


CENTRAL = {"owner": "the owner's alone, held by the dispatcher", "admin": "an administrator's, held by the dispatcher",
           "person": "a person's own sign-in, never a session's token, held by the dispatcher"}


def asked(gate, asks=()):
    """A route's gate as the page says it: what the dispatcher holds, with
    what the handler asks of that person besides, or the names of what the
    handler asks (scripts/lib/routegates.py)."""
    if not gate:
        return ""
    if gate[0] == "handler":
        return ", ".join(f"`{n}`" for n in gate[1:])
    return CENTRAL.get(gate[0], gate[0]) + ("; then " + ", ".join(f"`{n}`" for n in asks) if asks else "")


def render():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    fns = handlers(tree)
    gates, more = {}, {}
    for m, _h, p, _f, g, el in routegates.routes_of(tree):
        gates[(m, p)] = ast.literal_eval(g) if g is not None else None
        more[(m, p)] = next((ast.literal_eval(k.value) for k in el.keywords if k.arg == "asks"), ())
    lines = ["# The dashboard's API", "",
             "Written from `scripts/dashboard/server.py` by `tools/api-doc.py`; `aerie lint` holds this page equal to it.",
             "Every request carries the account's credential (a session's token, or the person's cookie or",
             "basic auth). The last column is the route's gate in the route record: what the dispatcher holds",
             "before the handler runs (and after `then`, what the handler asks of that person besides), or the",
             "names of everything the handler itself asks: a permission (of the",
             "install, or of the space the request names), `space` for a space the account sees, `unlocked` for",
             "one not locked against it, `node:` and `instance:` for a permission asked of one node or one",
             "cluster, `dial:` for a session's ask under the space's Agents may, `own` for the account's own",
             "things, and `seen` or `open` where the handler refuses nobody signed in (`seen`: the answer holds",
             "what the asker may see). A name is everything the handler consults, so a permission read only to",
             "draw a dead button is named too. A `prefix` route takes every path it prefixes, in the order",
             "listed; an `exact` one takes its path alone. The companion app's own contract is",
             "`apps/android/api-surface.json`.", "",
             "| Method | Path | Match | Handler | What it does | Asks |", "|---|---|---|---|---|---|"]
    for method in ("GET", "POST"):
        for how, path, fn in routes(tree, method):
            f = fns.get(fn)
            words = first_sentence(f) if f else "(no handler by that name)"
            lines.append(f"| {method} | `{path}` | {how} | `{fn}` | {words.replace('|', '\\\\|')} | {asked(gates.get((method, path)), more.get((method, path), ()))} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    text = render()
    if "--check" in sys.argv:
        have = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if have == text:
            print(f"  [ok]   docs/api.md is server.py's {text.count(chr(10)) - 17} routes, word for word")
            sys.exit(0)
        print("  [FAIL] docs/api.md differs from server.py's routes: tools/api-doc.py rewrites it")
        sys.exit(1)
    if "--print" in sys.argv:
        sys.stdout.write(text)
    else:
        OUT.write_text(text, encoding="utf-8")
        print(f"docs/api.md: {text.count(chr(10)) - 17} routes")
