"""The node's uninstall ends and removes only the accounts AerieOS made, and
leaves the doors' rules where their units read them when the doors stay.

account_goes is run as the bash it is, its /etc/aerieos pointed at a
scratch directory; the uninstall's order and the folder's removal are read
as text, since they run as root on a real node."""
import getpass
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.join(HERE, "..", "..", "..", "nodes", "provision-linux.sh")


def core():
    with open(CORE, encoding="utf-8") as f:
        return f.read()


def uninstall():
    src = core()
    a = src.index("cmd_uninstall() {")
    return src[a:src.index("\n}\n", a)]


class AccountGoes(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        src = core()
        a = src.index("account_goes() {")
        self.fn = src[a:src.index("\n}\n", a) + 3].replace("/etc/aerieos", self.d)
        self.me = getpass.getuser()

    def goes(self, user, *, kept=None, made=None):
        for name, names in (("kept-accounts", kept), ("made-accounts", made)):
            p = os.path.join(self.d, name)
            if names is None:
                if os.path.exists(p):
                    os.remove(p)
            else:
                with open(p, "w") as f:
                    f.write("".join(n + "\n" for n in names))
        r = subprocess.run(["bash", "-c", 'say() { echo "$*"; }\n' + self.fn + '\naccount_goes "$1" say', "x", user],
                           capture_output=True, text=True, check=False)
        return r.returncode == 0, r.stdout.strip()

    def test_one_it_made_goes(self):
        self.assertEqual(self.goes(self.me, made=[self.me]), (True, ""))

    def test_one_from_before_any_list_goes_as_it_did(self):
        self.assertEqual(self.goes(self.me), (True, ""))

    def test_one_that_was_here_before_stays_and_is_said(self):
        self.assertEqual(self.goes(self.me, kept=[self.me], made=[self.me]),
                         (False, f"kept {self.me}: it was an account here before AerieOS"))

    def test_one_it_did_not_make_stays_and_is_said(self):
        self.assertEqual(self.goes(self.me, made=["bbu-other"]), (False, f"kept {self.me}: AerieOS did not make it"))

    def test_root_and_nobody_there_never_go(self):
        self.assertFalse(self.goes("root")[0])
        self.assertFalse(self.goes("no-such-account-here")[0])


class Uninstall(unittest.TestCase):
    def test_no_process_is_ended_before_the_account_is_known_to_go(self):
        # Pkill -u ran before the kept-accounts check, so the person's
        # own account, and the shell running the uninstall, could be killed.
        text = uninstall()
        for sig in ("pkill -TERM -u", "pkill -KILL -u"):
            at = text.index(sig)
            loop = text.rfind("for u in", 0, at)
            self.assertIn("account_goes", text[loop:at], sig)
        self.assertEqual(text.count("account_goes"), 3)

    def test_the_doors_rules_stay_when_the_doors_do(self):
        # Without --doors the door-22 and hosting-fw units stay and
        # read their rules from /etc/aerieos at boot, which went whole.
        text = uninstall()
        a = text.index("keep_door=()")
        block = text[a:text.index("/usr/local/sbin/aerie-sandbox", a)]
        self.assertIn('if [ "$doors" != 1 ]', block)
        self.assertIn("door-22.nft hosting-fw.nft", block)
        self.assertIn('"${keep_door[@]}"', block)
        self.assertNotIn("rm -rf /etc/aerieos /etc/builderbot", text)


if __name__ == "__main__":
    unittest.main()
