"""What the supervisor asks of the dashboard (R246; the audit of 13 Nov):
it found the server by 'dashboard/server.py' on any command line, which a
test harness's copy answers to as well, and wrote its saved-sessions file
with printf, so a folder's name with a quote in it spoiled the file. The
server leaves its pid beside its lock now, and scripts/lib/supervise.sh
reads it and escapes what it writes."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

LIB = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib", "supervise.sh"))


def sh(body, **env):
    p = subprocess.run(["bash", "-c", f". {LIB}\n{body}"], capture_output=True, text=True, check=False,
                       env={**os.environ, **env})
    return p.returncode, p.stdout


class Pid(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        os.makedirs(os.path.join(self.d, "dashboard"))
        self.server = os.path.join(self.d, "dashboard", "server.py")
        with open(self.server, "w") as f:
            f.write("import time\ntime.sleep(60)\n")

    def spawn(self, argv):
        p = subprocess.Popen(argv)
        self.addCleanup(lambda: (p.kill(), p.wait()))
        return p

    def left(self, text):
        with open(os.path.join(self.d, ".server.pid"), "w") as f:
            f.write(text)

    def test_the_pid_the_server_left_while_it_is_a_server(self):
        p = self.spawn([sys.executable, self.server])
        self.left(f"{p.pid}\n")
        self.assertEqual(sh(f"dashboard_pid {self.d}"), (0, f"{p.pid}\n"))
        # ...read from DASHBOARD_STATE where no folder is named.
        self.assertEqual(sh("dashboard_pid", DASHBOARD_STATE=self.d), (0, f"{p.pid}\n"))

    def test_not_a_pid_that_is_gone_or_is_something_else_now(self):
        gone = self.spawn([sys.executable, "-c", "pass"])
        gone.wait()
        self.left(f"{gone.pid}\n")
        self.assertEqual(sh(f"dashboard_pid {self.d}")[0], 1)
        other = self.spawn(["sleep", "60"])
        self.left(f"{other.pid}\n")
        self.assertEqual(sh(f"dashboard_pid {self.d}"), (1, ""), "the number went to another process: not the dashboard")
        for junk in ("", "soon\n", "12; rm -rf /\n"):
            self.left(junk)
            self.assertEqual(sh(f"dashboard_pid {self.d}"), (1, ""), junk)

    def test_a_copy_of_the_server_elsewhere_is_not_this_one(self):
        # The harness's copy runs beside the real one on a node: with a pid
        # left here, only that process answers.
        mine = self.spawn([sys.executable, self.server])
        elsewhere = self.spawn([sys.executable, self.server])
        self.left(f"{mine.pid}\n")
        self.assertEqual(sh(f"dashboard_pid {self.d}"), (0, f"{mine.pid}\n"))
        self.assertNotEqual(mine.pid, elsewhere.pid)


class Json(unittest.TestCase):
    def test_a_folders_name_cannot_spoil_the_file(self):
        for name in ('/work/plain', '/work/my "quoted" app', "/work/back\\slash", "/work/tab\there", "/work/bell\x07"):
            rc, out = sh('printf \'{"cwd": "%s"}\' "$(json_str "$1")"'.replace("$1", "$NAME"), NAME=name)
            self.assertEqual(rc, 0)
            want = "".join(c for c in name if c >= " " or c == "\t")
            self.assertEqual(json.loads(out)["cwd"], want, name)


if __name__ == "__main__":
    unittest.main()
