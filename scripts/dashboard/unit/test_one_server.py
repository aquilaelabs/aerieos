"""One server on a /config at a time: a lock on a file there, held for the
process's life and taken before anything is migrated; a second start waits
for the first to go, then stops with the reason rather than writing beside it."""
import ast
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SERVER = os.path.join(os.path.dirname(__file__), "..", "server.py")


def the_function():
    """_one_server alone, out of server.py: importing the server opens its state."""
    tree = ast.parse(Path(SERVER).read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_one_server")
    return ast.get_source_segment(Path(SERVER).read_text(), fn)


class OneServer(unittest.TestCase):
    def test_a_second_start_waits_then_stops_and_a_freed_one_is_taken(self):
        d = tempfile.mkdtemp()
        ns = {"sys": sys, "time": __import__("time")}
        exec(the_function(), ns)                               # noqa: S102 (this repository's own function)
        held = ns["_one_server"](Path(d), wait=1)
        self.assertIsNotNone(held)
        child = textwrap.dedent(f"""
            import sys, time
            from pathlib import Path
            {textwrap.indent(the_function(), '            ').strip()}
            _one_server(Path({d!r}), wait=1)
            print("took it")
        """)
        r = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(r.returncode, 75, r.stderr)
        self.assertIn("another AerieOS server is running", r.stderr)
        held.close()
        r = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "took it"), r.stderr)


if __name__ == "__main__":
    unittest.main()
