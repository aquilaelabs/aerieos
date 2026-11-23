"""A space's lock refuses writes, and its history is read through it (B1036).

The roadmap's and the bugs' handlers let the history and finished reads past
the read-only gate, then the lock's 409 refused a member it held out anyway;
the memory handler asked the lock before anything. The lock is a write
refusal: here the three handlers are lifted out of server.py's source, as
test_project_asked does, and run against stand-ins."""
import ast
import os
import sys
import unittest
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from fields import field  # noqa: E402
import test_project_asked as base  # noqa: E402

SERVER = base.SERVER
LIFTED = base.LIFTED + ("_roadmap", "_bugs", "_memory")


class _Verb:
    def __init__(self):
        self.asked = []

    def verb(self, name, act, *a, **k):
        self.asked.append(act)
        return {"ok": True, "act": act}, 200


class _UsersMore(base._Users):
    @staticmethod
    def tmux_prefix(who):
        return ""


def handler(roadmap, bugs, memory):
    lines = SERVER.splitlines()
    cls = next(n for n in ast.parse(SERVER).body if isinstance(n, ast.ClassDef) and n.name == "Handler")
    body = "\n".join("\n".join(lines[f.lineno - 1:f.end_lineno]) for f in cls.body
                     if isinstance(f, ast.FunctionDef) and f.name in LIFTED)
    ns = {"field": field, "urllib": urllib, "users": _UsersMore, "projects": base._Projects,
          "project_names": lambda who: who["sees"], "roadmap": roadmap, "bugs": bugs, "memory": memory,
          "sessions_anywhere": lambda: [], "home_for": lambda uid: "/tmp"}
    exec("class Lifted:\n" + body, ns)      # noqa: S102 (the repository's own source, read from beside this test)

    class Stand(ns["Lifted"]):
        def __init__(self, who, path="/api/x"):
            self.who, self.path, self.said = who, path, []

        def _who(self):
            return self.who

        def _json(self, obj, code=200):
            self.said.append((code, obj))

        def _refused(self, *a):
            return False

    return Stand


MEMBER = {"uid": "u_member", "sees": ["locked"], "works": ["locked"]}


class LockedReads(unittest.TestCase):
    def setUp(self):
        self.rm, self.bg, self.mem = _Verb(), _Verb(), _Verb()
        self.Stand = handler(self.rm, self.bg, self.mem)

    def ask(self, method, body):
        h = self.Stand(MEMBER)
        getattr(h, method)(body)
        return h.said[-1][0] if h.said else None

    def test_the_history_is_read_through_the_lock_and_a_write_is_refused(self):
        for method in ("_roadmap", "_bugs"):
            for act in ("history", "finished"):
                self.assertEqual(self.ask(method, {"project": "locked", "action": act}), 200, (method, act))
            self.assertIn(self.ask(method, {"project": "locked", "action": "add"}), (403, 409), method)
        self.assertEqual(self.ask("_memory", {"project": "locked", "action": "history"}), 200)
        self.assertIn(self.ask("_memory", {"project": "locked", "action": "save"}), (403, 409))
        self.assertEqual((self.rm.asked, self.bg.asked, self.mem.asked),
                         (["history", "finished"], ["history", "finished"], ["history"]), "no write reached a verb")



class NameIsText(unittest.TestCase):
    """A JSON list as the space's name is a refusal, not a 500 (B1036): four
    handlers read it raw, and the list reached a set lookup."""

    def test_the_handlers_read_the_name_through_field(self):
        lines = SERVER.splitlines()
        cls = next(n for n in ast.parse(SERVER).body if isinstance(n, ast.ClassDef) and n.name == "Handler")
        for f in cls.body:
            if isinstance(f, ast.FunctionDef) and f.name in ("_changelog", "_prefs_post", "_rename", "_project_auth"):
                src = "\n".join(lines[f.lineno - 1:f.end_lineno])
                self.assertNotRegex(src, r'name = req\.get\("(project|name)"', f.name)
                self.assertRegex(src, r'name = field\(req, "(project|name)"\)', f.name)


if __name__ == "__main__":
    unittest.main()
