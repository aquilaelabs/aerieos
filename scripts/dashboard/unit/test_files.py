"""The file explorer (R224): the controller's fileexplorer.py talking to the
agent's files.py over the screen relay's port, as they do on a node. The
roots read from a census; a listing, a read and a ranged read, an upload,
a folder made, a rename, a delete into the trash; and the refusals: a path
out of its root, a link out of it, the system's folders as a root, a
request not signed by this controller, and anyone but an administrator.

The node holds a request to its own roots, by name, as its last census
said them: the list the controller's page is built from, made on the node
from the same census. Any other folder is refused there whatever was
signed, a link left at an upload's working name is not written through,
and a machine whose console turned root asks off answers no file request."""
import json
import os
import socket
import sys
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import agentpkg      # noqa: E402
import fileexplorer  # noqa: E402

TOKEN = "bbn_" + "t" * 40


class Files(unittest.TestCase):
    def setUp(self):
        self.agent = agentpkg.load("files")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pool = os.path.join(self.tmp.name, "mnt", "fast")
        os.makedirs(os.path.join(self.pool, "media", "films"))
        with open(os.path.join(self.pool, "media", "a.txt"), "w") as f:
            f.write("hello files")
        os.makedirs(os.path.join(self.tmp.name, "outside"))
        with open(os.path.join(self.tmp.name, "outside", "secret"), "w") as f:
            f.write("not yours")
        os.symlink(os.path.join(self.tmp.name, "outside"), os.path.join(self.pool, "out"))
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(8)
        self.addCleanup(srv.close)
        key = self.agent.screen_key(TOKEN)
        self.key = key

        def loop():
            while True:
                try:
                    conn, _ = srv.accept()
                except OSError:
                    return
                threading.Thread(target=self.agent.ScreenRelay._one, args=(conn, [key], lambda: {}), daemon=True).start()
        threading.Thread(target=loop, daemon=True).start()
        port = srv.getsockname()[1]
        self.node = {"id": "n_1", "name": "nas", "kind": "agent", "state": "online", "live": True,
                     "reported": {"pools": [{"name": "fast", "mount": self.pool}], "files": {"port": port},
                                  # A certificate reported, as every node's relay has one: the
                                  # dial itself is plain here, with no connect function set.
                                  "relay": {"tls": "sha256:" + "0" * 64},
                                  "shares": [{"name": "media", "path": os.path.join(self.pool, "media")}]}}
        # The node's own list, from the census it sent.
        self.files = self.agent.module("files")
        self.files.note_roots(self.node["reported"])
        self.root_off = False
        self.files.console_said = lambda: {"root_off": True} if self.root_off else {}
        self.audits = []
        fileexplorer.configure(node=lambda nid: self.node if nid == "n_1" else None, host=lambda nid: "127.0.0.1",
                               key=lambda nid: self.key, audit=lambda *a: self.audits.append(a))

    def act(self, op, **kw):
        return fileexplorer.act("user:ann", True, "n_1", self.pool, op, **kw)

    def test_a_node_whose_relay_has_no_certificate_is_opened_nothing(self):
        # Nothing is opened unencrypted: a node with no certificate yet is
        # refused before anything is dialed, in one sentence.
        self.node["reported"]["relay"] = {}
        tg = fileexplorer._target(True, "n_1", self.pool)
        self.assertEqual(tg, {"error": "nas's relay has no certificate yet, so no file is opened there"})

    def test_the_roots_come_from_the_census(self):
        got = fileexplorer.roots(self.node)
        self.assertEqual([r["kind"] for r in got], ["pool", "share"])
        self.node["reported"]["mounts"] = [{"path": "/workspace", "mounted": True}, {"path": "/mnt/gone", "mounted": False}]
        self.node["reported"]["ext_mounts"] = [{"name": "usb", "mounted": True}]
        self.assertEqual([r["path"] for r in fileexplorer.roots(self.node)][2:], ["/workspace", "/mnt/other/usb"])
        self.assertEqual(got[0]["path"], self.pool)

    def test_a_folder_is_listed_and_a_file_read(self):
        got, status = self.act("list", path="media")
        self.assertEqual(status, 200, got)
        names = {e["name"]: e for e in got["entries"]}
        self.assertEqual(names["films"]["kind"], "dir")
        self.assertEqual(names["a.txt"]["size"], 11)
        tg = fileexplorer._target(True, "n_1", self.pool)
        for start, want in ((0, b"hello files"), (6, b"files")):
            up = fileexplorer.open_request(tg, {"op": "read", "root": self.pool, "path": "media/a.txt", "from": start})
            status, hdr, rest = fileexplorer.read_head(up)
            while len(rest) < int(hdr["content-length"]):
                rest += up.recv(4096)
            up.close()
            self.assertEqual((status, rest, hdr["x-size"]), (200, want, "11"))

    def test_an_upload_a_folder_a_rename_and_a_delete(self):
        tg = fileexplorer._target(True, "n_1", self.pool)
        body = os.urandom(3 << 20)
        up = fileexplorer.open_request(tg, {"op": "write", "root": self.pool, "path": "media", "name": "big.bin"}, method="PUT", length=len(body))
        up.sendall(body)
        status, hdr, rest = fileexplorer.read_head(up)
        self.assertEqual(status, 200, fileexplorer.read_json(up, hdr, rest))
        up.close()
        with open(os.path.join(self.pool, "media", "big.bin"), "rb") as f:
            self.assertEqual(f.read(), body)
        self.assertEqual(self.act("mkdir", path="media", name="new")[1], 200)
        self.assertEqual(self.act("rename", path="media/a.txt", dest="media/new/b.txt")[1], 200)
        self.assertTrue(os.path.isfile(os.path.join(self.pool, "media", "new", "b.txt")))
        self.assertEqual(self.act("rename", path="media/new", dest="media/new/inside")[1], 400, "not inside itself")
        got, status = self.act("delete", path="media/new")
        self.assertEqual(status, 200, got)
        self.assertFalse(os.path.exists(os.path.join(self.pool, "media", "new")))
        trashed = os.path.join(self.pool, got["trash"])
        self.assertTrue(os.path.isfile(os.path.join(trashed, "b.txt")), "kept in the trash")
        with open(trashed + ".aerieos-from") as f:
            self.assertEqual(json.load(f)["from"], "media/new")
        self.assertEqual([a[1] for a in self.audits], ["files-mkdir", "files-rename", "files-delete"])

    def test_nothing_leaves_its_root(self):
        for path in ("../outside", "media/../../outside", "out", "out/secret"):
            got, status = self.act("list", path=path)
            self.assertEqual(status, 403, (path, got))
        got, status = self.act("rename", path="media/a.txt", dest="../a.txt")
        self.assertEqual(status, 403)
        got, status = self.act("delete", path="")
        self.assertEqual(status, 403, "the root itself")
        # The link itself, not where it points, goes to the trash.
        self.assertEqual(self.act("delete", path="out")[1], 200)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp.name, "outside", "secret")))

    def test_a_root_must_be_one_of_the_nodes_and_never_the_systems(self):
        got, status = fileexplorer.act("user:ann", True, "n_1", "/etc", "list")
        self.assertIn("not one of", got["error"])
        # A census that named a system folder as a pool: the node refuses it still.
        self.node["reported"]["pools"].append({"name": "sys", "mount": "/etc"})
        self.files.note_roots(self.node["reported"])
        got, status = fileexplorer.act("user:ann", True, "n_1", "/etc", "list")
        self.assertEqual(status, 403, got)
        self.assertIn("not a folder the file explorer reaches", got["error"])
        for root in ("/", "/usr/lib", "/var/lib", "/proc"):
            self.assertEqual(self.files.root_ok(root), "", root)

    def test_the_node_holds_a_request_to_its_own_roots_by_name(self):
        """A folder that is no system folder and no root of this machine's:
        signed by its controller all the same, and refused on the node."""
        elsewhere = os.path.join(self.tmp.name, "home", "someone")
        os.makedirs(elsewhere)
        for root in (elsewhere, self.tmp.name, "/home", "/opt", "/srv", "/tmp", os.path.join(self.pool, "media", "films"), self.pool + "/../fast"):
            self.assertEqual(self.files.root_ok(root), "", root)
            tg = {"node": self.node, "host": "127.0.0.1", "port": self.node["reported"]["files"]["port"], "key": self.key, "pin": "", "once": False}
            up = fileexplorer.open_request(tg, {"op": "list", "root": root, "path": ""})
            status, _hdr, rest = fileexplorer.read_head(up)
            up.close()
            self.assertEqual(status, 403, (root, rest))
        # Its own, by the names its census gave: a pool and a share inside it.
        self.assertEqual(self.files.root_ok(self.pool), os.path.realpath(self.pool))
        self.assertEqual(self.files.root_ok(self.pool + "/"), os.path.realpath(self.pool))
        self.assertTrue(self.files.root_ok(os.path.join(self.pool, "media")))
        # Before a first census there is no root at all.
        self.files.note_roots({})
        self.assertEqual(self.files.root_ok(self.pool), "")

    def test_the_node_s_roots_are_the_controller_s_list(self):
        census = {"os_stick": {"projects": "/mnt/user/projects"},
                  "pools": [{"name": "fast", "mount": "/mnt/fast"}, {"name": "none"}, "junk"],
                  "array": {"mount": "/mnt/array", "mounted": True},
                  "adopted": {"merged": {"/mnt/user": True, "/mnt/user0": False},
                              "mounts": [{"where": "/mnt/disk1", "mounted": True, "ro": True}, {"where": "/mnt/disk2", "mounted": False}]},
                  "shares": [{"name": "media", "path": "/mnt/fast/media/"}, {"name": "bad", "path": "relative"}, {"name": "up", "path": "/mnt/../etc"}],
                  "mounts": [{"path": "/workspace", "mounted": True}, {"path": "/mnt/gone", "mounted": False},
                             {"path": "/mnt/stale", "mounted": True, "stale": True}, {"path": "/mnt/fast", "mounted": True}],
                  "ext_mounts": [{"name": "usb", "mounted": True}, {"name": "off", "mounted": False}]}
        for rep in (census, {}, {"array": {"mount": "/mnt/array", "mounted": False}}, {"pools": None, "shares": None}):
            self.assertEqual(self.files.roots_of(rep), [r["path"] for r in fileexplorer.roots({"reported": rep})], rep)
        self.assertEqual(self.files.roots_of(census), ["/mnt/user/projects", "/mnt/fast", "/mnt/array", "/mnt/user", "/mnt/disk1",
                                                       "/mnt/fast/media", "/workspace", "/mnt/other/usb"])

    def test_a_link_at_an_upload_s_working_name_is_not_written_through(self):
        target = os.path.join(self.tmp.name, "outside", "secret")
        os.symlink(target, os.path.join(self.pool, "media", ".new.txt.aerieos-part"))
        tg = fileexplorer._target(True, "n_1", self.pool)
        up = fileexplorer.open_request(tg, {"op": "write", "root": self.pool, "path": "media", "name": "new.txt"}, length=7)
        up.sendall(b"planted")
        status, _hdr, _rest = fileexplorer.read_head(up)
        up.close()
        self.assertEqual(status, 200)
        with open(target) as f:
            self.assertEqual(f.read(), "not yours")
        with open(os.path.join(self.pool, "media", "new.txt")) as f:
            self.assertEqual(f.read(), "planted")

    def test_root_asks_off_at_the_console_closes_it(self):
        self.root_off = True
        for op, kw in (("list", {"path": "media"}), ("mkdir", {"path": "media", "name": "x"}), ("delete", {"path": "media/a.txt"})):
            got, status = self.act(op, **kw)
            self.assertEqual(status, 403, (op, got))
            self.assertEqual(got["error"], "root asks are off at this machine's console, and its files are root's to read")
        self.assertTrue(os.path.isfile(os.path.join(self.pool, "media", "a.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.pool, "media", "x")))
        self.root_off = False
        self.assertEqual(self.act("list", path="media")[1], 200)

    def test_a_node_that_reports_root_asks_off_is_asked_nothing(self):
        # Its census says so: the controller refuses before it dials, in the
        # one sentence the Files page draws as a thing switched off.
        self.node["reported"]["root_off"] = True
        tg = fileexplorer._target(True, "n_1", self.pool)
        self.assertEqual(tg, {"error": "nas has root asks switched off at its own console, so its files are not read from here"})
        self.assertEqual(fileexplorer.off_said(self.node), tg["error"])

    def test_only_this_controller_and_only_an_administrator(self):
        got, status = fileexplorer.act("user:bob", False, "n_1", self.pool, "list")
        self.assertIn("administrator", got["error"])
        self.key = "f" * 64
        got, status = self.act("list")
        self.assertEqual(status, 403)
        self.assertIn("not signed", got["error"])


if __name__ == "__main__":
    unittest.main()
