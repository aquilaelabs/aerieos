"""A node's folders and service under AerieOS's own name (R204): the agent
answers with whichever is really there and only ever adds a link under a
running machine, and the Enroll script is what moves a folder, leaving the
old name a link to it, or leaving the folder where a move would break what
holds it by its path."""
import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "agent"))
from aerieos_agent import names  # noqa: E402

PROV = os.path.join(HERE, "..", "..", "..", "nodes", "provision-linux.sh")


class Which(unittest.TestCase):
    def test_the_new_name_where_it_is_the_old_where_only_that_is(self):
        d = tempfile.mkdtemp()
        new, old = os.path.join(d, "aerieos"), os.path.join(d, "builderbot")
        self.assertEqual(names._home(new, old), new, "a machine with neither starts on the new name")
        os.mkdir(old)
        self.assertEqual(names._home(new, old), old, "one not yet met by the Enroll script keeps the old")
        os.symlink(old, new)
        self.assertEqual(names._home(new, old), new, "a link under the new name answers as the folder does")


def move_fn():
    """names_move out of the provisioner, its folders pointed at a scratch one."""
    text = open(PROV).read()
    body = re.search(r"^names_move\(\) \{\n.*?^\}\n", text, re.S | re.M).group(0)
    return body


class Move(unittest.TestCase):
    def run_move(self, d):
        body = move_fn().replace("/etc/aerieos:/etc/builderbot", f"{d}/etc/aerieos:{d}/etc/builderbot") \
                        .replace("/var/lib/aerieos:/var/lib/builderbot", f"{d}/var/lib/aerieos:{d}/var/lib/builderbot") \
                        .replace('[ "$old" = /var/lib/builderbot ]', f'[ "$old" = {d}/var/lib/builderbot ]')
        script = 'say() { echo "say: $*"; }; warn() { echo "warn: $*"; }\n' + body + "\nnames_move\n"
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30, check=False)

    def test_each_folder_is_renamed_and_the_old_name_left_a_link(self):
        d = tempfile.mkdtemp()
        os.makedirs(f"{d}/etc/builderbot"); os.makedirs(f"{d}/var/lib/builderbot/data")
        open(f"{d}/etc/builderbot/node.json", "w").write('{"node_id": "n_1"}')
        os.symlink(f"{d}/etc/builderbot", f"{d}/etc/aerieos")          # the link an agent added first
        r = self.run_move(d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isdir(f"{d}/etc/aerieos") and not os.path.islink(f"{d}/etc/aerieos"))
        self.assertTrue(os.path.islink(f"{d}/etc/builderbot"))
        self.assertEqual(open(f"{d}/etc/builderbot/node.json").read(), '{"node_id": "n_1"}', "the old path still reads it")
        self.assertTrue(os.path.isdir(f"{d}/var/lib/aerieos/data") and os.path.islink(f"{d}/var/lib/builderbot"))
        again = self.run_move(d)
        self.assertEqual((again.returncode, again.stdout), (0, ""), "run again, there is nothing to do")

    def test_where_vms_keep_their_disks_the_folder_stays(self):
        d = tempfile.mkdtemp()
        os.makedirs(f"{d}/etc/builderbot"); os.makedirs(f"{d}/var/lib/builderbot/vms/disks")
        open(f"{d}/var/lib/builderbot/vms/disks/a.qcow2", "w").write("x")
        r = self.run_move(d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isdir(f"{d}/var/lib/builderbot") and not os.path.islink(f"{d}/var/lib/builderbot"))
        self.assertTrue(os.path.islink(f"{d}/var/lib/aerieos"))
        self.assertTrue(os.path.exists(f"{d}/var/lib/aerieos/vms/disks/a.qcow2"), "and the new name answers")

    def test_a_fresh_machine_is_left_alone(self):
        d = tempfile.mkdtemp()
        self.assertEqual(self.run_move(d).stdout, "")
        self.assertFalse(os.path.exists(f"{d}/etc"))


if __name__ == "__main__":
    unittest.main()
