"""A job's source on a node: the snapshot cache and the job's folder.

The snapshot is fetched beside itself under a name of the fetch's own,
checked through the one open file and unpacked from it, in a folder of the
cache store no space's cache can be; nothing is followed through a link at
any name on the way, a fetch that stops short leaves nothing and says why,
and the cache and the half-made job folders are swept."""
import hashlib
import io
import os
import re
import shutil
import tarfile
import tempfile
import threading
import time
import types
import unittest

import agentpkg  # noqa: E402
agent = agentpkg.load("aerieos_agent_materialize")
agent.log = lambda *a, **k: None


def snapshot(files):
    """(sha256 hex, bytes) of a tar holding `files`, a {name: text}."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, text in sorted(files.items()):
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    raw = buf.getvalue()
    return hashlib.sha256(raw).hexdigest(), raw


class Ctl:
    """The controller, for a fetch: what it holds by digest, and how each
    fetch is to go ('short' stops half way, as a dropped connection does)."""
    def __init__(self):
        self.has, self.asked, self.how = {}, [], {}

    def fetch_into(self, path, f, timeout=600):
        hexd = path.split("=", 1)[1]
        self.asked.append(hexd)
        how = self.how.get(hexd, "")
        if how == "short":
            f.write(self.has[hexd][:100])
            return 0, "IncompleteRead(100 bytes read)"
        if hexd not in self.has:
            return 404, ""
        f.write(self.has[hexd] if how != "wrong" else b"not the snapshot")
        return 200, ""


class Materialize(unittest.TestCase):
    def setUp(self):
        self.top = tempfile.mkdtemp(prefix="mat-")
        self.addCleanup(shutil.rmtree, self.top, True)
        self.cache, self.data = os.path.join(self.top, "cache"), os.path.join(self.top, "data")
        os.makedirs(self.cache)
        os.makedirs(self.data)
        self.ctl = Ctl()
        self.hexd, raw = snapshot({"a.txt": "one\n", "src/b.txt": "two\n"})
        self.ctl.has[self.hexd] = raw
        self.said = []
        self.me = types.SimpleNamespace(state={"stores": {"cache": self.cache, "data": self.data}}, ctl=self.ctl, jobs={})
        for name in ("_snapshot", "_job_folder", "_jobs_sweep", "materialize", "finish_workspace", "deliver"):
            setattr(self.me, name, types.MethodType(getattr(agent.WorkspaceMixin, name), self.me))
        self.snaps = os.path.join(self.cache, agent.SNAPSHOTS)

    def job(self, jid="j_1"):
        return types.SimpleNamespace(job={"id": jid, "source": {"project": "alpha"}}, say=self.said.append, outputs=[])

    def run_job(self, jid="j_1", hexd=None, project="alpha"):
        return self.me.materialize(self.job(jid), {"digest": "sha256:" + (hexd or self.hexd), "project": project}, None)

    def test_the_snapshot_is_unpacked_into_the_jobs_own_folder(self):
        ws = self.run_job()
        self.assertEqual(ws, os.path.join(os.path.realpath(self.data), "jobs", "j_1", "workspace"))
        with open(os.path.join(ws, "src", "b.txt")) as f:
            self.assertEqual(f.read(), "two\n")
        jobdir = os.path.dirname(ws)
        with open(os.path.join(jobdir, "project")) as f:
            self.assertEqual(f.read(), "alpha")
        self.assertTrue(os.path.exists(os.path.join(jobdir, agent.BUILDING)))

    def test_it_is_kept_under_a_name_no_space_has_and_fetched_once(self):
        self.run_job("j_1")
        self.run_job("j_2")
        self.assertEqual(self.ctl.asked, [self.hexd])
        self.assertEqual(os.listdir(self.snaps), [self.hexd + ".tar"])
        self.assertEqual(os.stat(self.snaps).st_mode & 0o777, 0o700)
        # What a space's cache is named: its name, cleaned as jobs.py cleans it.
        self.assertNotEqual(re.sub(r"[^A-Za-z0-9._-]", "_", agent.SNAPSHOTS), agent.SNAPSHOTS)

    def test_a_cached_snapshot_that_is_not_its_digest_is_fetched_again(self):
        os.makedirs(self.snaps)
        with open(os.path.join(self.snaps, self.hexd + ".tar"), "wb") as f:
            f.write(b"something else")
        ws = self.run_job()
        self.assertTrue(os.path.isfile(os.path.join(ws, "a.txt")))
        self.assertEqual(self.ctl.asked, [self.hexd])
        self.assertIn("did not match its digest", "".join(self.said))

    def test_a_link_where_the_snapshot_goes_is_not_written_through(self):
        os.makedirs(self.snaps)
        victim = os.path.join(self.top, "victim")
        with open(victim, "w") as f:
            f.write("mine")
        os.symlink(victim, os.path.join(self.snaps, self.hexd + ".tar"))
        os.symlink(victim, os.path.join(self.snaps, f"{self.hexd}.{os.getpid()}.{threading.get_ident()}.part"))
        self.assertIsNotNone(self.run_job())
        with open(victim) as f:
            self.assertEqual(f.read(), "mine")
        self.assertFalse(os.path.islink(os.path.join(self.snaps, self.hexd + ".tar")))

    def test_a_link_at_the_cache_folders_name_is_replaced_not_followed(self):
        elsewhere = os.path.join(self.top, "elsewhere")
        os.makedirs(elsewhere)
        os.symlink(elsewhere, self.snaps)
        self.assertIsNotNone(self.run_job())
        self.assertEqual(os.listdir(elsewhere), [])
        self.assertFalse(os.path.islink(self.snaps))

    def test_a_link_at_the_jobs_name_is_replaced_not_followed(self):
        elsewhere = os.path.join(self.top, "elsewhere")
        os.makedirs(os.path.join(elsewhere, "workspace"))
        os.makedirs(os.path.join(self.data, "jobs"))
        os.symlink(elsewhere, os.path.join(self.data, "jobs", "j_1"))
        ws = self.run_job()
        self.assertTrue(os.path.isfile(os.path.join(ws, "a.txt")))
        self.assertEqual(os.listdir(os.path.join(elsewhere, "workspace")), [])

    def test_a_fetch_that_stops_short_says_so_and_leaves_nothing(self):
        self.ctl.how[self.hexd] = "short"
        self.assertIsNone(self.run_job())
        said = "".join(self.said)
        self.assertIn("could not fetch snapshot", said)
        self.assertIn("IncompleteRead", said)
        self.assertNotIn("moved on", said)
        self.assertEqual(os.listdir(self.snaps), [])
        self.assertFalse(os.path.exists(os.path.join(self.data, "jobs", "j_1")))

    def test_a_snapshot_the_controller_no_longer_has_says_the_tree_moved_on(self):
        gone = "0" * 64
        self.assertIsNone(self.run_job(hexd=gone))
        self.assertIn("the tree has moved on", "".join(self.said))
        self.assertEqual(os.listdir(self.snaps), [])

    def test_what_arrives_under_the_wrong_digest_is_not_kept(self):
        self.ctl.how[self.hexd] = "wrong"
        self.assertIsNone(self.run_job())
        self.assertIn("did not match its digest", "".join(self.said))
        self.assertEqual(os.listdir(self.snaps), [])

    def test_a_job_id_that_is_not_one_is_refused(self):
        for bad in ("..", "../x", "", "a/b"):
            self.assertIsNone(self.run_job(jid=bad), bad)
        self.assertFalse(os.path.exists(os.path.join(self.data, "jobs")))

    def test_the_cache_keeps_the_newest_few_and_drops_the_long_unused(self):
        os.makedirs(self.snaps)
        now = time.time()
        names = []
        for i in range(9):
            n = f"{i:064x}.tar"
            names.append(n)
            p = os.path.join(self.snaps, n)
            with open(p, "wb") as f:
                f.write(b"x")
            at = now - (i + 1) * 3600 if i < 8 else now - 30 * 86400
            os.utime(p, (at, at))
        stale = os.path.join(self.snaps, "f" * 64 + ".1.2.part")
        with open(stale, "wb") as f:
            f.write(b"x")
        os.utime(stale, (now - 7200, now - 7200))
        os.symlink("/etc", os.path.join(self.snaps, "stray"))
        self.run_job()
        left = sorted(os.listdir(self.snaps))
        self.assertEqual(left, sorted([self.hexd + ".tar"] + names[:agent.SNAPSHOTS_KEEP - 1]))

    def test_an_older_agents_snapshots_are_dropped_and_a_spaces_files_left(self):
        old = os.path.join(self.cache, "snapshots")
        os.makedirs(old)
        for n in ("a" * 64 + ".tar", "b" * 64 + ".tar.part"):
            with open(os.path.join(old, n), "wb") as f:
                f.write(b"x")
        with open(os.path.join(old, "gradle.lock"), "w") as f:
            f.write("a space's own")
        self.run_job()
        self.assertEqual(os.listdir(old), ["gradle.lock"])

    def test_a_half_made_job_folder_goes_and_a_kept_failure_stays(self):
        jobs = os.path.join(self.data, "jobs")
        for jid, marks in (("j_half", ["project", agent.BUILDING]), ("j_kept", ["project"]), ("j_running", ["project", agent.BUILDING])):
            os.makedirs(os.path.join(jobs, jid, "workspace"))
            for m in marks:
                with open(os.path.join(jobs, jid, m), "w") as f:
                    f.write("alpha")
        os.makedirs(os.path.join(jobs, "j_old", "workspace"))
        long_ago = time.time() - 3 * 86400
        os.utime(os.path.join(jobs, "j_old"), (long_ago, long_ago))
        os.makedirs(os.path.join(jobs, "j_new"))
        self.me.jobs = {"j_running": object()}
        self.run_job()
        self.assertEqual(sorted(os.listdir(jobs)), ["j_1", "j_kept", "j_new", "j_running"])

    def test_a_failure_is_kept_for_a_look_and_replaces_the_one_before(self):
        ws = self.run_job("j_1")
        job = self.job("j_1")
        self.me.finish_workspace(job, ws, {}, "failed")
        jobdir = os.path.dirname(ws)
        self.assertFalse(os.path.exists(os.path.join(jobdir, agent.BUILDING)))
        ws2 = self.run_job("j_2")
        self.assertTrue(os.path.isdir(jobdir), "a kept failure is not swept by the next job")
        self.me.finish_workspace(self.job("j_2"), ws2, {}, "failed")
        self.assertEqual(os.listdir(os.path.join(self.data, "jobs")), ["j_2"])

    def test_a_link_left_at_the_marker_is_not_written_through(self):
        ws = self.run_job("j_1")
        jobdir = os.path.dirname(ws)
        victim = os.path.join(self.top, "victim")
        with open(victim, "w") as f:
            f.write("mine")
        os.unlink(os.path.join(jobdir, "project"))
        os.symlink(victim, os.path.join(jobdir, "project"))
        self.me.finish_workspace(self.job("j_1"), ws, {}, "failed")
        with open(victim) as f:
            self.assertEqual(f.read(), "mine")
        with open(os.path.join(jobdir, "project")) as f:
            self.assertEqual(f.read(), "alpha")
        self.assertFalse(os.path.islink(os.path.join(jobdir, "project")))


class Fetch(unittest.TestCase):
    """controller.fetch: to a file beside itself, nothing left when it fails."""
    def setUp(self):
        self.top = tempfile.mkdtemp(prefix="fetch-")
        self.addCleanup(shutil.rmtree, self.top, True)
        self.dest = os.path.join(self.top, "file")

    def ctl(self, status, body=b"", fail=False):
        me = types.SimpleNamespace()

        def fetch_into(path, f, timeout=600):
            if status != 200:
                return status, ""
            out = f() if callable(f) else f
            try:
                out.write(body[:3] if fail else body)
            finally:
                out.close()
            return (0, "cut") if fail else (200, "sha256:x")
        me.fetch_into = fetch_into
        return types.MethodType(agent.Controller.fetch, me)

    def test_a_whole_body_lands_at_its_name(self):
        self.assertEqual(self.ctl(200, b"hello")("x", self.dest), (200, "sha256:x"))
        with open(self.dest, "rb") as f:
            self.assertEqual(f.read(), b"hello")
        self.assertEqual(os.listdir(self.top), ["file"])

    def test_one_that_stops_short_leaves_no_part(self):
        self.assertEqual(self.ctl(200, b"hello", fail=True)("x", self.dest), (0, "cut"))
        self.assertEqual(os.listdir(self.top), [])

    def test_a_refusal_writes_nothing(self):
        self.assertEqual(self.ctl(404)("x", self.dest), (404, ""))
        self.assertEqual(os.listdir(self.top), [])


if __name__ == "__main__":
    unittest.main()
