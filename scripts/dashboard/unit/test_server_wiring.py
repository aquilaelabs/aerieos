"""server.py is a program's parts and one function that joins them.

Everything it does to become a running controller (the one-server lock, the
state's gate and migrations, each module handed what it needs, the stores
opened, the threads started) is in wire(), which main() calls first. So
importing the file runs none of it, nothing at its top level has an effect,
and every part a module is handed goes through give(), which refuses a name
the module holds no place for."""
import ast
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.normpath(os.path.join(HERE, ".."))
with open(os.path.join(DASH, "server.py"), encoding="utf-8") as _f:
    SERVER = _f.read()
TREE = ast.parse(SERVER)


def function(name):
    return next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == name)


class Import(unittest.TestCase):
    def test_importing_it_writes_nothing_and_starts_no_thread(self):
        with tempfile.TemporaryDirectory() as d:
            state, ws = os.path.join(d, "state"), os.path.join(d, "ws")
            os.mkdir(state)
            os.mkdir(ws)
            code = ("import json, os, sys, threading\n"
                    "sys.argv = ['server.py']\n"
                    "import server\n"
                    "print(json.dumps({'threads': [t.name for t in threading.enumerate()],\n"
                    "                  'state': sorted(os.listdir(os.environ['DASHBOARD_STATE'])),\n"
                    "                  'ws': sorted(os.listdir(os.environ['WORKSPACE'])),\n"
                    "                  'down': server.NODES_DOWN, 'secret': len(server.SECRET)}))\n")
            env = {**os.environ, "DASHBOARD_STATE": state, "WORKSPACE": ws, "HOME": d, "BUILDER_HOME": d}
            p = subprocess.run([sys.executable, "-c", code], cwd=DASH, env=env, capture_output=True, text=True, timeout=180, check=False)
            self.assertEqual(p.returncode, 0, p.stderr[-2000:])
            got = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertEqual(got["threads"], ["MainThread"])
        self.assertEqual(got["state"], [], "nothing under the state folder")
        self.assertEqual(got["ws"], [], "nothing under the workspace")
        self.assertEqual((got["down"], got["secret"]), ("", 0), "what wire() sets is as it was declared")

    def test_nothing_at_its_top_level_has_an_effect(self):
        # An import, a function, a class, or a name given a value: nothing
        # that calls into a module, writes a file or starts a thread.
        odd = []
        for n in TREE.body:
            if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                continue
            if isinstance(n, (ast.Assign, ast.AnnAssign)):
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                flat = [e for t in targets for e in (t.elts if isinstance(t, (ast.Tuple, ast.List)) else [t])]
                if all(isinstance(t, ast.Name) for t in flat):
                    continue
            if isinstance(n, ast.If) and ast.unparse(n.test) == "__name__ == '__main__'" and ast.unparse(n.body[0]) == "main()":
                continue
            # A table of this file's own, filled where it is written.
            if isinstance(n, ast.Expr) and ast.unparse(n.value).startswith("MAX_BODY_FOR.update("):
                continue
            odd.append(f"line {n.lineno}: {ast.unparse(n)[:70]}")
        self.assertEqual(odd, [], "a statement with an effect belongs in wire()")

    def test_main_wires_before_anything_else_but_the_trace(self):
        first = [ast.unparse(n)[:40] for n in function("main").body[:2]]
        self.assertIn("wire()", first, first)


class Give(unittest.TestCase):
    def give(self):
        ns = {}
        exec(compile(ast.Module([function("give")], []), "server.py", "exec"), ns)  # noqa: S102 (the repository's own source)  # nosemgrep: python.lang.security.audit.exec-detected.exec-detected
        return ns["give"]

    def test_a_part_is_handed_over_by_its_name(self):
        m = types.ModuleType("feature")
        m.audit = None
        m.STATE = None
        self.give()(m, audit=print, STATE="/config")
        self.assertEqual((m.audit, m.STATE), (print, "/config"))

    def test_a_name_the_module_holds_no_place_for_is_refused_and_nothing_is_set(self):
        m = types.ModuleType("feature")
        m.audit = None
        with self.assertRaises(TypeError) as e:
            self.give()(m, audit=print, adit=print)
        self.assertIn("feature takes nothing called adit", str(e.exception))
        self.assertIsNone(m.audit, "all of a call's parts or none")

    def test_wire_hands_every_part_over_through_it(self):
        # No `module.name = value` in wire(): each would be a name nobody
        # checked. What a module is handed is a parameter of its configure()
        # or of give().
        modules = {a.asname or a.name for n in TREE.body if isinstance(n, ast.Import) for a in n.names}
        direct = []
        for n in ast.walk(function("wire")):
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    for e in (t.elts if isinstance(t, (ast.Tuple, ast.List)) else [t]):
                        if isinstance(e, ast.Attribute) and isinstance(e.value, ast.Name) and e.value.id in modules:
                            direct.append(f"line {n.lineno}: {ast.unparse(e)}")
        self.assertEqual(direct, [])

    def test_every_name_wire_gives_is_one_its_module_holds(self):
        # What give() checks at a start, read off the source: a typo fails
        # here, before any controller is started on it.
        alias = {a.asname or a.name: a.name for n in TREE.body if isinstance(n, ast.Import) for a in n.names}
        wrong, seen = [], 0
        for n in ast.walk(function("wire")):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "give" and n.args and isinstance(n.args[0], ast.Name)):
                continue
            mod = alias.get(n.args[0].id)
            path = os.path.join(DASH, f"{mod}.py") if mod else ""
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8") as f:
                held = {x.id for x in ast.walk(ast.parse(f.read())) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store)}
                f.seek(0)
                held |= {x.name for x in ast.parse(f.read()).body if isinstance(x, (ast.FunctionDef, ast.ClassDef))}
            for kw in n.keywords:
                seen += 1
                if kw.arg not in held:
                    wrong.append(f"{mod}.{kw.arg}")
        self.assertEqual(wrong, [])
        self.assertGreater(seen, 150, "the parts were found")


if __name__ == "__main__":
    unittest.main()
