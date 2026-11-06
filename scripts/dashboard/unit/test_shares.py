"""SMB and NFS shares on the controller's own machine (R162 step 1): the
agent reads its two files whole into the census and writes them whole from
the storage-share job, each argument held to its shape, each user to the
machine's and the path to a folder under a pool; the controller keeps the
census's shares to their shape and queues the job for the own machine alone."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import agentpkg  # noqa: E402

SMB = """# Written by AerieOS
[media]
    path = /mnt/tank/media
    browseable = yes
    read only = no
    guest ok = yes
    force user = nobody

[docs]
    path = /mnt/tank/docs
    read only = yes
    guest ok = no
    valid users = bbu-0a1b2c3d ada
"""
NFS = """# Written by AerieOS
/mnt/tank/media 192.168.1.0/24(rw,sync,no_subtree_check,root_squash) nas2(ro,sync,no_subtree_check,root_squash)
/mnt/tank/backup *(ro,sync,no_subtree_check,root_squash)
"""


class Job:
    def __init__(self):
        self.log = []

    def say(self, s):
        self.log.append(s)

    def step(self, s):
        self.log.append(f"[{s}]")

    def text(self):
        return "".join(self.log)


class TheAgent(unittest.TestCase):
    def setUp(self):
        self.agent = agentpkg.load("aerieos_agent_shares")
        self.sm = sys.modules[self.agent.Agent.__module__.rsplit(".", 1)[0] + ".shares"]
        self.d = tempfile.mkdtemp()
        self.smb = os.path.join(self.d, "samba", "builderbot.conf")
        self.nfs = os.path.join(self.d, "exports.d", "builderbot.exports")
        os.makedirs(os.path.dirname(self.smb)); os.makedirs(os.path.dirname(self.nfs))
        open(self.smb, "w").write(SMB); open(self.nfs, "w").write(NFS)
        self.internal = os.path.join(self.d, "internal.json")
        self.env = {"BB_SMB_FILE": self.smb, "BB_NFS_FILE": self.nfs, "BB_SMB_MAIN": os.path.join(self.d, "smb.conf"), "BB_SHARES_INTERNAL": self.internal}
        sm = self.sm
        ran = self.ran = []

        class A(sm.SharesMixin):
            def _sh(self, job, argv, timeout=0, **kw):
                ran.append(argv)
                return 0

            def hello_again(self, why):
                self.said = why
        self.A = A

    def test_the_census_reads_both_files_as_one_list(self):
        with mock.patch.dict(os.environ, self.env):
            got = self.sm.shares_now()
        by = {s["name"]: s for s in got}
        self.assertEqual(set(by), {"media", "docs", "backup"})
        self.assertEqual(by["media"]["smb"], {"on": True, "guest": True, "ro": False, "tm": False, "users": [], "readers": []})
        self.assertEqual(by["media"]["nfs"], {"on": True, "ro": True, "clients": ["192.168.1.0/24", "nas2"]})
        self.assertEqual(by["docs"]["smb"]["users"], ["bbu-0a1b2c3d", "ada"])
        self.assertFalse(by["docs"]["nfs"]["on"])
        self.assertEqual((by["backup"]["smb"]["on"], by["backup"]["nfs"]["clients"]), (False, ["*"]))

    def run_job(self, cfg, users=("ada", "bbu-0a1b2c3d"), folders=("/mnt/tank/media", "/mnt/tank/docs", "/mnt/tank/photos")):
        job = Job()
        import pwd
        real_isdir = os.path.isdir
        with mock.patch.dict(os.environ, self.env), mock.patch.object(self.sm.os, "geteuid", return_value=0), \
             mock.patch.object(self.sm.os.path, "isdir", side_effect=lambda p: p in folders or (not p.startswith("/mnt/") and real_isdir(p))), \
             mock.patch.object(pwd, "getpwnam", side_effect=lambda u: u if u in users else (_ for _ in ()).throw(KeyError(u))), \
             mock.patch.object(self.sm.shutil, "which", side_effect=lambda n: "/usr/bin/" + n if n in ("smbcontrol", "exportfs") else None):
            state, code = self.A()._apply_storage_share(job, cfg)
        return state, code, job.text()

    def test_a_share_set_is_written_whole_and_the_daemons_told(self):
        state, code, text = self.run_job({"share": "set", "name": "photos", "path": "/mnt/tank/photos",
                                          "smb": {"on": True, "guest": False, "ro": False, "users": ["ada"]},
                                          "nfs": {"on": True, "ro": True, "clients": ["192.168.1.0/24"]}})
        self.assertEqual((state, code), ("succeeded", 0), text)
        smb, nfs = open(self.smb).read(), open(self.nfs).read()
        self.assertIn("[photos]\n    path = /mnt/tank/photos", smb)
        self.assertIn("valid users = ada", smb)
        self.assertIn("[media]", smb, "the shares before are kept")
        self.assertIn("/mnt/tank/photos 192.168.1.0/24(ro,sync,no_subtree_check,root_squash)", nfs)
        self.assertEqual([a[0] for a in self.ran], ["/usr/bin/smbcontrol", "/usr/bin/exportfs"])
        state, code, text = self.run_job({"share": "remove", "name": "media"})
        self.assertEqual(state, "succeeded", text)
        self.assertNotIn("[media]", open(self.smb).read())
        self.assertNotIn("/mnt/tank/media", open(self.nfs).read())

    def test_a_share_with_a_space_in_its_name_is_served_and_read_back(self):
        # R163 step 13: another NAS names one TV Shows; a doubled space, a
        # quote or a newline is still refused.
        state, code, text = self.run_job({"share": "set", "name": "TV Shows", "path": "/mnt/tank/TV Shows",
                                          "smb": {"on": True, "guest": True, "ro": False, "users": []},
                                          "nfs": {"on": True, "ro": False, "clients": ["*"]}},
                                         folders=("/mnt/tank/media", "/mnt/tank/docs", "/mnt/tank/TV Shows"))
        self.assertEqual((state, code), ("succeeded", 0), text)
        self.assertIn("[TV Shows]\n    path = /mnt/tank/TV Shows\n", open(self.smb).read())
        self.assertIn('"/mnt/tank/TV Shows" *(rw,', open(self.nfs).read())
        with mock.patch.dict(os.environ, self.env):
            got = {x["name"]: x for x in self.sm.shares_now()}
        self.assertEqual((got["TV Shows"]["path"], got["TV Shows"]["nfs"]["on"]), ("/mnt/tank/TV Shows", True))
        for name, path in (("TV  Shows", "/mnt/tank/TV Shows"), ("TV Shows ", "/mnt/tank/TV Shows"),
                           ("TV", "/mnt/tank/TV\nShows"), ("TV", '/mnt/tank/TV"x')):
            state, _c, text = self.run_job({"share": "set", "name": name, "path": path, "smb": {"on": True, "guest": True}},
                                           folders=())
            self.assertEqual(state, "failed", (name, path, text))
        import nodes
        self.assertIsNotNone(nodes._share_cfg({"smb": True}, {"share": "set", "name": "TV Shows", "path": "/mnt/user/TV Shows",
                                                              "smb": {"on": True, "guest": True}})[0])
        self.assertIsNone(nodes._share_cfg({"smb": True}, {"share": "set", "name": "TV  Shows", "path": "/mnt/user/x"})[0])

    def test_the_merged_trees_top_folders_are_listed(self):
        adopt = agentpkg.load("aerieos_agent_shares_folders").module("adopt")
        d = tempfile.mkdtemp()
        for n in ("TV Shows", "appdata", ".Recycle.Bin", "bad\nname"):
            os.makedirs(os.path.join(d, n))
        open(os.path.join(d, "file.txt"), "w").close()
        self.assertEqual(adopt.top_folders(d), ["TV Shows", "appdata"])
        self.assertEqual(adopt.top_folders(os.path.join(d, "none")), [])

    def test_a_time_machine_target_is_said_to_the_finder_and_read_back(self):
        smb, _nfs = self.sm.render([{"name": "tm", "path": "/mnt/tank/tm", "smb": {"on": True, "guest": False, "ro": False, "tm": True, "users": ["bbu-0a1b2c3d"]},
                                     "nfs": {"on": False, "ro": False, "clients": []}}])
        self.assertIn("vfs objects = catia fruit streams_xattr", smb)
        self.assertIn("fruit:time machine = yes", smb)
        open(self.smb, "w").write(smb)
        with mock.patch.dict(os.environ, self.env):
            got = self.sm.shares_now()
        self.assertEqual((got[0]["name"], got[0]["smb"]["tm"]), ("tm", True))
        smb, _nfs = self.sm.render([{"name": "plain", "path": "/mnt/tank/p", "smb": {"on": True, "guest": True, "ro": False, "tm": False, "users": [], "readers": []},
                                     "nfs": {"on": False, "ro": False, "clients": []}}])
        self.assertNotIn("time machine", smb)

    def test_the_accounts_smb_passwords_are_imported_once_per_change_and_the_gone_removed(self):
        sm = self.sm
        a = self.A(); a.state = {}
        runs = []
        users_file = os.path.join(self.d, "smbusers")
        fake_pw = {"bbu-0a1b2c3d": mock.Mock(pw_uid=1001)}

        def run(argv, **kw):
            runs.append(argv)
            if argv[0] == "useradd":
                fake_pw[argv[-1]] = mock.Mock(pw_uid=1002)
            if argv[:2] == ["/usr/bin/pdbedit", "-i"]:
                runs.append(("file", open(users_file).read()))
            return mock.Mock(returncode=0, stderr="", stdout="")

        def getpwnam(n):
            if n in fake_pw:
                return fake_pw[n]
            raise KeyError(n)
        rows = [{"user": "bbu-0a1b2c3d", "nt": "8846f7eaee8fb117ad06bdd830b7586c"}, {"user": "bbu-deadbeef", "nt": "31D6CFE0D16AE931B73C59D7E0C089C0"},
                {"user": "root", "nt": "31D6CFE0D16AE931B73C59D7E0C089C0"}, {"user": "bbu-00000000", "nt": "junk"}]
        with mock.patch.dict(os.environ, {"BB_SMB_USERS_FILE": users_file}), mock.patch.object(sm.shutil, "which", return_value="/usr/bin/pdbedit"), \
             mock.patch.object(sm.os, "geteuid", return_value=0), mock.patch.object(sm.subprocess, "run", side_effect=run), \
             mock.patch.object(sm, "save_state"), mock.patch("pwd.getpwnam", side_effect=getpwnam), \
             mock.patch.object(self.A, "_out", create=True, return_value="bbu-0a1b2c3d:1001:\nbbu-feedface:1003:\nnobody:65534:\n"):
            a.smb_users_want(rows)
            n = len(runs)
            a.smb_users_want(rows)
            self.assertEqual(len(runs), n, "the same set again does nothing")
        # The missing user made, the gone one removed, the file imported with both hashes upper-case, and removed after.
        self.assertEqual([r for r in runs if r[0] == "useradd"][0][-1], "bbu-deadbeef")
        self.assertIn(["/usr/bin/pdbedit", "-x", "-u", "bbu-feedface"], runs)
        text = [r[1] for r in runs if isinstance(r, tuple)][0]
        # X and a real time: LCT-00000000 tells Samba the password must change
        # first, which no share client can do (B672).
        self.assertRegex(text, r"\Abbu-0a1b2c3d:1001:X{32}:8846F7EAEE8FB117AD06BDD830B7586C:\[UX {9}\]:LCT-[0-9A-F]{8}:\n")
        self.assertRegex(text, r"\nbbu-deadbeef:1002:X{32}:31D6CFE0D16AE931B73C59D7E0C089C0:\[UX {9}\]:LCT-[0-9A-F]{8}:\n\Z")
        self.assertNotIn("LCT-00000000", text)
        self.assertFalse(os.path.exists(users_file))
        self.assertTrue(a.state.get("smb_users_sig"))

    def test_an_accounts_user_the_share_names_is_made_here_when_missing(self):
        # B633 (the VM walk, 2 Nov): a share adopted from another system
        # named a person who had never signed in, so their bbu- user was not
        # here yet and the whole share was refused; it is made at share time.
        made = []

        def run(argv, **kw):
            made.append(argv)
            return mock.Mock(returncode=0, stderr="", stdout="")
        with mock.patch.object(self.sm.subprocess, "run", side_effect=run):
            state, code, text = self.run_job({"share": "set", "name": "photos", "path": "/mnt/tank/photos",
                                              "smb": {"on": True, "users": ["bbu-0a1b2c3d", "bbu-deadbeef"]}})
        self.assertEqual((state, code), ("succeeded", 0), text)
        self.assertEqual([a[-1] for a in made if a[0] == "useradd"], ["bbu-deadbeef"], "the missing one made, the one here left")
        self.assertIn("-G", made[0]); self.assertIn("bbu", made[0])
        self.assertIn("bbu-deadbeef made here for the share: they reach it over SMB once their password is set on Profile", text)
        self.assertIn("valid users = bbu-0a1b2c3d bbu-deadbeef", open(self.smb).read())
        # One useradd cannot make: said, nothing written.
        before = open(self.smb).read()
        with mock.patch.object(self.sm.subprocess, "run", return_value=mock.Mock(returncode=1, stderr="useradd: UID range exhausted", stdout="")):
            state, code, text = self.run_job({"share": "set", "name": "more", "path": "/mnt/tank/photos", "smb": {"on": True, "users": ["bbu-feedface"]}})
        self.assertEqual(state, "failed")
        self.assertIn("could not be made: useradd: UID range exhausted", text)
        self.assertEqual(open(self.smb).read(), before)

    def test_samba_is_told_of_the_shares_file_and_the_names_map_once(self):
        # B672: the image's smb.conf includes neither.
        main = os.path.join(self.d, "smb.conf")
        with open(main, "w") as f:
            f.write("[global]\n   workgroup = WORKGROUP\n\n[printers]\n   path = /x\n")
        with mock.patch.dict(os.environ, {"BB_SMB_MAP": "/m/map", "BB_SMB_FILE": "/s/file"}):
            self.assertTrue(self.sm._samba_hooks(main))
            once = open(main).read()
            self.assertTrue(self.sm._samba_hooks(main))
        self.assertEqual(open(main).read(), once, "a second time writes nothing more")
        lines = once.split("\n")
        self.assertEqual(lines[1], "   username map = /m/map", "the map is [global]'s")
        self.assertEqual(lines[-2], "   include = /s/file", "the include comes last, since it starts sections of its own")

    def test_a_shares_missing_folder_is_made_only_on_a_disk_the_machine_has(self):
        # B672: the Storage page says it is made; never on the root's tmpfs.
        sm = self.sm
        base = os.path.join(self.d, "pool")
        os.makedirs(base)
        with mock.patch.object(sm.os.path, "ismount", lambda p: False):
            self.assertIn("not on a disk", sm._make_folder(os.path.join(base, "media")))
        self.assertFalse(os.path.exists(os.path.join(base, "media")))
        me = mock.Mock(pw_uid=os.getuid()); grp = mock.Mock(gr_gid=os.getgid())
        with mock.patch.object(sm.os.path, "ismount", lambda p: p == base), mock.patch("pwd.getpwnam", return_value=me), mock.patch("grp.getgrnam", return_value=grp):
            self.assertEqual(sm._make_folder(os.path.join(base, "media")), "")
        self.assertEqual(os.stat(os.path.join(base, "media")).st_mode & 0o777, 0o770)

    def test_a_share_with_no_export_is_a_share_samba_never_hears_of(self):
        # The operator, 4 Nov: internal until it is exported.
        state, code, text = self.run_job({"share": "set", "name": "photos", "path": "/mnt/tank/photos", "smb": {"on": False}, "nfs": {"on": False}})
        self.assertEqual((state, code), ("succeeded", 0), text)
        self.assertIn("internal, not exported", text)
        self.assertNotIn("[photos]", open(self.smb).read())
        self.assertNotIn("/mnt/tank/photos", open(self.nfs).read())
        with mock.patch.dict(os.environ, self.env):
            by = {x["name"]: x for x in self.sm.shares_now()}
        self.assertEqual(by["photos"]["path"], "/mnt/tank/photos")
        self.assertFalse(by["photos"]["smb"]["on"] or by["photos"]["nfs"]["on"])
        # Exported later, it is one share, and no longer the internal list's.
        state, _, text = self.run_job({"share": "set", "name": "photos", "path": "/mnt/tank/photos", "smb": {"on": True, "guest": True}})
        self.assertEqual(state, "succeeded", text)
        self.assertIn("[photos]", open(self.smb).read())
        self.assertEqual(json.load(open(self.internal)), [])
        state, _, _ = self.run_job({"share": "remove", "name": "photos"})
        self.assertEqual(state, "succeeded")
        with mock.patch.dict(os.environ, self.env):
            self.assertNotIn("photos", [x["name"] for x in self.sm.shares_now()])

    def test_private_says_each_person_and_secure_lets_everybody_read(self):
        state, _, text = self.run_job({"share": "set", "name": "fam", "path": "/mnt/tank/photos",
                                       "smb": {"on": True, "guest": False, "users": ["ada"], "readers": ["bob"]}}, users=("ada", "bob"))
        self.assertEqual(state, "succeeded", text)
        smb = open(self.smb).read()
        self.assertIn("valid users = ada bob", smb)
        self.assertIn("read list = bob", smb)
        with mock.patch.dict(os.environ, self.env):
            got = {x["name"]: x for x in self.sm.shares_now()}["fam"]["smb"]
        self.assertEqual((got["users"], got["readers"], got["guest"]), (["ada"], ["bob"], False), "read back as it was asked")
        state, _, text = self.run_job({"share": "set", "name": "fam", "path": "/mnt/tank/photos",
                                       "smb": {"on": True, "guest": True, "users": ["ada"]}}, users=("ada", "bob"))
        self.assertEqual(state, "succeeded", text)
        smb = open(self.smb).read()
        self.assertIn("write list = ada", smb)
        with mock.patch.dict(os.environ, self.env):
            got = {x["name"]: x for x in self.sm.shares_now()}["fam"]["smb"]
        self.assertEqual((got["users"], got["guest"]), (["ada"], True))

    def test_what_is_refused_writes_nothing(self):
        before = open(self.smb).read()
        for cfg, why in (({"share": "set", "name": "x", "path": "/home/ada", "smb": {"on": True, "guest": True}}, "under /mnt or /srv"),
                         ({"share": "set", "name": "x", "path": "/mnt/tank/nope", "smb": {"on": True, "guest": True}}, "not on a disk"),
                                                  ({"share": "set", "name": "x", "path": "/mnt/tank/photos", "smb": {"on": True, "users": ["zed"]}}, "not a user this machine has"),
                         ({"share": "set", "name": "x", "path": "/mnt/tank/photos", "smb": {"on": True, "users": []}}, "takes the users"),
                         ({"share": "set", "name": "x", "path": "/mnt/tank/photos", "nfs": {"on": True, "clients": ["bad client"]}}, "not a client"),
                         ({"share": "set", "name": "x", "path": "/mnt/tank/media", "smb": {"on": True, "guest": True}}, "shared already under another name"),
                         ({"share": "remove", "name": "nope"}, "no share called"),
                         ({"share": "set", "name": "bad name!", "path": "/mnt/tank/photos"}, "not a share name")):
            self.ran.clear()
            state, code, text = self.run_job(cfg)
            self.assertEqual(state, "failed", cfg)
            self.assertIn(why, text, cfg)
        self.assertEqual(open(self.smb).read(), before)
        self.assertEqual(self.ran, [])


class TheController(unittest.TestCase):
    def test_the_census_keeps_each_share_to_its_shape(self):
        import nodes
        got = nodes._census({"shares": [{"name": "media", "path": "/mnt/tank/media<b>", "smb": {"on": True, "guest": "yes", "ro": False, "users": ["ada", 7]},
                                         "nfs": {"on": True, "ro": True, "clients": ["192.168.1.0/24"]}}, {"name": "bad  name"}]})
        self.assertEqual(got["shares"], [{"name": "media", "path": "/mnt/tank/mediab", "smb": {"on": True, "guest": False, "ro": False, "tm": False, "users": ["ada"], "readers": []},
                                          "nfs": {"on": True, "ro": True, "clients": ["192.168.1.0/24"]}}])

    def test_the_verb_is_the_own_machines(self):
        import nodes
        nodes.configure(state=tempfile.mkdtemp())
        self.assertEqual(nodes.node_storage_share("user:t", "n_none", {"share": "remove", "name": "x"})["error"], "no such node")


if __name__ == "__main__":
    unittest.main()
