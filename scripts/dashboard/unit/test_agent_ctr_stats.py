"""What each running container uses, read by the agent once a minute for the
hour the controller keeps: one docker stats, its lines read
into [cpu %, memory %] by name, a line it cannot read skipped, and nothing at
all said between two minutes or where there is no docker. The read runs on a
thread of its own and its answer rides a later turn."""
import os
import sys
import tempfile
import time
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agentpkg  # noqa: E402

agent = agentpkg.load("aerieos_agent_ctr_stats")


class CtrStats(unittest.TestCase):
    def fake_docker(self, out):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "docker")
        with open(path, "w") as f:
            f.write("#!/bin/sh\ncat <<'EOF'\n" + out + "EOF\n")
        os.chmod(path, 0o755)
        agent.DOCKER_BIN = path

    def handed(self, me, wait=10):
        """stats_now asked turn after turn until it hands an answer over."""
        end = time.monotonic() + wait
        while time.monotonic() < end:
            got = agent.SessionsMixin.stats_now(me)
            if got is not None:
                return got
            if not getattr(me, "stats_reading", False) and getattr(me, "stats_got", None) is None:
                return None
            time.sleep(0.02)
        return None

    def test_a_minutes_sample_is_read_into_numbers(self):
        self.fake_docker("web-1\t12.50%\t3.25%\nweird line\ndb-1\t--\t1%\nnginx\t0.00%\t0.40%\n")
        me = types.SimpleNamespace()
        self.assertIsNone(agent.SessionsMixin.stats_now(me), "the turn that starts the read does not wait for it")
        self.assertEqual(self.handed(me), {"web-1": [12.5, 3.25], "nginx": [0.0, 0.4]})
        # ...and nothing again until the minute is up.
        self.assertIsNone(agent.SessionsMixin.stats_now(me))
        self.assertFalse(getattr(me, "stats_reading", False))

    def test_the_read_does_not_hold_the_turn(self):
        # A docker that takes its time: the turn that starts it goes on.
        self.fake_docker("web-1\t1.00%\t2.00%\n")
        with open(agent.DOCKER_BIN, "w") as f:
            f.write("#!/bin/sh\nsleep 1\nprintf 'web-1\\t1.00%%\\t2.00%%\\n'\n")
        me = types.SimpleNamespace()
        t0 = time.monotonic()
        self.assertIsNone(agent.SessionsMixin.stats_now(me))
        self.assertLess(time.monotonic() - t0, 0.5)
        self.assertEqual(self.handed(me), {"web-1": [1.0, 2.0]})

    def test_docker_is_found_on_the_path_by_its_bare_name(self):
        # DOCKER_BIN is "docker" unless the environment names a path,
        # and os.access on that bare name looked in the working directory.
        self.fake_docker("web-1\t1.00%\t2.00%\n")
        d = os.path.dirname(agent.DOCKER_BIN)
        agent.DOCKER_BIN = "docker"
        old = os.environ.get("PATH", "")
        os.environ["PATH"] = d + os.pathsep + old
        try:
            self.assertEqual(agent.SessionsMixin.stats_read(types.SimpleNamespace()), {"web-1": [1.0, 2.0]})
            self.assertIsNotNone(agent.SessionsMixin.published_now(types.SimpleNamespace()))
        finally:
            os.environ["PATH"] = old

    def test_no_docker_says_nothing(self):
        agent.DOCKER_BIN = "/nonexistent/docker"
        self.assertIsNone(agent.SessionsMixin.stats_now(types.SimpleNamespace()))


if __name__ == "__main__":
    unittest.main()
