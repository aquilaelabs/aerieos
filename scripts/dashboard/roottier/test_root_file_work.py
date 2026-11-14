"""The root agent's file work in an account's folder, as root for real
(R240 steps 1 and 2; the audit of 13 Nov).

Each test plants what a job or a session could: a link, at the name root is
about to open, to a file that is root's alone or into a folder only root
makes files in. Root acting as the account is refused there as the account
would be, and what is root's is as it was. The first class shows the hazard
itself, so the rest is known to be able to see it."""
import os
import unittest
from unittest import mock

import world

AGENT = world.agent("root_file_work")
base = AGENT.module("base")
NAME, UID, GID = world.account()
WHO = (UID, GID)


def planted(folder, name, target):
    """A link the account left at `name` in its own folder."""
    path = os.path.join(folder, name)
    os.symlink(target, path)
    os.lchown(path, UID, GID)
    return path


class TheHazard(unittest.TestCase):
    def test_root_by_itself_follows_the_link(self):
        # What every site did before it worked as the account: this is why
        # the tests below mean something on this machine.
        w = world.World(self)
        mine = w.folder("account", WHO)
        with open(planted(mine, "report.txt", w.secret), "w") as f:
            f.write("written through the link\n")
        self.assertIn("root's own file was written", w.intact())


class Identity(unittest.TestCase):
    def test_this_machine_holds_file_work_as_an_account(self):
        ok, why = base.fs_probe(WHO)
        self.assertIs(ok, True, why)

    def test_inside_it_root_is_the_account_and_root_again_after(self):
        w = world.World(self)
        mine = w.folder("account", WHO)
        to_secret = planted(mine, "report.txt", w.secret)
        into_vault = planted(mine, "new.txt", os.path.join(w.vault, "planted"))
        with base.fs_holds(WHO):
            for path, mode in ((to_secret, "r"), (to_secret, "w"), (into_vault, "w")):
                with self.assertRaises(PermissionError, msg=f"{path} ({mode})"):
                    with open(path, mode):
                        pass
            with open(os.path.join(mine, "made"), "w") as f:
                f.write("x")
            self.assertEqual(os.getgroups(), [], "none of root's groups")
            with base.as_root():
                with open(w.secret) as f:
                    self.assertEqual(f.read(), world.SECRET, "root again for a file of the agent's own")
            with self.assertRaises(PermissionError):
                open(w.secret).close()
        st = os.lstat(os.path.join(mine, "made"))
        self.assertEqual((st.st_uid, st.st_gid), WHO, "a file made there is the account's, with no chown")
        with open(w.secret) as f:
            self.assertEqual(f.read(), world.SECRET)
        self.assertEqual(w.intact(), "")


class Downloads(unittest.TestCase):
    """controller.fetch writes DEST.part and moves it into place: the sync's
    files, a job's inputs and an instance's shipped data all arrive by it,
    each inside base.fs_holds for the folder's account."""

    def setUp(self):
        self.w = world.World(self)
        self.mine = self.w.folder("account", WHO)
        self.served = world.Served(self, b"the download\n")
        self.ctl = AGENT.Controller(self.served.url, "bbn_test")

    def test_a_link_at_the_part_file_reaches_nothing_of_roots(self):
        dest = os.path.join(self.mine, "app.apk")
        planted(self.mine, "app.apk.part", self.w.secret)
        with base.fs_holds(WHO):
            code, why = self.ctl.fetch("file?job=j1&path=app.apk", dest)
        self.assertEqual(code, 0, "refused, as the account would be")
        self.assertIn("Permission denied", why)
        self.assertEqual(self.w.intact(), "")
        self.assertFalse(os.path.exists(dest))

    def test_a_link_into_roots_folder_makes_nothing_there(self):
        dest = os.path.join(self.mine, "cron")
        planted(self.mine, "cron.part", os.path.join(self.w.vault, "planted"))
        with base.fs_holds(WHO):
            code, _why = self.ctl.fetch("file?job=j1&path=cron", dest)
        self.assertEqual(code, 0)
        self.assertEqual(self.w.intact(), "")

    def test_a_plain_download_is_the_accounts_own_file(self):
        dest = os.path.join(self.mine, "app.apk")
        with base.fs_holds(WHO):
            code, _ = self.ctl.fetch("file?job=j1&path=app.apk", dest)
        self.assertEqual(code, 200)
        with open(dest, "rb") as f:
            self.assertEqual(f.read(), b"the download\n")
        st = os.lstat(dest)
        self.assertEqual((st.st_uid, st.st_gid), WHO)

    def test_an_instances_shipped_data_arrives_as_the_job_account(self):
        # work.ship_step: the path is held to the job's compose folder, and
        # the download into it is the job account's.
        a = object.__new__(AGENT.Agent)
        a.ctl, a.state = self.ctl, {"user": NAME}
        said = []
        job = type("Job", (), {"say": lambda self, t: said.append(t)})()
        cdir = self.w.folder("compose-app", WHO)
        planted(cdir, "data.tar.part", self.w.secret)
        got = a.ship_step(job, {"fetch": "devdata?instance=app", "dest": "{cdir}/data.tar"}, cdir)
        self.assertEqual(got, ("failed", 75), said)
        self.assertEqual(self.w.intact(), "")
        os.remove(os.path.join(cdir, "data.tar.part"))
        got = a.ship_step(job, {"fetch": "devdata?instance=app", "dest": "{cdir}/data.tar"}, cdir)
        self.assertEqual(got, ("succeeded", 0), said)
        st = os.lstat(os.path.join(cdir, "data.tar"))
        self.assertEqual((st.st_uid, st.st_gid), WHO)
        # ...and a path a link leads out of the folder by is refused before anything is asked.
        planted(cdir, "out.tar", self.w.secret)
        asked = len(self.served.gets)
        self.assertEqual(a.ship_step(job, {"fetch": "devdata?instance=app", "dest": "{cdir}/out.tar"}, cdir), ("failed", 78))
        self.assertEqual(len(self.served.gets), asked)
        self.assertEqual(self.w.intact(), "")


