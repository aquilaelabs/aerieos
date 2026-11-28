"""aerie tests last reads a gate that failed on its unit tier as failed.

The run's log was opened after the unit tier and the patch check, and
neither's lines went into it, so a gate red only there read back as every
suite passed. preflight writes their verdict into the log now, in the shape
the verdict reads; its own line conversion is run here on unittest's lines."""
import os
import re
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "..", "lib")
PREFLIGHT = open(os.path.join(LIB, "preflight.sh"), encoding="utf-8").read()


def named(unittest_out):
    sed = re.search(r"sed -n '([^']+)'", PREFLIGHT.split("mapfile -t named", 1)[1]).group(1)
    return subprocess.run(["sed", "-n", sed], input=unittest_out, capture_output=True, text=True, check=True).stdout.split("\n")


class Last(unittest.TestCase):
    def verdict(self, lines):
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
            f.write("\n".join(lines) + "\n")
        try:
            return subprocess.run(["python3", os.path.join(LIB, "tests-verdict.py")], capture_output=True, text=True,
                                  env=dict(os.environ, BB_VERDICT_LOG=f.name), timeout=30, check=False)
        finally:
            os.unlink(f.name)

    def test_a_red_unit_tier_is_read_as_failed_with_its_tests_named(self):
        fails = [x for x in named("FAIL: test_what (test_sig.Signer.test_what)\nERROR: test_b (test_x.X.test_b)\nOK\n") if x]
        self.assertEqual(fails, ["FAIL  test_sig.Signer.test_what", "FAIL  test_x.X.test_b"])
        log = ["[builderbot] preflight over main", "[builderbot] == unit ==", *fails, "0 passed, 2 failed",
               "[builderbot] == home.mjs ==", "PASS  a thing", "47 passed, 0 failed"]
        out = self.verdict(log)
        said = out.stdout + out.stderr
        self.assertIn("unit", said)
        self.assertNotIn("all 2 suites passed", said)
        self.assertIn("test_sig.Signer.test_what", said)

    def test_the_log_is_written_after_it_is_opened(self):
        opened = PREFLIGHT.index('> "$rl" 2>/dev/null || rl=/dev/null')
        self.assertIn('printf \'%s\\n\' "${before_log[@]}" >> "$rl"', PREFLIGHT[opened:opened + 300])


if __name__ == "__main__":
    unittest.main()
