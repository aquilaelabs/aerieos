"""The doctor says a TLS key probe that failed with nothing said (B1101).

Its stderr was thrown away and its exit ignored, so a traceback in the probe
printed nothing and the doctor said nothing of the key every node pins.
The doctor's own lines are run here with the probe stood in."""
import os
import re
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
AERIE = open(os.path.join(HERE, "..", "..", "aerie"), encoding="utf-8").read()


def snippet():
    m = re.search(r'(?ms)^        local tls_key tls_err tls_rc=0\n.*?^        rm -f "\$tls_err"\n', AERIE)
    assert m
    return m.group(0).replace("        local ", "")


class Said(unittest.TestCase):
    def run_probe(self, body):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "doctor-probes.py"), "w", encoding="utf-8") as f:
                f.write(body)
            script = f'BB_LIB={d}; BB_SCRIPTS={d}; ok=0\n' + snippet() + 'echo "ok=$ok"\n'
            return subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30, check=False).stdout

    def test_a_traceback_is_a_warning(self):
        out = self.run_probe("raise KeyError('DASHBOARD_STATE')\n")
        self.assertIn("[warn] the doctor could not read the state of the TLS key every node pins: KeyError", out)
        self.assertIn("ok=1", out)

    def test_a_probe_that_says_its_line_and_one_with_nothing_to_say(self):
        out = self.run_probe("import sys\nprint('  [bad]  the TLS key cannot be opened')\nsys.exit(1)\n")
        self.assertIn("[bad]  the TLS key cannot be opened", out)
        self.assertNotIn("could not read", out)
        self.assertEqual(self.run_probe("pass\n").strip(), "ok=0")


if __name__ == "__main__":
    unittest.main()