class ComposeFiles(unittest.TestCase):
    def test_a_compose_file_is_written_as_the_job_account(self):
        # work.compose writes the controller's compose file and env into the
        # job account's folder: a link left at docker-compose.yml was
        # written through as root.
        w = world.World(self)
        data = w.folder("data")
        cdir = w.folder("data/compose/app", WHO)
        planted(cdir, "docker-compose.yml", w.secret)
        a = object.__new__(AGENT.Agent)
        a.state = {"user": NAME, "stores": {"data": data}}
        said = []
        job = type("Job", (), {"say": lambda self, t: said.append(t), "outputs": []})()
        work = AGENT.module("work")
        with mock.patch.object(work.shutil, "which", lambda name: "/bin/true"), \
                mock.patch.object(AGENT.Agent, "docker_by_root", lambda self: False):
            with self.assertRaises(PermissionError):
                a.compose(job, {"name": "app", "files": {"docker-compose.yml": "services: {}\n"}})
            self.assertEqual(w.intact(), "")
            os.remove(os.path.join(cdir, "docker-compose.yml"))
            got = a.compose(job, {"name": "app", "files": {"docker-compose.yml": "services: {}\n", ".env": "A=1\n"}})
        self.assertEqual(got, ("succeeded", 0), said)
        for name in ("docker-compose.yml",):
            st = os.lstat(os.path.join(cdir, name))
            self.assertEqual((st.st_uid, st.st_gid), WHO, name)
        self.assertEqual(w.intact(), "")


class Folders(unittest.TestCase):
    def test_a_folder_is_handed_over_by_itself_and_never_through_a_link(self):
        w = world.World(self)
        store = w.folder("store")
        a = object.__new__(AGENT.Agent)
        who = {"user": UID, "group": GID}
        # The account can leave a link where its folder was: root's folder stays root's.
        os.symlink(w.vault, os.path.join(store, "artifacts"))
        a.own_dir(os.path.join(store, "artifacts"), who)
        self.assertEqual(os.stat(w.vault).st_uid, 0, "a link left at the folder's name is not followed")
        a.own_dir(os.path.join(store, "cache"), who)
        st = os.stat(os.path.join(store, "cache"))
        self.assertEqual((st.st_uid, st.st_gid), WHO)
        self.assertEqual(w.intact(), "")


class Artifacts(unittest.TestCase):
    def test_what_a_job_names_is_found_and_read_as_its_account(self):
        # workspace.deliver: root opened whatever a glob in the job's
        # workspace named, so a link there to a file only root reads went
        # up as the space's artifact.
        w = world.World(self)
        served = world.Served(self)
        ws = w.folder("ws", WHO)
        dist = w.folder("ws/dist", WHO)
        with open(os.path.join(dist, "app.apk"), "w") as f:
            f.write("the app\n")
        os.chown(os.path.join(dist, "app.apk"), UID, GID)
        planted(dist, "keys.apk", w.secret)
        # ...and one behind a folder the account may not enter: not even found.
        closed = w.folder("closed", mode=0o700)
        with open(os.path.join(closed, "inner.apk"), "w") as f:
            f.write("root's too\n")
        planted(dist, "inner.apk", os.path.join(closed, "inner.apk"))
        a = object.__new__(AGENT.Agent)
        a.ctl, a.state = AGENT.Controller(served.url, "bbn_test"), {"user": NAME}
        said = []
        job = type("Job", (), {"say": lambda self, t: said.append(t), "outputs": [], "job": {"id": "j1"}})()
        a.deliver(job, ws, ["dist/*.apk"])
        self.assertEqual([body for _path, body in served.posts], [b"the app\n"], said)
        # The link to root's file was found (its name is the account's to
        # see) and refused at the open: not a byte of it went up. (The
        # request it had begun is cut short, which the stand-in keeps apart
        # whenever it notices; nothing here waits for that.)
        self.assertEqual([o["path"] for o in job.outputs], ["dist/app.apk"])
        self.assertTrue(any("could not deliver dist/keys.apk" in s for s in said), said)
        self.assertFalse(any("inner.apk" in s for s in said), said)
        self.assertEqual(w.intact(), "")


if __name__ == "__main__":
    unittest.main()
