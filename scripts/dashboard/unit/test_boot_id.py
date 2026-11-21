"""The id for a run of the machine: the same from the controller, the agent and
bb-tty, digits alone, and untouched by the clock, whose steps reloaded every
page open on a machine at its first time sync."""
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "agent"))

import layout  # noqa: E402
from aerieos_agent import census  # noqa: E402


def bbtty(fn):
    """A function of bb-tty's own, run alone."""
    src = (HERE / "bb-tty").read_text()
    body = re.search(rf"^{fn}\(\) \{{\n.*?^\}}\n", src, re.S | re.M).group(0)
    return subprocess.run(["bash", "-c", f"{body}\n{fn}"], capture_output=True, text=True, check=True).stdout


def old_shape():
    start = Path("/proc/1/stat").read_text().rsplit(")", 1)[1].split()[19]
    btime = next(ln for ln in Path("/proc/stat").read_text().splitlines() if ln.startswith("btime ")).split()[1]
    return f"{btime}.{start}"


class BootId(unittest.TestCase):
    def test_all_three_say_the_same(self):
        here = layout.boot_id()
        self.assertTrue(here)
        self.assertEqual(census.boot_id(), here)
        self.assertEqual(bbtty("boot_id"), here)

    def test_digits_alone_since_a_census_keeps_only_those(self):
        self.assertRegex(layout.boot_id(), r"^[0-9]+\.[0-9]+$")

    def test_the_clock_is_not_read(self):
        real = Path.read_text

        def no_btime(path, *a, **k):
            if str(path) == "/proc/stat":
                raise AssertionError("read btime with a boot id to hand")
            return real(path, *a, **k)
        with mock.patch.object(Path, "read_text", no_btime):
            self.assertTrue(layout.boot_id())

    def test_btime_stands_in_where_the_kernel_gives_no_id(self):
        real = Path.read_text

        def no_id(path, *a, **k):
            if str(path).endswith("random/boot_id"):
                raise OSError("no such file")
            return real(path, *a, **k)
        with mock.patch.object(Path, "read_text", no_id):
            self.assertEqual(layout.boot_id(), old_shape())


if __name__ == "__main__":
    unittest.main()
