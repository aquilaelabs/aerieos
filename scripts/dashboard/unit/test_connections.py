"""Connected services: every kind's rows as they stand with
what the ledger knows of each (who added it, its last use at most once a
minute, its expiry), the install's first; Forget through the kind, its ledger
row going with it, refused for a kind forgotten only where it lives and for
one not kept; a kind that cannot list is said, not the list's end."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import connections  # noqa: E402


def write_json(p, d, mode=0o644):
    Path(p).write_text(json.dumps(d))


class Connections(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.audits = []
        connections.configure(state=self.d.name, write_json_fn=write_json, audit_fn=lambda *a: self.audits.append(a))
        saved = dict(connections._KINDS)
        self.addCleanup(lambda: (connections._KINDS.clear(), connections._KINDS.update(saved)))
        connections._KINDS.clear()
        self.tokens = {"web": True}
        connections.kind("git", "Space's git token", "space",
                         lambda: [{"ref": p, "name": p, "uses": "push", "sealed": True, "go": ["project", p]} for p in self.tokens],
                         lambda ref, by: self.tokens.pop(ref) and {"ok": True})
        connections.kind("setting", "Controller setting", "install",
                         lambda: [{"ref": "smtp_password", "name": "Mail server password", "sealed": True}])

        def broken():
            raise OSError("unreadable")
        connections.kind("router", "Model router key", "shared", broken)

    def test_rows_with_the_ledger_the_install_s_first(self):
        connections.added("git", "web", by="ada")
        connections.used("git", "web", at=1000)
        connections.used("git", "web", at=1030)       # within the minute: not written
        connections.expires("git", "web", "2026-12-01")
        rows = connections.listing()["rows"]
        self.assertEqual([(r["whose"], r["kind"]) for r in rows], [("install", "setting"), ("space", "git"), ("shared", "router")])
        git = rows[1]
        self.assertEqual((git["by"], git["used"], git["expires"], git["forget"]), ("ada", 1000, "2026-12-01", True))
        self.assertTrue(git["at"])
        self.assertEqual((rows[0]["at"], rows[0]["forget"]), (0, False), "added before the ledger kept any; forgotten only where it lives")
        self.assertIn("could not be listed", rows[2]["error"])

    def test_forget_through_the_kind(self):
        connections.added("git", "web", by="ada")
        r, status = connections.forget("git", "web", "owner")
        self.assertEqual(status, 200)
        self.assertNotIn("web", self.tokens)
        self.assertNotIn("git:web", connections._load(), "its ledger row goes with it")
        self.assertEqual(self.audits[-1][:3], ("owner", "connection-forget", "git:web"))
        self.assertEqual(connections.forget("git", "web", "owner")[1], 404, "no longer kept")
        self.assertEqual(connections.forget("setting", "smtp_password", "owner")[1], 400, "forgotten where it lives")
        self.assertEqual(connections.forget("cluster", "x", "owner")[1], 400)


if __name__ == "__main__":
    unittest.main()
