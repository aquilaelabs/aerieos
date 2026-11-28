"""A job's source on a node, as root for real: the snapshot cache and the
job's folder (the review of 22 Nov).

A space named `snapshots` was handed the agent's snapshot cache as its own
cache, and root then fetched HEX.tar.part there by name; the job's folder
was made and its marker written by name too. Each test plants what a job
could, and what is root's is as it was."""
import hashlib
import io
import os
import tarfile
import unittest

import world

AGENT = world.agent("root_materialize")
NAME, UID, GID = world.account()
WHO = (UID, GID)


def snapshot():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, text in (("a.txt", b"one\n"), ("src/b.txt", b"two\n")):
            info = tarfile.TarInfo(name)
            info.size = len(text)
            tar.addfile(info, io.BytesIO(text))
    raw = buf.getvalue()
    return hashlib.sha256(raw).hexdigest(), raw


class TheJobsSource(unittest.TestCase):
    def setUp(self):
        self.w = world.World(self)
        self.cache, self.data = self.w.folder("cache"), self.w.folder("data")
        self.hexd, raw = snapshot()
        self.served = world.Served(self, raw)
        self.a = object.__new__(AGENT.Agent)
        self.a.ctl = AGENT.Controller(self.served.url, "bbn_test")
        self.a.state = {"user": NAME, "stores": {"cache": self.cache, "data": self.data}}
        self.a.jobs = {}
        self.said = []
        self.who = self.a.drop_privileges({})

    def job(self, jid):
        said = self.said
        return type("Job", (), {"say": lambda self, t: said.append(t), "outputs": [],
                                "job": {"id": jid, "source": {"project": "snapshots"}}})()

    def materialize(self, jid="j_1"):
        return self.a.materialize(self.job(jid), {"digest": "sha256:" + self.hexd, "project": "snapshots"}, self.who)

    def test_a_space_named_snapshots_does_not_hold_the_snapshot_cache(self):
        # Its cache, as jobs.py gives it, with a link left where an older
        # agent fetched the snapshot and where it kept it.
        theirs = self.w.folder("cache/snapshots", WHO)
        for name in (self.hexd + ".tar.part", self.hexd + ".tar"):
            os.symlink(self.w.secret, os.path.join(theirs, name))
            os.lchown(os.path.join(theirs, name), UID, GID)
        ws = self.materialize()
        self.assertIsNotNone(ws, self.said)
        self.assertEqual(self.w.intact(), "")
        snaps = os.path.join(self.cache, AGENT.SNAPSHOTS)
        st = os.lstat(snaps)
        self.assertEqual((st.st_uid, st.st_mode & 0o777), (0, 0o700), "the snapshots are in a folder of root's alone")
        self.assertEqual(os.listdir(snaps), [self.hexd + ".tar"])

    def test_the_workspace_is_unpacked_as_the_jobs_account(self):
        ws = self.materialize()
        self.assertIsNotNone(ws, self.said)
        for rel in ("", "a.txt", "src", "src/b.txt"):
            st = os.lstat(os.path.join(ws, rel))
            self.assertEqual((st.st_uid, st.st_gid), WHO, rel or "the workspace")
        self.assertEqual(os.lstat(os.path.join(self.data, "jobs")).st_uid, 0, "the folder of every job's is root's")

    def test_a_link_the_job_left_at_its_marker_is_not_written_through(self):
        ws = self.materialize()
        jobdir = os.path.dirname(ws)
        os.unlink(os.path.join(jobdir, "project"))
        os.symlink(self.w.secret, os.path.join(jobdir, "project"))
        os.lchown(os.path.join(jobdir, "project"), UID, GID)
        self.a.finish_workspace(self.job("j_1"), ws, {}, "failed")
        self.assertEqual(self.w.intact(), "")
        with open(os.path.join(jobdir, "project")) as f:
            self.assertEqual(f.read(), "snapshots")

    def test_a_kept_failure_whose_marker_is_a_link_is_passed_over_unread(self):
        ws = self.materialize("j_1")
        self.a.finish_workspace(self.job("j_1"), ws, {}, "failed")
        jobdir = os.path.dirname(ws)
        os.unlink(os.path.join(jobdir, "project"))
        os.symlink(self.w.secret, os.path.join(jobdir, "project"))
        ws2 = self.materialize("j_2")
        self.a.finish_workspace(self.job("j_2"), ws2, {}, "failed")
        self.assertEqual(self.w.intact(), "")


if __name__ == "__main__":
    unittest.main()
