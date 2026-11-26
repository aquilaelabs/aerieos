"""Your coding agents on Profile (R294 step 6): each agent with a sign-in of
its own on each node the person may sign in on, where it is installed or they
are signed in to it, with the server's own reason a press could not run now;
a hosting-only node, a retired one and one out of the person's scope are
left out."""
import os
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import profiletab  # noqa: E402

AGENTS = [NS(id="claude", name="Claude", provider="Anthropic", login_job="claude-login"),
          NS(id="codex", name="ChatGPT", provider="OpenAI", login_job="codex-login"),
          NS(id="open", name="Any model", provider="", login_job="")]


def node(nid, name, versions, state="online", kind="agent", **config):
    return {"id": nid, "name": name, "kind": kind, "state": state, "config": config, "versions": versions}


NODES = [node("n_a", "alpha", {"claude": "1.2.3", "codex": "0.163.0", "open": "1.0"}),
         node("n_b", "beta", {"claude": "1.2.3"}, state="offline"),
         node("n_h", "hoster", {}, host_only=True),
         node("n_r", "gone", {"claude": "1.2.3"}, state="retired"),
         node("n_x", "elsewhere", {"claude": "1.2.3"}),
         node("ctl", "controller", {}, kind="local")]


class AgentSignins(unittest.TestCase):
    def setUp(self):
        saved = {k: getattr(profiletab, k) for k in ("agent_rows", "node_list", "agent_version", "signed_on", "signin_cannot")}
        self.addCleanup(lambda: [setattr(profiletab, k, v) for k, v in saved.items()])
        profiletab.agent_rows = lambda: AGENTS
        profiletab.node_list = lambda: NODES
        profiletab.agent_version = lambda n, aid: n["versions"].get(aid, "")
        signed = {"claude": {"n_a": {"email": "me@example.com", "plan": "max"}, "n_h": {"email": "me@example.com", "plan": ""}}}
        profiletab.signed_on = lambda uid, aid: signed.get(aid, {}) if uid == "u_1" else {}
        profiletab.signin_cannot = lambda n, aid: "" if n["state"] == "online" else f"{n['name']} is {n['state']}"

    def rows(self, scope=None):
        return [(r["node_name"], r["agent"], r["email"], r["cannot"]) for r in profiletab.agent_signins("u_1", scope)]

    def test_every_agent_with_a_sign_in_on_every_node_it_is_on(self):
        self.assertEqual(self.rows(), [
            ("alpha", "claude", "me@example.com", ""),
            ("alpha", "codex", "", ""),
            ("beta", "claude", "", "beta is offline"),
            ("elsewhere", "claude", "", ""),
            # Hosting-only, yet signed in there before it was: listed, so it can be signed out.
            ("hoster", "claude", "me@example.com", ""),
        ])

    def test_held_to_the_nodes_a_sign_in_may_be_made_on(self):
        self.assertEqual([r[0] for r in self.rows(scope={"n_a", "n_b"})], ["alpha", "alpha", "beta"])
        self.assertEqual(self.rows(scope=set()), [])

    def test_a_registry_that_cannot_be_read_lists_none(self):
        def broken():
            raise OSError("nodes.db")
        profiletab.node_list = broken
        self.assertEqual(profiletab.agent_signins("u_1", None), [])


if __name__ == "__main__":
    unittest.main()
