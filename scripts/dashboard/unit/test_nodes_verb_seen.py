"""A session asking aerie nodes through the relay reads its space's own
nodes, and every node only from an owner's or an administrator's seat (B727:
it read the whole install's inventory); a person at the controller reads all."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.join(HERE, "..")
LIB = os.path.join(DASH, "..", "lib")
sys.path.insert(0, DASH)
import db  # noqa: E402


class Seen(unittest.TestCase):
    def setUp(self):
        self.st = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.st, True)
        db.configure(state=self.st)
        db.migrate()
        cols = [r["name"] if isinstance(r, dict) else r[1] for r in db._rows("PRAGMA table_info(nodes)")]
        for nid, name in (("n_aaa111", "ours"), ("n_bbb222", "theirs")):
            row = dict.fromkeys(cols, "")
            row.update(id=nid, name=name, kind="agent", state="online", created=1)
            for c in ("services", "labels", "agent", "reported", "routing", "config"):
                if c in row:
                    row[c] = "{}"
            row["capabilities"] = "[]"
            db._exec(f"INSERT INTO nodes ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", tuple(row[c] for c in cols))
        with open(os.path.join(self.st, "claude-prefs.json"), "w") as f:
            json.dump({"projects": {"alpha": {"node": "n_aaa111", "nodes": ["n_aaa111"]}}}, f)
        with open(os.path.join(self.st, "users.json"), "w") as f:
            json.dump({"users": {"boss": {"uid": "u_00000001", "role": "owner"}, "ann": {"uid": "u_00000002", "role": "user"}}}, f)

    def run_it(self, *argv, **env):
        e = {**os.environ, "DASHBOARD_STATE": self.st, "PYTHONPATH": LIB, "BB_PROJECT": "alpha", **env}
        for k in ("BB_RELAYED", "BB_ACCOUNT_UID"):
            if k not in env:
                e.pop(k, None)
        return subprocess.run([sys.executable, os.path.join(LIB, "nodes-verbs.py"), argv[0], os.path.join(DASH, "nodes.py"), *argv[1:]],
                              env=e, capture_output=True, text=True, check=False)

    def test_a_session_reads_its_spaces_nodes(self):
        out = self.run_it("list", BB_RELAYED="1", BB_ACCOUNT_UID="u_00000002").stdout
        self.assertIn("ours", out)
        self.assertNotIn("theirs", out)
        r = self.run_it("show", "theirs", BB_RELAYED="1", BB_ACCOUNT_UID="u_00000002")
        self.assertIn("no node called theirs", r.stderr)

    def test_an_owners_seat_and_the_controller_read_every_node(self):
        for env in ({"BB_RELAYED": "1", "BB_ACCOUNT_UID": "u_00000001"}, {}):
            out = self.run_it("list", **env).stdout
            self.assertIn("ours", out, env)
            self.assertIn("theirs", out, env)


if __name__ == "__main__":
    unittest.main()
