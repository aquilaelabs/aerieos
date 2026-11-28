"""devapp.edit_rec is the one way to change one container record: the block
is handed the record under the store's lock and the store is written when it
ends cleanly. Without create an instance the store does not have is handed
over as None and nothing is written, so a result that lands after Remove
does not bring the row back; with create it is made. set_field sets
one field through it, or takes it off when the value is empty."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import devapp  # noqa: E402
import statefile  # noqa: E402


class EditRec(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        was = (devapp.FILE, devapp.write_json, devapp._load)
        self.addCleanup(lambda: (setattr(devapp, "FILE", was[0]), setattr(devapp, "write_json", was[1]),
                                 setattr(devapp, "_load", was[2])))
        devapp.FILE, devapp.write_json = self.tmp / "devapps.json", statefile.write_json
        self.keep({"alpha": {"main": {"rev": "abc"}, "empty": {}}})

    def keep(self, d):
        devapp.FILE.write_text(json.dumps(d))

    def kept(self):
        return json.loads(devapp.FILE.read_text())

    def test_a_record_that_is_there_is_handed_over_and_written(self):
        with devapp.edit_rec("alpha", "main") as rec:
            rec["await_env"] = True
        self.assertEqual(self.kept()["alpha"]["main"], {"rev": "abc", "await_env": True})
        with devapp.edit_rec("alpha", "empty") as rec:
            self.assertEqual(rec, {}, "a record with nothing set is still there")
            rec["building_since"] = 5
        self.assertEqual(self.kept()["alpha"]["empty"], {"building_since": 5})

    def test_a_forgotten_instance_is_not_made_again(self):
        before = devapp.FILE.read_bytes()
        for project, instance in (("alpha", "gone"), ("nowhere", "main")):
            with devapp.edit_rec(project, instance) as rec:
                self.assertIsNone(rec)
        self.assertEqual(devapp.FILE.read_bytes(), before, "nothing is written for a record that is not there")
        self.assertFalse(devapp.set_field("alpha", "gone", "await_env", True))
        self.assertEqual(devapp.FILE.read_bytes(), before)
        devapp.FILE.unlink()
        with devapp.edit_rec("alpha", "main") as rec:
            self.assertIsNone(rec)
        self.assertFalse(devapp.FILE.exists())

    def test_create_makes_the_record(self):
        with devapp.edit_rec("alpha", "new", create=True) as rec:
            self.assertEqual(rec, {})
            rec["node"] = "n1"
        with devapp.edit_rec("beta", "main", create=True):
            pass
        self.assertEqual(self.kept(), {"alpha": {"main": {"rev": "abc"}, "empty": {}, "new": {"node": "n1"}}, "beta": {"main": {}}})

    def test_a_fault_in_the_block_writes_nothing_and_lets_the_lock_go(self):
        before = devapp.FILE.read_bytes()
        with self.assertRaises(RuntimeError):
            with devapp.edit_rec("alpha", "main") as rec:
                rec["rev"] = "changed"
                raise RuntimeError("no revision to read")
        self.assertEqual(devapp.FILE.read_bytes(), before)
        self.assertTrue(devapp._lock.acquire(blocking=False))
        devapp._lock.release()

    def test_a_return_from_the_block_still_writes(self):
        def stamp():
            with devapp.edit_rec("alpha", "main") as rec:
                rec["at"] = 9
                return True
        self.assertTrue(stamp())
        self.assertEqual(self.kept()["alpha"]["main"]["at"], 9)

    def test_set_field_sets_and_takes_off(self):
        self.assertTrue(devapp.set_field("alpha", "main", "gpu", "amd"))
        self.assertEqual(self.kept()["alpha"]["main"], {"rev": "abc", "gpu": "amd"})
        self.assertTrue(devapp.set_field("alpha", "main", "gpu", ""))
        self.assertEqual(self.kept()["alpha"]["main"], {"rev": "abc"})
        self.assertTrue(devapp.set_field("alpha", "third", "ref", "", create=True))
        self.assertEqual(self.kept()["alpha"]["third"], {}, "made, with nothing to take off")

    def test_the_load_the_writer_and_the_file_of_the_moment_are_used(self):
        wrote = []
        devapp._load = lambda: {"alpha": {"main": {"from": "a stand-in"}}}
        devapp.write_json = lambda path, d: wrote.append((Path(path).name, d))
        devapp.FILE = self.tmp / "elsewhere.json"
        with devapp.edit_rec("alpha", "main") as rec:
            rec["seen"] = True
        self.assertEqual(wrote, [("elsewhere.json", {"alpha": {"main": {"from": "a stand-in", "seen": True}}})])


if __name__ == "__main__":
    unittest.main()
