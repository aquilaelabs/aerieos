"""A suite run on a commit (R55): run.sh's --at copies the commit with git
archive, so an edit in the working tree is not in it, and without --at the
copy is the working tree's, as it always was. The block is run.sh's own,
run against a scratch repository with the exec that starts the copy's
harness said instead of done."""
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.abspath(os.path.join(HERE, "..", "test", "run.sh"))
with open(RUN, encoding="utf-8") as f:
    SRC = f.read()
EXEC = 'exec bash "$_dst/scripts/dashboard/test/run.sh" "$@"'


def block():
    start = SRC.index("# A run on a commit (R55)")
    end = SRC.index("\nfi\n", SRC.index(EXEC, start)) + len("\nfi\n")
    return SRC[start:end].replace(EXEC, 'echo "RAN $_dst $*"')


class At(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        os.makedirs(os.path.join(self.repo, "scripts", "dashboard", "test"))
        open(os.path.join(self.repo, "scripts", "dashboard", "test", "run.sh"), "w").write("true\n")
        open(os.path.join(self.repo, "a.txt"), "w").write("committed\n")
        g = ["git", "-C", self.repo, "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(g[:3] + ["init", "-q"], check=True)
        subprocess.run(g + ["add", "-A"], check=True)
        subprocess.run(g + ["commit", "-qm", "one"], check=True)
        open(os.path.join(self.repo, "a.txt"), "w").write("edited, not committed\n")

    def run_block(self, *args, env=None):
        script = ("set -euo pipefail\nHERE=" + os.path.join(self.repo, "scripts", "dashboard", "test") + "\n"
                  + "die() { echo \"died: $*\" >&2; exit 1; }\n" + block())
        e = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "TMPDIR": self.tmp, "HOME": self.tmp, **(env or {})}
        r = subprocess.run(["bash", "-c", script, "run.sh", *args], capture_output=True, text=True, env=e)
        ran = [x for x in r.stdout.splitlines() if x.startswith("RAN ")]
        return r, (ran[0].split()[1] if ran else ""), (ran[0].split()[2:] if ran else [])

    def read(self, dst):
        return open(os.path.join(dst, "a.txt")).read()

    def test_at_a_commit_the_edit_is_not_there(self):
        r, dst, rest = self.run_block("cards", "--at", "HEAD")
        self.assertTrue(dst, r.stderr)
        self.assertEqual(self.read(dst), "committed\n")
        self.assertEqual(rest, ["cards"], "--at is the copy's business, not the suite's")
        self.assertIn("running commit", r.stderr)

    def test_the_environment_says_it_too(self):
        r, dst, _ = self.run_block("cards", env={"BB_TEST_AT": "HEAD"})
        self.assertEqual(self.read(dst), "committed\n", r.stderr)

    def test_without_it_the_working_tree(self):
        r, dst, _ = self.run_block("cards")
        self.assertEqual(self.read(dst), "edited, not committed\n", r.stderr)

    def test_no_such_commit_is_said(self):
        r, dst, _ = self.run_block("cards", "--at", "nope")
        self.assertEqual((r.returncode, dst), (2, ""))
        self.assertIn("no such commit", r.stderr)


class LauncherGone(unittest.TestCase):
    """B926: run.sh's launcher_watch ends the run once whoever started it
    is gone, the way a TERM ends it, and spares a kept one."""
    def watch(self, env=None):
        start = SRC.index("launcher_watch() {")
        fn = SRC[start:SRC.index("\n}\n", start) + 3]
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        out = os.path.join(d, "said")
        child = os.path.join(d, "child.sh")
        open(child, "w").write(fn + f"\ntrap 'echo ended > {out}; exit 0' TERM\nlauncher_watch\n"
                               "for _ in $(seq 40); do sleep 0.25 & wait $!; done\necho outlived > " + out + "\n")
        e = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), **(env or {})}
        # The launcher starts the run and goes, as a gate ended by its pid
        # does: after the run has started under it, as a gate's has.
        subprocess.run(["bash", "-c", f"bash {child} > /dev/null 2>&1 & disown; sleep 1; exit 0"], env=e, check=True)
        import time
        for _ in range(60):
            if os.path.exists(out) and open(out).read().strip():
                break
            time.sleep(0.25)
        return open(out).read().strip() if os.path.exists(out) else ""

    def test_a_run_whose_launcher_is_gone_ends(self):
        self.assertEqual(self.watch(), "ended")

    def test_a_kept_run_outlives_it(self):
        self.assertEqual(self.watch({"BB_TEST_HOLD": "1"}), "outlived")


if __name__ == "__main__":
    unittest.main()
