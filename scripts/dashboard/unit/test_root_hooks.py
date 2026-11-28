"""The root startup hooks an administrator approves: scripts/root-hook
keeps the approvals where only its runner writes, a hook runs (check) only as
it was approved, a change or a folder another account could write makes it
wait again, and roothooks.py reads and changes them through it. Run as this
account, whose files stand in for root's."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import roothooks  # noqa: E402

HELPER = os.path.join(HERE, "..", "..", "root-hook")


class Helper(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.state = Path(self.d.name)
        (self.state / "startup.d").mkdir()
        self.hook = self.state / "startup.d" / "10-mine.root.sh"
        self.hook.write_text("#!/bin/sh\necho hello\n")

    def run_(self, *argv):
        p = subprocess.run(["bash", HELPER, *argv], capture_output=True, text=True,
                           env=dict(os.environ, BB_ROOT_HOOK_STATE=str(self.state)), check=False)
        return p.returncode, p.stdout.strip(), p.stderr.strip()

    def listed(self):
        return {ln.split()[0]: ln.split()[1:] for ln in self.run_("list")[1].splitlines()}

    def test_a_new_hook_waits_until_approved_as_it_is(self):
        name = self.hook.name
        sha = self.listed()[name][0]
        self.assertEqual(self.listed()[name][1], "new")
        self.assertNotEqual(self.run_("check", name)[0], 0, "not approved: the start skips it")
        rc, _, err = self.run_("approve", name, "0" * 64)
        self.assertNotEqual(rc, 0)
        self.assertIn("changed since it was shown", err)
        self.assertEqual(self.run_("approve", name, sha)[0], 0)
        self.assertEqual(self.listed()[name][1], "approved")
        self.assertEqual(self.run_("check", name)[0], 0, "approved as it is: the start runs it")
        self.hook.write_text("#!/bin/sh\necho changed\n")
        self.assertEqual(self.listed()[name][1], "changed")
        self.assertNotEqual(self.run_("check", name)[0], 0, "changed since: it waits again")
        self.assertEqual(self.run_("revoke", name)[0], 0)
        self.assertEqual(self.listed()[name][1], "new")

    def test_an_approvals_folder_another_account_could_write_is_not_trusted(self):
        name = self.hook.name
        self.run_("approve", name, self.listed()[name][0])
        os.chmod(self.state / ".root", 0o777)
        self.assertNotEqual(self.run_("check", name)[0], 0, "a folder others write is nobody's word")
        self.assertEqual(self.listed()[name][1], "new")
        # Approving again sets the untrusted folder aside and makes its own.
        self.assertEqual(self.run_("approve", name, self.listed()[name][0])[0], 0)
        self.assertEqual(self.run_("check", name)[0], 0)
        self.assertTrue(any(p.name.startswith(".root.untrusted-") for p in self.state.iterdir()))

    def test_a_link_and_a_bad_name_never_run(self):
        link = self.state / "startup.d" / "20-link.root.sh"
        link.symlink_to(self.hook)
        self.assertNotIn(link.name, self.listed())
        self.assertNotEqual(self.run_("check", link.name)[0], 0)
        self.assertNotEqual(self.run_("approve", "../x.root.sh", "0" * 64)[0], 0)


class Module(unittest.TestCase):
    def test_listing_and_acting_through_the_helper(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "startup.d").mkdir()
            (Path(d) / "startup.d" / "a.root.sh").write_text("#!/bin/sh\nid\n")
            roothooks.configure(state=d)
            got = roothooks.listing()["hooks"]
            self.assertEqual([(h["name"], h["state"]) for h in got], [("a.root.sh", "new")])
            self.assertIn("id", got[0]["text"])
            r, status = roothooks.act({"action": "approve", "name": "a.root.sh", "sha": got[0]["sha"]})
            self.assertEqual(status, 200)
            self.assertEqual(r["hooks"][0]["state"], "approved")
            r, status = roothooks.act({"action": "approve", "name": "a.root.sh", "sha": "f" * 64})
            self.assertEqual(status, 409)
            self.assertEqual(roothooks.act({"action": "wipe", "name": "a.root.sh"})[1], 400)


if __name__ == "__main__":
    unittest.main()
