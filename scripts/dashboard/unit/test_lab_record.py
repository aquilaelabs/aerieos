"""The lab writes its own record, and a system's vetted line is read from
it (R3 step 8; the audit of 13 Nov: the dates beside the systems were typed
by hand, 13 to 22 Oct, and the provisioner changed in 16 commits since).

A lab suite prints one line for each subject it walked with nothing failed;
`aerie tests lab` hands the run's output to labrecord.py, which keeps each
dated with the build it ran against. systems.py reads a walked system's
line from the newest walk whose machine said it was that system, and a
system with no walk on record is not vetted."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import forges  # noqa: E402
import labrecord  # noqa: E402
import systems  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RUN = """PASS  [debian-13] a VM made a node (lab-debian-13)
PASS  [debian-13] Uninstall takes it off the Nodes page
RECORD  suite=lab-systems subject=debian-13 said=linux x86_64 Debian GNU/Linux 13 (trixie)
FAIL  [fedora-44] a toolchain installs (no node item)
[12:01:07] RECORD  suite=lab-forge subject=gitea said=Gitea   1.24.7
RECORD  suite=Not-A-Suite subject=x said=y
"""


class Record(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.path = os.path.join(self.d, "lab-record.json")

    def test_a_runs_lines_are_read_wherever_the_harness_put_them(self):
        self.assertEqual(labrecord.parse(RUN), [("lab-systems", "debian-13", "linux x86_64 Debian GNU/Linux 13 (trixie)"),
                                                ("lab-forge", "gitea", "Gitea 1.24.7")])
        self.assertEqual(labrecord.parse("PASS  everything\n3 passed, 0 failed\n"), [])

    def test_each_is_kept_dated_with_its_build_and_the_newest_first(self):
        labrecord.add(labrecord.parse(RUN), "0.9.0-dev.5300+abc1234", "2026-11-01", self.path)
        new = labrecord.add([("lab-systems", "debian-13", "linux x86_64 Debian GNU/Linux 13 (trixie)")],
                            "0.9.0-dev.5400+def5678", "2026-11-14", self.path)
        self.assertEqual([r["at"] for r in new], ["2026-11-14"])
        got = labrecord.rows(self.path)
        self.assertEqual([(r["suite"], r["subject"], r["at"], r["build"]) for r in got],
                         [("lab-systems", "debian-13", "2026-11-14", "0.9.0-dev.5400+def5678"),
                          ("lab-forge", "gitea", "2026-11-01", "0.9.0-dev.5300+abc1234"),
                          ("lab-systems", "debian-13", "2026-11-01", "0.9.0-dev.5300+abc1234")])
        self.assertEqual(labrecord.newest(lambda r: r["subject"] == "debian-13", self.path)["at"], "2026-11-14")
        # The same walk said twice in a day is one line, and only the newest few of each stay.
        labrecord.add([("lab-systems", "debian-13", "again")], "0.9.0-dev.5400+def5678", "2026-11-14", self.path)
        for day in ("2026-11-15", "2026-11-16", "2026-11-17"):
            labrecord.add([("lab-systems", "debian-13", "x")], "b", day, self.path)
        mine = [r["at"] for r in labrecord.rows(self.path) if r["subject"] == "debian-13"]
        self.assertEqual(mine, ["2026-11-17", "2026-11-16", "2026-11-15"])
        with open(self.path) as f:
            self.assertEqual(json.load(f)["format"], labrecord.FORMAT)

    def test_a_run_that_walked_nothing_whole_writes_nothing(self):
        self.assertEqual(labrecord.add([], "b", "2026-11-14", self.path), [])
        self.assertFalse(os.path.exists(self.path))
        with self.assertRaises(ValueError):
            labrecord.add([("lab-forge", "gitea", "x")], "b", "14 Nov", self.path)

    def test_a_file_this_build_does_not_read_is_no_record(self):
        for body in ("[not json", json.dumps({"format": 99, "walks": [{}]}), json.dumps([1, 2]),
                     json.dumps({"format": 1, "walks": [{"suite": "lab-systems"}, "x"]})):
            with open(self.path, "w") as f:
                f.write(body)
            self.assertEqual(labrecord.rows(self.path), [], body)
        self.assertEqual(labrecord.rows(os.path.join(self.d, "none.json")), [])

    def test_the_verb_writes_it_from_a_runs_output(self):
        out = os.path.join(self.d, "run.log")
        with open(out, "w") as f:
            f.write(RUN)
        r = subprocess.run([sys.executable, os.path.join(HERE, "..", "labrecord.py"), "add", "--from", out, "--build", "0.9.0-dev.1+aaaaaaa",
                            "--at", "2026-11-14", "--file", self.path], capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("2 walk(s) written", r.stdout)
        self.assertIn("commit it with the work", r.stdout)
        self.assertEqual(len(labrecord.rows(self.path)), 2)


class Vetted(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.path = os.path.join(self.d, "lab-record.json")
        self.addCleanup(systems.vet)
        self.addCleanup(setattr, forges, "unvetted_ok", forges.unvetted_ok)

    def test_a_walked_systems_line_is_dated_by_the_newest_walk_of_it(self):
        labrecord.add([("lab-systems", "debian-12", "linux x86_64 Debian GNU/Linux 12 (bookworm)")], "", "2026-10-21", self.path)
        labrecord.add([("lab-systems", "debian-13", "linux x86_64 Debian GNU/Linux 13 (trixie)"),
                       ("lab-systems", "fedora-44", "linux x86_64 Fedora Linux 44")], "0.9.0-dev.5400+def5678", "2026-11-14", self.path)
        systems.vet(self.path)
        deb = systems.get("debian")["vetted"]
        self.assertTrue(deb.startswith("2026-11-14, lab-systems at build 0.9.0-dev.5400+def5678: a VM made a node"), deb)
        self.assertTrue(deb.endswith("(linux x86_64 Debian GNU/Linux 13 (trixie))"), deb)
        self.assertIn("2026-11-14", systems.get("fedora")["vetted"])
        # A suite that only asks a node a question does not vet its system.
        labrecord.add([("lab-node", "a-rocky-node", "linux x86_64 Rocky Linux 9.8")], "b", "2026-11-14", self.path)
        systems.vet(self.path)
        self.assertEqual(systems.get("rocky")["vetted"], "")
        # A system in daily use is vetted by that, with no date to go stale.
        self.assertIn("in daily use", systems.get("ubuntu")["vetted"])

    def test_one_with_no_walk_on_record_is_not_vetted_and_says_so(self):
        labrecord.add([("lab-systems", "debian-13", "Debian 13")], "b", "2026-11-14", self.path)
        systems.vet(self.path)
        self.assertEqual(systems.get("alpine")["vetted"], "")
        forges.unvetted_ok = lambda: False
        self.assertEqual({s["id"] for s in systems.offered()}, {"ubuntu", "debian"})
        forges.unvetted_ok = lambda: True
        got = {s["id"]: s for s in systems.offered()}
        self.assertIn("the lab's record holds no walk of it", got["alpine"]["why"])
        self.assertIn("subscription", got["rhel"]["why"], "one that cannot be walked keeps its own reason")
        # ...and walked again, it is vetted again and the reason goes.
        labrecord.add([("lab-systems", "alpine-3", "linux x86_64 Alpine Linux v3.24")], "b", "2026-11-15", self.path)
        systems.vet(self.path)
        self.assertIn("2026-11-15", systems.get("alpine")["vetted"])
        self.assertNotIn("why", systems.get("alpine"))

    def test_the_shipped_record_vets_what_was_walked_and_no_date_is_typed_beside_a_system(self):
        systems.vet()
        vetted = {s["id"] for s in systems.SYSTEMS if s["vetted"]}
        self.assertEqual(vetted, {"ubuntu", "rocky", "debian", "almalinux", "centos", "fedora", "arch", "opensuse", "alpine"})
        with open(os.path.join(HERE, "..", "systems.py"), encoding="utf-8") as f:
            src = f.read()
        import re
        self.assertIsNone(re.search(r"20\d\d-\d\d-\d\d", src), "a date typed beside a system is what the record replaced")
        for r in labrecord.rows():
            self.assertRegex(r["at"], r"^\d{4}-\d{2}-\d{2}$")


class TheRun(unittest.TestCase):
    def test_every_lab_suite_says_what_it_walked_and_the_verb_keeps_it(self):
        tdir = os.path.join(ROOT, "scripts", "dashboard", "test")
        for f in sorted(os.listdir(tdir)):
            if f.startswith("lab-") and f.endswith(".mjs"):
                with open(os.path.join(tdir, f), encoding="utf-8") as fh:
                    self.assertIn(f"record('{f[:-4]}', ", fh.read(), f)
        with open(os.path.join(tdir, "lib.mjs"), encoding="utf-8") as fh:
            lib = fh.read()
        self.assertIn("if (fail > since) return false;", lib, "a subject with a failed check leaves no line")
        with open(os.path.join(ROOT, "scripts", "aerie"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('labrecord.py" add --from "$said" --build "$(cmd_version --semver', src)


if __name__ == "__main__":
    unittest.main()
