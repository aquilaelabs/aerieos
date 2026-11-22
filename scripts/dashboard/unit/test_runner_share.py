"""A node's CI runner is held to its share of the machine (R271): its unit
puts it in AerieOS's fence where the node has one, slows it past half the
memory, kills it inside its own share past three fifths, lets it swap a
quarter of the swap at most, and makes it the kernel's to take before the
sessions. A runner whose unit an older agent or svc.sh wrote is brought to
that unit on a hello while it is idle, and left alone while a job runs."""
import os
import shutil
import tempfile
import unittest

import agentpkg  # noqa: E402

pkg = agentpkg.load("aerieos_agent_runner_share")
runners = pkg.module("runners")
base = pkg.module("base")
runners.log = lambda *a, **k: None

SWAP = {"SwapTotal": 4194300}
# What svc.sh wrote on bb-sandbox, before this agent wrote the unit itself.
SVC_SH = """[Unit]
Description=GitHub Actions Runner (aquilaelabs.bb-sandbox)
After=network-online.target

[Service]
ExecStart={d}/runsvc.sh
User=bb
WorkingDirectory={d}
KillMode=process
KillSignal=SIGTERM
TimeoutStopSec=5min

[Install]
WantedBy=multi-user.target
"""
UNIT = "actions.runner.aquilaelabs.bb-sandbox.service"


class Share(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="runner-share-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.units = os.path.join(self.tmp, "units")
        self.d = os.path.join(self.tmp, "runner")
        os.makedirs(self.units)
        os.makedirs(self.d)

    def test_in_the_fence_where_the_node_has_one(self):
        self.assertNotIn("Slice=", runners.runner_share(self.units, SWAP))
        open(os.path.join(self.units, "builderbot.slice"), "w").close()
        share = runners.runner_share(self.units, SWAP)
        self.assertEqual(share.splitlines(), ["Slice=builderbot.slice", "MemoryHigh=50%", "MemoryMax=60%",
                                              f"MemorySwapMax={4194300 // 4 * 1024}", "OOMScoreAdjust=300"])

    def test_no_swap_is_no_swap_for_it(self):
        self.assertIn("MemorySwapMax=0\n", runners.runner_share(self.units, {}))

    def test_the_unit_is_githubs_template_with_the_share_in_its_service(self):
        text = runners.runner_unit_text(self.d, "bb", "aquilaelabs.bb-sandbox", self.units, SWAP)
        service = text.split("[Service]\n", 1)[1].split("\n[Install]", 1)[0]
        self.assertIn(f"ExecStart={self.d}/runsvc.sh\nUser=bb\n", service)
        self.assertIn("MemoryMax=60%\n", service)
        self.assertIn("OOMScoreAdjust=300", service)
        self.assertTrue(text.endswith("[Install]\nWantedBy=multi-user.target\n"))

    def test_a_unit_svc_sh_wrote_is_due_and_one_already_written_is_not(self):
        with open(os.path.join(self.units, UNIT), "w") as f:
            f.write(SVC_SH.format(d=self.d))
        self.assertEqual(runners.unit_due(self.d, UNIT, self.units, SWAP), "", "no runsvc.sh at its top: not this agent's to write")
        open(os.path.join(self.d, "runsvc.sh"), "w").close()
        due = runners.unit_due(self.d, UNIT, self.units, SWAP)
        self.assertIn("User=bb\n", due)
        self.assertIn("MemoryHigh=50%\n", due)
        with open(os.path.join(self.units, UNIT), "w") as f:
            f.write(due)
        self.assertEqual(runners.unit_due(self.d, UNIT, self.units, SWAP), "")

    def test_an_account_it_cannot_name_plainly_is_left(self):
        open(os.path.join(self.d, "runsvc.sh"), "w").close()
        with open(os.path.join(self.units, UNIT), "w") as f:
            f.write(SVC_SH.format(d=self.d).replace("User=bb", "User=../root"))
        self.assertEqual(runners.unit_due(self.d, UNIT, self.units, SWAP), "")

    def test_a_job_starts_at_the_score_the_kernel_takes_first(self):
        argv = base.oom_first(["bash", "./run.sh"], 300)
        self.assertEqual(argv[:2], ["sh", "-c"])
        self.assertIn("echo 300 > /proc/self/oom_score_adj", argv[2])
        self.assertEqual(argv[3:], ["sh", "bash", "./run.sh"])
        self.assertIn("echo 500 ", base.oom_first(["make"])[2])


class Sync(unittest.TestCase):
    """The hello's pass over an installed runner, as bb-sandbox's was."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="runner-sync-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.units = os.path.join(self.tmp, "units")
        self.d = os.path.join(self.tmp, "runner")
        os.makedirs(self.units)
        os.makedirs(self.d)
        open(os.path.join(self.d, "runsvc.sh"), "w").close()
        with open(os.path.join(self.d, ".service"), "w") as f:
            f.write(UNIT + "\n")
        with open(os.path.join(self.units, UNIT), "w") as f:
            f.write(SVC_SH.format(d=self.d))
        for name, value in (("UNIT_DIR", self.units), ("has_systemd", lambda: True),
                            ("runner_busy", lambda d: self.busy)):
            self.addCleanup(setattr, runners, name, getattr(runners, name))
            setattr(runners, name, value)
        self.busy = False
        self.ran = []
        state = {"user": "bb"}
        test = self

        class Node(runners.RunnersMixin):
            def __init__(self):
                self.state = state

            def as_user(self, env, name):
                return {}

            def own_dir(self, d, who):
                pass

            def _sh(self, job, argv):
                test.ran.append(argv[1:])
                return 0

            def runner_stop(self, d=None):
                test.ran.append(["stop"])

            def runner_start(self, who, job=None, d=None):
                test.ran.append(["start"])

        self.node = Node()
        with open(os.path.join(self.d, ".env"), "w") as f:
            f.write(runners.runner_env_text(state))

    def unit(self):
        with open(os.path.join(self.units, UNIT)) as f:
            return f.read()

    def test_idle_it_is_rewritten_reloaded_and_restarted_once(self):
        self.node._runner_sync(self.d)
        self.assertIn("MemoryMax=60%\n", self.unit())
        self.assertEqual(self.ran, [["daemon-reload"], ["restart", UNIT]])
        self.ran.clear()
        self.node._runner_sync(self.d)
        self.assertEqual(self.ran, [], "nothing more once it holds its share")

    def test_busy_it_is_left_for_the_next_hello(self):
        self.busy = True
        self.node._runner_sync(self.d)
        self.assertNotIn("MemoryMax", self.unit())
        self.assertEqual(self.ran, [])


if __name__ == "__main__":
    unittest.main()
