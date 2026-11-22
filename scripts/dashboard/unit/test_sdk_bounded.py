"""A warm-up that outlives its limit is ended whole (sdk.sh sdk_bounded).

A toolchain's warm-up runs a vendor's own tool for the first time, bounded
so one that hangs fails that toolchain alone. `timeout` was the bound, and a
tool whose script traps the signal and goes on waiting in a loop outlived
it on a node whose timeout signals only the process it started: what was
left kept the directory busy, the partial install could not be removed, and
the next install was refused as in use. The bound is the installer's own
now: the command in a session of its own, and the whole group ended.
"""
import os
import subprocess
import tempfile
import time
import unittest

SDK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib", "sdk.sh")
# The function alone, as sdk.sh defines it: the file whole wants a store.
FUNC = "eval \"$(sed -n '/^sdk_bounded() {/,/^}/p' \"$SDK\")\"\n"


def sh(script, **env):
    return subprocess.run(["bash", "-c", FUNC + script], env=dict(os.environ, SDK=SDK, **env), capture_output=True, text=True,
                          timeout=60, check=False)


def alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    # A process ended and not yet reaped still answers the signal.
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


class Bounded(unittest.TestCase):
    def test_a_script_that_traps_the_signal_and_its_children_are_all_ended(self):
        d = tempfile.mkdtemp()
        stubborn = os.path.join(d, "stubborn.sh")
        with open(stubborn, "w") as f:
            # As a vendor's launcher waiting for its own lock: the signal
            # trapped, a child loop beside it, each sleeping in turn.
            f.write("#!/bin/bash\ntrap 'echo trapped' TERM INT\n"
                    f"( echo $BASHPID > {d}/child; while :; do sleep 0.2; done ) &\n"
                    f"echo $$ > {d}/main\nwhile :; do sleep 0.2; done\n")
        os.chmod(stubborn, 0o755)
        began = time.time()
        r = sh(f"sdk_bounded 2 {stubborn}; echo rc=$?")
        self.assertIn("rc=124", r.stdout, r.stdout + r.stderr)
        self.assertLess(time.time() - began, 20)
        time.sleep(0.5)
        for name in ("main", "child"):
            with open(os.path.join(d, name)) as f:
                self.assertFalse(alive(int(f.read())), f"the script's {name} process outlived the bound")

    def test_a_command_that_ends_in_time_answers_its_own_exit_and_keeps_its_environment(self):
        r = sh("sdk_bounded 20 sh -c 'exit 7'; echo rc=$?")
        self.assertIn("rc=7", r.stdout)
        r = sh("WARM=yes sdk_bounded 20 sh -c 'echo \"warm=$WARM\"'; echo rc=$?")
        self.assertIn("warm=yes", r.stdout)
        self.assertIn("rc=0", r.stdout)

    def test_it_reads_nothing(self):
        # Asked of nobody: a tool that would prompt finds no terminal to wait on.
        r = sh("echo typed | sdk_bounded 20 sh -c 'read -r x; echo \"got=[$x]\"'; echo rc=$?")
        self.assertIn("got=[]", r.stdout)


if __name__ == "__main__":
    unittest.main()
