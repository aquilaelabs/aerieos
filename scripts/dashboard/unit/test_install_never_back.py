"""A bare-metal controller's update never moves back to an older release
(B1170; the operator, 28 Oct: no roll back): the installer's own version
order, X.Y.Z then a dev build before the release it leads to."""
import os
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INSTALLER = os.path.join(HERE, "..", "..", "..", "nodes", "install-controller.sh")


def key(v):
    src = open(INSTALLER).read()
    i = src.index("ver_key() {")
    fn = src[i:src.index("\n}\n", i) + 3]
    return subprocess.run(["bash", "-c", fn + 'ver_key "$1"', "_", v], capture_output=True, text=True, check=True).stdout


class Order(unittest.TestCase):
    def test_versions_sort_as_releases_do(self):
        order = ["0.8.2", "0.9.0-dev.6054", "0.9.0-dev.6168", "0.9.0-dev.6312", "0.9.0", "v0.9.1-dev.1", "0.10.0"]
        self.assertEqual(sorted(order, key=key), order)

    def test_the_update_refuses_an_older_one(self):
        src = open(INSTALLER).read()
        self.assertIn('[[ "$(ver_key "$ver")" < "$(ver_key "$cur")" ]]', src)
        self.assertIn("an update never moves back to an older release", src)


if __name__ == "__main__":
    unittest.main()
