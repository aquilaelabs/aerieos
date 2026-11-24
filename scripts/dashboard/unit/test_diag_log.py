"""The controller's own log as a section of the diagnostics (diag.log): read
whole rather than for its faults, the last lines of one log of one start
or the last of those holding some words, each line redacted as every
section is; asked for by name and never part of the whole report."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import diag  # noqa: E402


class Log(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        (self.d / "dashboard.log").write_text("".join(f"[dashboard] line {i}\n" for i in range(1, 501))
                                               + "[dashboard] n_1 reports claude signed out for u_00000001\n"
                                               + "[dashboard] asked with token=bbs_abcdefghijklmnop\n")
        (self.d / "dashboard.log.2").write_text("[dashboard] two starts back\n")
        (self.d / "builderbot.log").write_text("[builderbot] boot\n")
        p = mock.patch.object(diag, "log_dir", lambda: self.d)
        p.start()
        self.addCleanup(p.stop)

    def test_the_last_lines_of_the_dashboards_own_log_by_default(self):
        got = diag.log()
        self.assertEqual(got["file"], "dashboard.log")
        self.assertEqual(len(got["lines"]), 300)
        self.assertEqual(got["lines"][-3], "[dashboard] line 500")

    def test_a_line_count_is_held_between_one_and_the_most(self):
        self.assertEqual(len(diag.log(lines=2)["lines"]), 2)
        self.assertEqual(len(diag.log(lines=0)["lines"]), 1)
        self.assertEqual(len(diag.log(lines=10 ** 9)["lines"]), 502)

    def test_words_pick_the_lines_holding_them_in_any_case(self):
        got = diag.log(grep="  Signed   OUT ")
        self.assertEqual(got["lines"], ["[dashboard] n_1 reports claude signed out for u_00000001"])
        self.assertEqual(got["grep"], "Signed OUT")

    def test_words_are_a_phrase_never_a_pattern(self):
        self.assertEqual(diag.log(grep="line .*")["lines"], [])

    def test_a_secret_in_a_line_is_redacted(self):
        last = diag.log(lines=1)["lines"][0]
        self.assertNotIn("bbs_abcdefghijklmnop", last)
        self.assertIn("<redacted>", last)

    def test_another_log_and_an_earlier_start(self):
        self.assertEqual(diag.log(stream="builderbot")["lines"], ["[builderbot] boot"])
        self.assertEqual(diag.log(boot=2)["lines"], ["[dashboard] two starts back"])
        self.assertIn("no log is kept from 5 starts back", diag.log(boot=5)["error"])
        self.assertIn("this start has written none", diag.log(stream="docker")["error"])

    def test_a_log_it_does_not_have_is_refused_by_name(self):
        self.assertIn("the logs are dashboard, builderbot, docker", diag.log(stream="../etc/passwd")["error"])
        self.assertEqual(diag.log(**{"lines": "x"}), {"error": "lines and boot are numbers"})

    def test_asked_for_by_name_and_never_in_the_whole_report(self):
        with mock.patch.dict(diag._BUILD, {s: (lambda: {}) for s in diag.SECTIONS}):
            self.assertNotIn("log", diag.report())
            got = diag.report(["log"], log_opts={"lines": 1, "grep": "boot", "stream": "builderbot", "nope": 1})
        self.assertEqual(got["log"]["lines"], ["[builderbot] boot"])
        self.assertIn("log", diag.report(["nope"])["error"])


if __name__ == "__main__":
    unittest.main()
