"""The first-run doors (B1165): open for SETUP_WINDOW_S after a start and
only to this dashboard's own page, and a landing's startup hooks set aside
rather than put where a start runs them as root."""
import ast
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import move  # noqa: E402

SERVER = open(os.path.join(HERE, "..", "server.py"), encoding="utf-8").read()


def lifted():
    """_setup_shut and the two values it reads, off server.py."""
    tree = ast.parse(SERVER)
    lines = SERVER.splitlines()
    vals = [n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") in ("SETUP_WINDOW_S", "SETUP_SHUT_SAID")]
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Handler")
    meth = next(f for f in cls.body if isinstance(f, ast.FunctionDef) and f.name == "_setup_shut")
    src = "\n".join(["\n".join(lines[n.lineno - 1:n.end_lineno]) for n in vals] + ["class Lifted:", "\n".join(lines[meth.lineno - 1:meth.end_lineno])])
    ns = {"time": time}
    exec(compile(src, "server.py", "exec"), ns)  # noqa: S102 (the repository's own source)
    return ns


class Window(unittest.TestCase):
    def door(self, started_ago, cross=""):
        ns = lifted()
        ns["STARTED"] = time.time() - started_ago

        class Stand(ns["Lifted"]):
            def _post_cross_site(self):
                return cross
        return Stand()._setup_shut(), ns

    def test_open_for_the_window_after_a_start(self):
        self.assertEqual(self.door(60)[0], "")
        self.assertEqual(self.door(14 * 60)[0], "")

    def test_shut_once_it_has_passed_saying_how_to_open_it(self):
        why, ns = self.door(16 * 60)
        self.assertEqual(why, ns["SETUP_SHUT_SAID"])
        self.assertIn("Restart AerieOS", why)

    def test_another_site_s_page_is_refused_however_soon(self):
        why, _ = self.door(5, cross="a change is asked for from this dashboard's own page, not from another site's")
        self.assertIn("not from another site's", why)


class Hooks(unittest.TestCase):
    def test_a_landing_s_hooks_are_set_aside_not_put_live(self):
        with tempfile.TemporaryDirectory() as d:
            hooks = Path(d) / "startup.d"
            hooks.mkdir()
            (hooks / "x.root.sh").write_text("#!/bin/sh\nid\n")
            self.assertTrue(move.hooks_aside(d))
            self.assertFalse(hooks.exists(), "nothing is left where a start runs it")
            self.assertTrue((Path(d) / "startup.d.carried" / "x.root.sh").is_file(), "kept for a person to read")

    def test_none_is_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(move.hooks_aside(d))


if __name__ == "__main__":
    unittest.main()
