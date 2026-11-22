"""The root tier is run where it can be root and nowhere it should not be
(R240 step 5, R3 step 8; the operator's choice of 14 Nov: a container tier,
in CI).

Its modules (scripts/dashboard/roottier) plant a link where the root agent
or a root helper works and see that root's own file is as it was; they mean
something only as root, which no suite here is. This holds what an ordinary
account can: the runner's refusals, that no module skips itself, the door
the dev instance's test command reaches it by, and the two places CI runs
it."""
import importlib.util
import os
import re
import unittest

try:
    import yaml
except ImportError:                                            # pragma: no cover
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TIER = os.path.join(ROOT, "scripts", "dashboard", "roottier")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read(*rel):
    with open(os.path.join(ROOT, *rel), encoding="utf-8") as f:
        return f.read()


runner = load(os.path.join(ROOT, "scripts", "lib", "roottier.py"), "roottier_runner")


class Runner(unittest.TestCase):
    def test_it_runs_as_root_in_a_container_and_says_why_not_otherwise(self):
        self.assertIn("runs as root, which this is not", runner.refusal(1000, True, False))
        self.assertIn("runs as root, which this is not", runner.refusal(1000, False, True))
        self.assertIn("not in a container", runner.refusal(0, False, False))
        self.assertEqual(runner.refusal(0, True, False), "")
        self.assertEqual(runner.refusal(0, False, True), "", "--here says this machine is meant")

    def test_started_as_an_ordinary_account_it_runs_nothing(self):
        if os.geteuid() == 0:
            self.skipTest("this is root")
        self.assertEqual(runner.main([]), 2)

    def test_its_modules_are_found_where_it_looks(self):
        self.assertEqual(runner.TIER, TIER)
        mods = sorted(f for f in os.listdir(TIER) if f.startswith("test_") and f.endswith(".py"))
        self.assertEqual(mods, ["test_root_file_work.py", "test_root_session.py", "test_root_sync.py"])

    def test_no_module_skips_itself(self):
        # As root in a container everything a test needs is there, so one
        # that skipped proved nothing; the runner fails the tier on a skip,
        # and none is written to.
        for f in sorted(os.listdir(TIER)):
            if f.endswith(".py"):
                self.assertIsNone(re.search(r"skipTest|skipUnless|skipIf|unittest\.skip", read("scripts", "dashboard", "roottier", f)), f)
        self.assertIn("r.skipped", read("scripts", "lib", "roottier.py"))


class Doors(unittest.TestCase):
    def test_the_dev_instances_test_command_reaches_it_before_the_harness_gives_root_up(self):
        src = read("scripts", "dashboard", "test", "run.sh")
        door = src.index('if [ "${1:-}" = root-tier ]; then')
        self.assertLess(door, src.index("exec runuser -u builder"), "after the drop to builder it would not be root")
        self.assertIn('exec python3 "$HERE/../../lib/roottier.py" "$@"', src[door:door + 200])

    def test_aerie_tests_root_runs_it_as_root_or_in_a_container_or_says_where(self):
        src = read("scripts", "aerie")
        at = src.index('if [ "${1:-}" = root ]; then')
        block = src[at:src.index("\n    fi\n", src.index("die ", at)) + 8]
        self.assertIn('python3 "$rt/scripts/lib/roottier.py" "$@"', block)
        self.assertIn('bash "$rt/tools/root-tier.sh" --tree "$rt" "" "$@"', block)
        self.assertIn("aerie devapp test root-tier", block)

    def test_the_container_is_thrown_away_and_the_tree_is_never_written(self):
        src = read("tools", "root-tier.sh")
        for line in (l for l in src.splitlines() if l.lstrip().startswith("exec docker run")):
            self.assertIn("--rm", line)
            self.assertIn("--user 0", line)
        self.assertIn('-v "$tree:/src:ro"', src)
        self.assertEqual(src.count("docker run"), 2)


@unittest.skipUnless(yaml, "PyYAML reads the workflows")
class InCi(unittest.TestCase):
    def wf(self, name):
        with open(os.path.join(ROOT, ".github", "workflows", name), encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_every_pull_request_and_every_tags_gate_runs_the_checkouts(self):
        # lint.yml is what a pull request runs, what a tag's gate calls and
        # what the rehearsal calls: its jobs are needed whole by each.
        job = self.wf("lint.yml")["jobs"]["root"]
        self.assertEqual(job["runs-on"], "ubuntu-24.04", "hosted: nothing of the box's is root's to touch")
        self.assertIn("tools/root-tier.sh --tree .", "\n".join(str(s.get("run") or "") for s in job["steps"]))
        self.assertNotIn("if", job, "a hosted job holds no secret, so a fork's request runs it too")
        for name, key in (("build-image.yml", "lint"), ("release-rehearsal.yml", "lint")):
            self.assertEqual(self.wf(name)["jobs"][key]["uses"], "./.github/workflows/lint.yml", name)

    def test_a_release_runs_the_images_own_copy_before_anything_is_published(self):
        jobs = self.wf("build-image.yml")["jobs"]
        runs = "\n".join(str(s.get("run") or "") for s in jobs["upgrade"]["steps"])
        self.assertIn('tools/root-tier.sh "$image"', runs)
        n = jobs["release"]["needs"]
        self.assertIn("upgrade", [n] if isinstance(n, str) else n)


if __name__ == "__main__":
    unittest.main()
