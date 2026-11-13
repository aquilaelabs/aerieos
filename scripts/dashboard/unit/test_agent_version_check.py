"""The agent's version moves with every change to the agent (R241; the audit
of 13 Nov): tools/agent-version.sh measured from the branch's merge point
with main, so one bump early on a long branch passed every change after it,
and one commit changed the agent with no bump. It measures from the commit
that last moved the number now."""
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.normpath(os.path.join(HERE, "..", "..", "..", "tools", "agent-version.sh"))
INIT = "scripts/agent/aerieos_agent/__init__.py"


class Check(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        os.makedirs(os.path.join(self.d, "scripts/agent/aerieos_agent"))
        self.git("init", "-q", "-b", "main")
        self.put(INIT, 'AGENT_VERSION = "0.9.1"\n')
        self.put("scripts/agent/builderbot-agent.py", "# the entry\n")
        self.put("scripts/agent/aerieos_agent/work.py", "x = 1\n")
        self.commit("the agent")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("checkout", "-q", "-b", "long-branch")

    def git(self, *argv):
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *argv],
                              cwd=self.d, capture_output=True, text=True, check=True).stdout

    def put(self, rel, text):
        with open(os.path.join(self.d, rel), "w") as f:
            f.write(text)

    def commit(self, said):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", said)

    def check(self):
        p = subprocess.run(["sh", TOOL], cwd=self.d, capture_output=True, text=True, check=False)
        return p.returncode, p.stdout.strip()

    def test_every_change_after_a_bump_needs_the_next(self):
        self.assertEqual(self.check()[0], 0)
        # A change with its bump, early on the branch.
        self.put("scripts/agent/aerieos_agent/work.py", "x = 2\n")
        self.put(INIT, 'AGENT_VERSION = "0.9.2"\n')
        self.commit("a change and its bump")
        self.assertEqual(self.check()[0], 0)
        # A later change with none: this passed, since the number differed from main's.
        self.put("scripts/agent/aerieos_agent/work.py", "x = 3\n")
        self.commit("a change with no bump")
        rc, said = self.check()
        self.assertEqual(rc, 1, said)
        self.assertIn("AGENT_VERSION", said)
        # ...in the working tree as well, before it is committed.
        self.git("reset", "-q", "--hard", "HEAD~1")
        self.put("scripts/agent/builderbot-agent.py", "# the entry, changed\n")
        self.assertEqual(self.check()[0], 1)
        # The bump beside it, committed or not, is what it asks for.
        self.put(INIT, 'AGENT_VERSION = "0.9.3"\n')
        self.assertEqual(self.check()[0], 0)
        self.commit("the change and its bump")
        self.assertEqual(self.check()[0], 0)

    def test_what_is_not_the_agent_asks_for_nothing(self):
        self.put("scripts/agent/ruff.toml", "line-length = 100\n")
        self.put("README.md", "words\n")
        self.commit("neither is what a node runs")
        self.assertEqual(self.check()[0], 0)


if __name__ == "__main__":
    unittest.main()
