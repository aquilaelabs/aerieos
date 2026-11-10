"""The image carries AerieOS's release key: the Dockerfile copies config
files one by one, and a key the image lacked was a key no Enroll script
carried (met on the dev pair, 10 Nov)."""
import os
import unittest

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")


class InTheImage(unittest.TestCase):
    def test_the_dockerfile_copies_the_key_where_the_enroll_script_reads_it(self):
        text = open(os.path.join(REPO, "Dockerfile"), encoding="utf-8").read()
        self.assertIn("COPY config/aerieos-release.pub /opt/aerieos/config/aerieos-release.pub", text)


if __name__ == "__main__":
    unittest.main()
