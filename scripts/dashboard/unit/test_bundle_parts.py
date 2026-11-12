"""What a node's sessions run from the bundle (workspace.BUNDLE_PARTS): every
bb-* script beside bb-tty is a hook or a relay a session on a node calls, and
one left out is a hooks file naming a path that is not there (B241: every
Codex hook failed because bb-agent-hook did not ride along)."""
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.join(HERE, "..")


def bundle_parts():
    # Read off the source rather than imported: workspace.py configures
    # itself against /config at import.
    tree = ast.parse(open(os.path.join(DASH, "workspace.py")).read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "BUNDLE_PARTS" for t in node.targets):
            return set(ast.literal_eval(node.value))
    raise AssertionError("workspace.py has no BUNDLE_PARTS")


class BundleParts(unittest.TestCase):
    def test_every_session_script_rides_in_the_bundle(self):
        parts = bundle_parts()
        scripts = sorted(f for f in os.listdir(DASH) if f.startswith("bb-") and os.path.isfile(os.path.join(DASH, f)))
        self.assertIn("bb-agent-hook", scripts)
        missing = [f for f in scripts if f"scripts/dashboard/{f}" not in parts]
        self.assertEqual(missing, [], f"not in the bundle a node runs sessions from: {missing}")

    def test_the_record_documents_ride_too(self):
        # design-verbs.py, wiki-verbs.py and roadmap-verbs.py import
        # records from beside the dashboard (B426).
        self.assertIn("scripts/dashboard/records.py", bundle_parts())

    def test_the_agents_hook_answers_from_the_bundle_s_files_alone(self):
        # A node has the bundle and nothing else of the dashboard: the verbs
        # a session is not asked about come from agents.py, which the hook
        # imports from beside itself, so it rides too. Asked here of a copy
        # holding only what the bundle names.
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        repo = os.path.join(DASH, "..", "..")
        for part in sorted(bundle_parts()):
            if not part.startswith("scripts/"):
                continue
            src, to = os.path.join(repo, part), os.path.join(d, part)
            os.makedirs(os.path.dirname(to), exist_ok=True)
            if os.path.isdir(src):
                shutil.copytree(src, to, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy(src, to)
        hook = os.path.join(d, "scripts", "dashboard", "bb-agent-hook")
        r = subprocess.run([sys.executable, hook, "--allow", "claude"], capture_output=True, text=True, cwd=d, timeout=60, check=False)
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        self.assertIn("Bash(aerie roadmap *)", json.loads(r.stdout)["settings"])
        r = subprocess.run([sys.executable, "-c", "import importlib.machinery, importlib.util, sys\n"
                            "l = importlib.machinery.SourceFileLoader('h', sys.argv[1])\n"
                            "m = importlib.util.module_from_spec(importlib.util.spec_from_loader('h', l)); l.exec_module(m)\n"
                            "print(m.own_verb('aerie roadmap'), m.own_verb('aerie status'))", hook],
                           capture_output=True, text=True, cwd=d, timeout=60, check=False)
        self.assertEqual(r.stdout.split(), ["True", "False"], r.stderr[-400:])


if __name__ == "__main__":
    unittest.main()
