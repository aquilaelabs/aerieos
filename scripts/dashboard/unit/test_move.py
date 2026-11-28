"""Moving a controller to another home (move.py): the bundle
sealed under a token shown once, the nodes' challenges, the restore held to
the version gate and refused under another token, the old home marked
moved, and what the new home answers a node's knock; and the second pass:
the move armed with no life and the bundle packed fresh, a late
node handed its challenge after the move, the landing told both ways under
the move key, the pull's proof, the pieces, and the nodes not yet here."""
import contextlib
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import move     # noqa: E402
import signing  # noqa: E402


def write_json(path, obj, mode=0o644):
    with open(path, "w") as f:
        json.dump(obj, f)


class Move(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.state = self.tmp / "config"
        self.ws = self.tmp / "workspace"
        self.secrets = self.tmp / "secrets"
        self.store = self.tmp / "elsewhere" / "gitrelay"
        for d in (self.state / "logs", self.state / "apps", self.ws / "alpha" / ".git", self.secrets, self.store / "alpha.git"):
            d.mkdir(parents=True)
        (self.state / "users.json").write_text('{"users": {"ann": {}}}')
        (self.state / "logs" / "old.log").write_text("not moved")
        (self.ws / "alpha" / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        (self.secrets / "deploy.env").write_text("DEPLOY=1\n")
        (self.store / "alpha.git" / "HEAD").write_text("bare\n")
        self.configure(self.state, bare=False)

    def configure(self, state, bare, url="https://old.example/"):
        self.audits = []
        move.configure(state=state, workspace=self.ws, secrets_dir=str(self.secrets), write_json_fn=write_json,
                       seal_fn=signing.seal, open_fn=signing.open_with, state_version_fn=lambda: 29, build_version_fn=lambda: "0.9.0",
                       install_key_fn=lambda: b"k" * 32, store_paths_fn=lambda: {"gitrelay": str(self.store), "logs": str(self.tmp / "logs")},
                       page_url_fn=lambda: url, node_ids_fn=lambda: ["n_1", "n_2"], bare_metal_fn=lambda: bare,
                       node_name_fn=lambda nid: {"n_1": "alpha", "n_2": "beta"}.get(nid, nid),
                       audit_fn=lambda who, what, detail: self.audits.append((what, detail)))

    def _land(self, path, token):
        return move.restore(str(path), token, state_dir=self.tmp / "new-config", workspace_dir=self.tmp / "new-ws",
                            secrets_dir=self.tmp / "new-secrets", build_state_version=29, here_bare_metal=False)

    def _pieces(self, path):
        """The bundle's head (its two lines) and its pieces, each with its
        length."""
        raw = Path(path).read_bytes()
        cut = raw.index(b"\n", len(move.HEADER)) + 1
        head, body, out = raw[:cut], raw[cut:], []
        while body:
            n = int.from_bytes(body[:4], "big")
            out.append(body[:4 + n])
            body = body[4 + n:]
        return head, out

    def test_a_bundle_is_sealed_a_piece_at_a_time_and_every_piece_is_held_to_its_place(self):
        # Never whole in memory; here pieces of 4 KiB over a
        # repository of 64 KiB of noise, so a bundle is many pieces.
        (self.ws / "alpha" / "big.bin").write_bytes(os.urandom(64 << 10))
        move.PIECE, was = 4096, move.PIECE
        self.addCleanup(setattr, move, "PIECE", was)
        r = move.prepare("user:ann", "https://new.example", repos=True)
        path = move.bundle_path()
        head, pieces = self._pieces(path)
        self.assertEqual(json.loads(head.split(b"\n")[1])["format"], 2)
        self.assertGreater(len(pieces), 10)
        bad = self.tmp / "bad.aeriemove"
        for why, body in (("a piece dropped", pieces[:3] + pieces[4:]), ("two pieces swapped", [pieces[1], pieces[0]] + pieces[2:]),
                          ("the last piece missing", pieces[:-1]), ("junk after the last", pieces + [b"junk"])):
            bad.write_bytes(head + b"".join(body))
            got = self._land(bad, r["token"])
            self.assertIn("error", got, why)
            self.assertFalse((self.tmp / "new-config" / "users.json").exists(), f"{why}: nothing here changed")
        self.assertIn("not this bundle's move token", self._land(path, "not-the-token").get("error", ""))
        got = self._land(path, r["token"])
        self.assertTrue(got.get("ok"), got)
        self.assertEqual((self.tmp / "new-ws" / "alpha" / "big.bin").read_bytes(), (self.ws / "alpha" / "big.bin").read_bytes())

    def test_a_bundle_is_packed_in_place_and_the_one_before_goes_first(self):
        # A full disk on the old home: the body went to
        # a file beside the bundle and was copied after, and the bundle
        # before stayed until the new one was done, so packing took three
        # times the bundle's room.
        (self.ws / "alpha" / "big.bin").write_bytes(os.urandom(256 << 10))
        r = move.prepare("user:ann", "https://new.example", repos=True)
        first = move.bundle_path()
        seen, real = [], move._pack_into

        def watching(tar, **kw):
            seen.append(sorted(p.name for p in first.parent.iterdir()))
            return real(tar, **kw)
        with mock.patch.object(move, "_pack_into", watching):
            self.assertTrue(move.pack_bundle().get("ok"))
        self.assertEqual(len(seen), 1)
        self.assertNotIn(first.name, seen[0], "the bundle before is gone before the new one is packed")
        self.assertTrue(all(n.endswith(".partial") for n in seen[0]), seen[0])
        now = move.bundle_path()
        self.assertEqual(sorted(p.name for p in now.parent.iterdir()), [now.name], "no body beside it, nothing left over")
        line = now.read_bytes().split(b"\n")[1]
        self.assertEqual(len(move.HEADER) + len(line) + 1, len(move.HEADER) + move.MANIFEST_SLOT)
        self.assertEqual(json.loads(line)["format"], 2, "the slot reads as the manifest")
        self.assertTrue(self._land(now, r["token"]).get("ok"))

    def test_a_full_disk_while_packing_is_said_as_a_sentence(self):
        r = move.prepare("user:ann", "https://new.example", repos=True)
        self.assertTrue(r.get("ok"))

        def full(tar, **kw):
            raise OSError(28, "No space left on device")
        with mock.patch.object(move, "_pack_into", full):
            got = move.pack_bundle()
        self.assertIn("filled up", got.get("error", ""))
        self.assertIn("without the repositories", got["error"])
        self.assertEqual([p for p in (self.state / "move").iterdir() if p.suffix != ".json"], [], "nothing half written is left")

    def test_a_landings_upload_is_read_a_megabyte_at_a_time(self):
        # The bundle part straddles the reader's megabyte edges, and its
        # bytes hold the boundary's start (never the whole: a browser picks
        # one its content does not hold) and line endings.
        blob = (os.urandom((1 << 20) - 7) + b"\r\n--XY" + b"\r\n" * 9 + os.urandom(3 << 20)).replace(b"XYZ", b"XYQ") * 2
        form = (b"--XYZ\r\nContent-Disposition: form-data; name=\"token\"\r\n\r\n tok-1 \r\n"
                b"--XYZ\r\nContent-Disposition: form-data; name=\"bundle\"; filename=\"b.aeriemove\"\r\n"
                b"Content-Type: application/octet-stream\r\n\r\n" + blob + b"\r\n"
                b"--XYZ\r\nContent-Disposition: form-data; name=\"from\"\r\n\r\n\r\n--XYZ--\r\n")
        src, dest = self.tmp / "form", self.tmp / "file"
        src.write_bytes(form)
        fields, got = move.split_form(src, "multipart/form-data; boundary=XYZ", "bundle", dest)
        self.assertEqual(fields, {"token": "tok-1", "from": ""})
        self.assertTrue(got)
        self.assertEqual(dest.read_bytes(), blob)
        src.write_bytes(form[:len(form) // 2])
        with self.assertRaises(ValueError):
            move.split_form(src, "multipart/form-data; boundary=XYZ", "bundle", dest)
        with self.assertRaises(ValueError):
            move.split_form(src, "application/x-www-form-urlencoded", "bundle", dest)

    def test_a_landing_without_room_is_refused_before_it_takes_the_bundle(self):
        # A stick before a system pool lands on its own partition.
        from unittest import mock
        with mock.patch.object(move.shutil, "disk_usage", return_value=mock.Mock(free=2 << 30)):
            why = move.room_for(5 << 30, self.tmp)
        self.assertIn("without the repositories", why)
        self.assertIn("spaces folder on the Nodes page", why)
        with mock.patch.object(move.shutil, "disk_usage", return_value=mock.Mock(free=20 << 30)):
            self.assertEqual(move.room_for(5 << 30, self.tmp), "")

    def test_a_bundle_from_before_the_held_manifest_is_refused(self):
        # A bundle of the format before, one whose body carries no mark, and
        # one whose manifest names no state: each refused, nothing changed.
        r = move.prepare("user:ann", "https://new.example")
        token = r["token"]
        raw, counts = move.pack()
        m = {"format": 1, "version": "0.9.0", "state_version": 29, "made_at": 1, "packed_at": 1, "from": "https://old.example/",
             "to": "https://new.example", "repos": False, "carries_key": False, "nodes": ["n_1"], "bare_metal": False, "counts": counts,
             "token_hash": move.token_hash(token)}
        old = self.tmp / "old.aeriemove"
        old.write_bytes(move.HEADER + json.dumps(m).encode() + b"\n" + signing.seal(raw, move.key_of(token)))
        self.assertIn("format this build does not read", self._land(old, token).get("error", ""))
        with mock.patch.object(move, "MANIFEST_MARK", "elsewhere.json"):
            r = move.prepare("user:ann", "https://new.example")
        got = self._land(move.bundle_path(), r["token"])
        self.assertIn("too old to land here", got.get("error", ""))
        with mock.patch.object(move, "state_version", lambda: 0):
            r = move.prepare("user:ann", "https://new.example")
        self.assertEqual(json.loads(move.bundle_path().read_bytes().split(b"\n")[1])["state_version"], 0)
        got = self._land(move.bundle_path(), r["token"])
        self.assertIn("nothing updates from", got.get("error", ""))
        self.assertFalse((self.tmp / "new-config" / "users.json").exists(), "nothing here changed")
        self.assertEqual([p.suffix for p in (self.state / "move").iterdir()], [".aeriemove"], "the bundle before went with the next")

    def test_a_manifest_changed_after_the_bundle_was_made_is_refused(self):
        # The plain line's origin, kind and versions were believed.
        r = move.prepare("user:ann", "https://new.example")
        path = self.tmp / "config" / "move" / r["bundle"]
        head, line, body = path.read_bytes().split(b"\n", 2)
        m = json.loads(line)
        self.assertTrue(m.get("mac"))
        for why, edit in (("origin", lambda x: x.update({"from": "https://elsewhere.example/"})),
                          ("mac taken off", lambda x: x.pop("mac"))):
            changed = dict(m)
            edit(changed)
            bad = self.tmp / f"bad-{len(why)}.aeriemove"
            bad.write_bytes(head + b"\n" + json.dumps(changed).encode() + b"\n" + body)
            got = self._land(bad, r["token"])
            self.assertIn("outer details were changed", got.get("error", ""), why)
            self.assertFalse((self.tmp / "new-config" / "users.json").exists(), f"{why}: nothing here changed")
        got = self._land(path, r["token"])
        self.assertTrue(got.get("ok"), got)
        self.assertNotIn("bundle.json", got.get("counts", {}))

    def test_the_bundle_moves_the_state_and_the_nodes_follow(self):
        r = move.prepare("user:ann", "https://new.example", repos=True, carry_key=True)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r["counts"]["state"], 2, "the record and the users; the logs and the apps stay behind")
        self.assertEqual((r["counts"]["repos"], r["counts"]["secrets"], r["counts"]["gitrelay"], r["counts"]["install_key"]), (1, 1, 1, 1))
        token = r["token"]
        st = move.status()
        self.assertTrue(st["prepared"] and st["to"] == "https://new.example" and st["carries_key"] and st["repos"])
        self.assertEqual((st["heard"], st["nodes"], st["stores"]), (0, 2, ["gitrelay"]), "nobody has heard it yet; the logs store is off by default")
        move.for_node("n_1")
        self.assertEqual(move.status()["heard"], 1, "a node whose hello carried the move has heard it")
        self.assertTrue(move.bundle_path().is_file())
        raw = move.bundle_path().read_bytes()
        self.assertNotIn(b'"users"', raw, "the state is sealed, not readable")
        self.assertNotIn(token.encode(), (self.state / "move.json").read_bytes(), "the token is never kept")
        # The nodes are told: an address and a challenge each.
        fn = move.for_node("n_1")
        self.assertEqual(fn["url"], "https://new.example")
        self.assertEqual(len(fn["expect"]), 64)
        self.assertNotEqual(fn["expect"], move.for_node("n_2")["expect"])
        self.assertEqual(move.answer_for("n_1"), "", "nothing is answered before the bundle lands")
        # The new home: another token is refused, an older build is refused,
        # the right token lands the state and answers the nodes' knocks.
        new_state = self.tmp / "new-config"
        new_state.mkdir()
        (new_state / "fresh.json").write_text("{}")
        self.configure(new_state, bare=True)
        self.assertIn("not this bundle's", move.restore(str(move_bundle := self.tmp / "config" / "move" / r["bundle"]), "wrong-token",
                                                         state_dir=new_state)["error"])
        self.assertIn("never lands on an older build", move.restore(str(move_bundle), token, state_dir=new_state, build_state_version=15)["error"])
        got = move.restore(str(move_bundle), token, state_dir=new_state, workspace_dir=self.tmp / "new-ws", secrets_dir=self.tmp / "new-secrets")
        self.assertTrue(got.get("ok"), got)
        self.assertEqual(got["from"], "https://old.example/")
        self.assertEqual(got["nodes"], ["n_1", "n_2"])
        self.assertTrue((new_state / "users.json").is_file() and not (new_state / "logs").exists())
        self.assertTrue((self.tmp / "new-ws" / "alpha" / ".git" / "HEAD").is_file())
        self.assertTrue((self.tmp / "new-secrets" / "deploy.env").is_file())
        self.assertEqual((new_state / ".install-key" / "key").read_bytes(), b"k" * 32)
        self.assertTrue(Path(got["moved_aside"]).is_dir() and (Path(got["moved_aside"]) / "fresh.json").is_file(), "what was there is moved aside")
        self.assertTrue((self.store / "alpha.git" / "HEAD").is_file(), "the store landed where the record names it")
        self.assertEqual(move.answer_for("n_1"), fn["expect"], "the knock is answered with the challenge the node holds")
        self.assertEqual(move.restored()["from"], "https://old.example/")
        self.assertFalse(move.status()["prepared"], "landed, the move is used")
        self.assertEqual(move.for_node("n_1"), {}, "the new home tells its nodes of no move: the record came with the bundle")
        # The nodes not yet here: both, until each says hello
        # after the landing; each with its follow line.
        self.configure(new_state, bare=True, url="https://new.example/")
        nh = move.not_yet_here()
        self.assertEqual([x["name"] for x in nh], ["alpha", "beta"])
        self.assertEqual(nh[0]["line"], f"aerieos-agent follow https://new.example {fn['expect']}", "the address the move named (B936)")
        move.tunnel_host = lambda nid: "aerie.example.com" if nid == "n_2" else ""
        try:
            self.assertTrue(move.not_yet_here()[1]["line"].startswith("aerieos-agent follow https://aerie.example.com "),
                            "a node at the public hostname is followed there")
        finally:
            move.tunnel_host = lambda nid: ""
        move.node_here("n_1")
        move.node_here("n_9")
        self.assertEqual([x["id"] for x in move.not_yet_here()], ["n_2"], "a hello here takes a node off the list; a stranger is nobody's")
        # The old home, marked moved: read-only, saying where; and a late
        # node still hears the move with its challenge.
        self.configure(self.state, bare=False)
        self.assertEqual(move.mark_moved("https://new.example")["to"], "https://new.example")
        self.assertEqual(move.moved_to(), "https://new.example")
        fn2 = move.challenge(move.key_of(token), "n_2")
        self.assertEqual(move.for_node("n_2"), {"url": "https://new.example", "expect": fn2})
        self.assertEqual(move.answer_for("n_2"), "", "the old home answers no knock")
        # Its 410 to a late node names the key to knock under, this
        # controller's own, which went with its state: a node that pinned a
        # certificate before keys were pinned knocked with no pin at all.
        pin = "sha256//" + "A" * 43 + "="
        self.assertEqual(move.moved_answer("n_2", pin), {"error": "this controller moved", "moved": True, "to": "https://new.example",
                                                         "move": {"url": "https://new.example", "expect": fn2, "pin": pin}})
        self.assertEqual(move.moved_answer("n_2", "")["move"], {"url": "https://new.example", "expect": fn2}, "a port under no key names none")
        self.assertEqual(move.moved_answer("", pin), {"error": "this controller moved", "moved": True, "to": "https://new.example"},
                         "a caller it does not know is told where, and nothing of a node's")
        with open(os.path.join(os.path.dirname(__file__), "..", "server.py"), encoding="utf-8") as f:
            self.assertIn('self._json(move.moved_answer(late.get("node") or "", tls.key_pin()), 410)', f.read())
        # A node enrolled at the home tunnel's public hostname is told that
        # hostname, never the new home's local address
        # (a server elsewhere could not follow a move to a LAN address).
        move.tunnel_host = lambda nid: "aerie.example.com" if nid == "n_2" else ""
        try:
            self.assertEqual(move.for_node("n_2")["url"], "https://aerie.example.com")
            self.assertEqual(move.for_node("n_1")["url"], "https://new.example")
            self.assertEqual(move.node_url("n_2", "http://192.168.1.15:7680"), "https://aerie.example.com")
        finally:
            move.tunnel_host = lambda nid: ""
        self.assertIn("moved already", move.prepare("user:ann", "https://x.example")["error"])
        self.assertIn("not withdrawn", move.forget("user:ann")["error"])

    def test_a_repositorys_links_move_as_links_and_one_leading_out_stays_behind(self):
        # Links were skipped, so a moved repository showed them deleted.
        import os
        (self.ws / "alpha" / "README.md").write_text("hi\n")
        os.symlink("README.md", self.ws / "alpha" / "README")
        os.symlink("/etc/passwd", self.ws / "alpha" / "outside")
        r = move.prepare("user:ann", "https://new.example", repos=True, carry_key=True)
        self.assertTrue(r.get("ok"), r)
        new_state = self.tmp / "new-config"
        new_state.mkdir()
        self.configure(new_state, bare=True)
        got = move.restore(str(self.tmp / "config" / "move" / r["bundle"]), r["token"], state_dir=new_state,
                           workspace_dir=self.tmp / "new-ws", secrets_dir=self.tmp / "new-secrets")
        self.assertTrue(got.get("ok"), got)
        link = self.tmp / "new-ws" / "alpha" / "README"
        self.assertTrue(link.is_symlink() and os.readlink(link) == "README.md", "a link inside comes back a link")
        self.assertFalse(os.path.lexists(self.tmp / "new-ws" / "alpha" / "outside"), "one leading out is not restored")

    def test_a_space_folder_already_here_is_set_aside_never_merged(self):
        # The new controller's own alpha and the moved alpha's files
        # were mixed in one folder.
        (self.ws / "alpha" / "README.md").write_text("moved\n")
        (self.ws / ".trash" / "old").mkdir(parents=True)
        (self.ws / ".trash" / "old" / "f").write_text("gone\n")
        r = move.prepare("user:ann", "https://new.example", repos=True, carry_key=True)
        new_state, new_ws = self.tmp / "new-config", self.tmp / "new-ws"
        new_state.mkdir()
        (new_ws / "alpha").mkdir(parents=True)
        (new_ws / "alpha" / "mine.txt").write_text("here first\n")
        (new_ws / "empty").mkdir()
        (new_ws / ".trash" / "old").mkdir(parents=True)
        self.configure(new_state, bare=True)
        got = move.restore(str(self.tmp / "config" / "move" / r["bundle"]), r["token"], state_dir=new_state,
                           workspace_dir=new_ws, secrets_dir=self.tmp / "new-secrets")
        self.assertTrue(got.get("ok"), got)
        self.assertEqual((new_ws / "alpha" / "README.md").read_text(), "moved\n")
        self.assertFalse((new_ws / "alpha" / "mine.txt").exists(), "never merged with what was here")
        kept = [p for p in (new_ws / ".trash").iterdir() if p.name.startswith("alpha-before-move-")]
        self.assertEqual(len(kept), 1)
        self.assertEqual((kept[0] / "mine.txt").read_text(), "here first\n", "what was here, whole in the trash")
        self.assertTrue([p for p in (new_ws / ".trash").iterdir() if p.name.startswith("old-before-move-")], "a deleted one of the same name too")
        said = " ".join(str(x) for x in (got.get("said") or []))
        self.assertIn("alpha: this controller had a space folder of that name", said)

    def land_with_copy_failing(self, which):
        r = move.prepare("user:ann", "https://new.example", repos=True, carry_key=True)
        new_state, new_ws = self.tmp / "new-config", self.tmp / "new-ws"
        new_state.mkdir()
        (new_state / "fresh.json").write_text("{}")
        (new_ws / "alpha").mkdir(parents=True)
        (new_ws / "alpha" / "mine.txt").write_text("here first\n")
        self.configure(new_state, bare=True)
        real = shutil.copytree

        def copy(src, dst, *a, **k):
            if Path(src).name == which:
                raise PermissionError(13, "Permission denied", str(dst))
            return real(src, dst, *a, **k)
        with mock.patch.object(move.shutil, "copytree", copy):
            got = move.restore(str(self.tmp / "config" / "move" / r["bundle"]), r["token"], state_dir=new_state,
                               workspace_dir=new_ws, secrets_dir=self.tmp / "new-secrets")
        return got, new_state

    def test_a_workspace_copy_that_fails_is_said_with_what_was_set_aside(self):
        # The copy's error escaped restore after this controller's
        # alpha had gone to the trash, and the line saying so was lost.
        got, new_state = self.land_with_copy_failing("workspace")
        self.assertIn("could not be copied", got.get("error", ""), got)
        self.assertIn("alpha: this controller had a space folder", got["error"])
        self.assertTrue((new_state / "fresh.json").is_file(), "the state here not changed")
        self.assertFalse((new_state / "users.json").exists())

    def test_secrets_the_home_cannot_take_are_said_and_the_rest_lands(self):
        # A secrets folder that is root's stopped the whole landing.
        got, new_state = self.land_with_copy_failing("secrets")
        self.assertTrue(got.get("ok"), got)
        self.assertIn("secrets were not written", " ".join(got.get("said") or []))
        self.assertTrue((new_state / "users.json").exists())

    def test_share_users_made_here_are_kept_through_a_landing(self):
        # The accounts a stick made from the old system's share users
        # went with the state the move replaced, and the shares lost them.
        r = move.prepare("user:ann", "https://new.example", repos=True, carry_key=True)
        new_state = self.tmp / "new-config"
        new_state.mkdir()
        here = {"users": {
            "setup": {"uid": "u_00000001", "role": "owner", "password": "pbkdf2_sha256$1$x$y"},
            "carol": {"uid": "u_0000000c", "role": "user", "password": "", "smb_nt": "A" * 32},
            "ann": {"uid": "u_0000000a", "role": "user", "password": "", "smb_nt": "B" * 32},
            "dave": {"uid": "u_0000000d", "role": "user", "password": ""}}}
        (new_state / "users.json").write_text(json.dumps(here))
        self.configure(new_state, bare=True)
        got = move.restore(str(self.tmp / "config" / "move" / r["bundle"]), r["token"], state_dir=new_state,
                           workspace_dir=self.tmp / "new-ws", secrets_dir=self.tmp / "new-secrets")
        self.assertTrue(got.get("ok"), got)
        users = json.loads((new_state / "users.json").read_text())["users"]
        self.assertEqual(users["carol"], here["users"]["carol"], "kept whole, its id with it")
        self.assertNotIn("setup", users, "the setup account goes with what was here")
        self.assertNotIn("dave", users, "no SMB password: not a share user")
        self.assertNotEqual(users["ann"].get("smb_nt"), "B" * 32, "the moved controller's ann is its own")
        said = " ".join(got.get("said") or [])
        self.assertIn("kept as accounts with their SMB passwords: carol", said)
        self.assertIn("already has are its accounts now: ann", said)
        self.assertEqual(os.stat(new_state / "users.json").st_mode & 0o777, 0o600)

    def test_a_backup_arms_nothing_and_lands_under_its_own_token(self):
        # A copy of the controller to keep, under a token
        # the person records, no move armed and no node told; landed, it
        # never tells the controller it came from, and nodes still there
        # follow by its key.
        (self.ws / "alpha" / "README.md").write_text("kept\n")
        r = move.backup_bundle("user:ann", repos=True, carry_key=False)
        self.assertTrue(r.get("ok"), r)
        self.assertFalse(move._load().get("made_at"), "no move armed")
        self.assertEqual(move.for_node("n_02529b69"), {}, "no node told")
        p = move.backup_path(r["bundle"])
        self.assertTrue(p and p.is_file())
        self.assertIsNone(move.backup_path("../users.json"))
        new_state, new_ws = self.tmp / "new-config", self.tmp / "new-ws"
        new_state.mkdir()
        self.configure(new_state, bare=True)
        self.assertIn("token", move.restore(str(p), "wrong-token", state_dir=new_state, workspace_dir=new_ws,
                                            secrets_dir=self.tmp / "new-secrets").get("error", ""))
        got = move.restore(str(p), r["token"], state_dir=new_state, workspace_dir=new_ws, secrets_dir=self.tmp / "new-secrets")
        self.assertTrue(got.get("ok"), got)
        self.assertEqual((new_ws / "alpha" / "README.md").read_text(), "kept\n")
        rec = json.loads((new_state / "move.json").read_text())
        self.assertEqual((rec.get("came_from"), rec.get("came_from_backup")), ("", True), "the controller it came from is never told")
        self.assertTrue(rec.get("key_b64") and rec.get("token_hash") == move.token_hash(r["token"]), "nodes still there follow by its key")

    def test_a_restore_that_fails_puts_the_state_back(self):
        # A failure after the swap left the new state half restored
        # and the old one aside, unsaid.
        r = move.prepare("user:ann", "https://new.example", repos=True, carry_key=True)
        new_state = self.tmp / "new-config"
        new_state.mkdir()
        (new_state / "fresh.json").write_text("{}")
        self.configure(new_state, bare=True)
        def refused(key, state_dir):
            raise OSError("no")
        with mock.patch.object(move, "install_landed_key", refused):
            got = move.restore(str(self.tmp / "config" / "move" / r["bundle"]), r["token"], state_dir=new_state,
                               workspace_dir=self.tmp / "new-ws", secrets_dir=self.tmp / "new-secrets")
        self.assertIn("back as it was", got.get("error", ""), got)
        self.assertTrue((new_state / "fresh.json").is_file(), "the state that was here, in its place")
        self.assertFalse((new_state / "users.json").exists())
        self.assertEqual([p.name for p in new_state.iterdir() if p.name.startswith(".move")], [], "nothing of the landing left")

    def test_a_carried_key_the_home_cannot_take_is_said(self):
        # INSTALL_KEY in the new home's environment, so the carried key
        # is not taken; the landing reported ok and nothing said why the
        # moved state's sealed settings answered Locked.
        r = move.prepare("user:ann", "https://new.example", repos=False, carry_key=True)
        new_state = self.tmp / "new-config"
        new_state.mkdir()
        self.configure(new_state, bare=True)
        with mock.patch.object(move, "install_landed_key", lambda key, state_dir: "this install's key is set in its environment (INSTALL_KEY), so the carried key was not taken"):
            got = move.restore(str(self.tmp / "config" / "move" / r["bundle"]), r["token"], state_dir=new_state,
                               workspace_dir=self.tmp / "new-ws", secrets_dir=self.tmp / "new-secrets")
        self.assertTrue(got.get("ok"), got)
        self.assertEqual(len(got["said"]), 1)
        self.assertIn("INSTALL_KEY", got["said"][0])
        self.assertIn("INSTALL_KEY", json.loads((new_state / "move.json").read_text()).get("said", [""])[0]) if (new_state / "move.json").is_file() else None

    def test_a_landing_cut_midway_is_marked_and_said_and_finishes_on_the_next(self):
        # The power goes between the renames; the next start finds the
        # mark, the bell says what is where, and the same bundle lands again.
        r = move.prepare("user:ann", "https://new.example", repos=False, carry_key=False)
        new_state = self.tmp / "new-config"
        new_state.mkdir()
        (new_state / "fresh.json").write_text("{}")
        self.configure(new_state, bare=True)
        bundle = str(self.tmp / "config" / "move" / r["bundle"])
        real_into = move._into

        def cut(src, dst):
            raise KeyboardInterrupt("the power")
        with mock.patch.object(move, "_into", cut), self.assertRaises(KeyboardInterrupt):
            move.restore(bundle, r["token"], state_dir=new_state, workspace_dir=self.tmp / "new-ws", secrets_dir=self.tmp / "new-secrets")
        c = move.cut_landing(new_state)
        self.assertTrue(c and c["stamp"], c)
        self.assertTrue(Path(c["aside"]).is_dir() and (Path(c["aside"]) / "fresh.json").is_file(), "what was here, kept whole aside")
        out = io.StringIO()
        with mock.patch.object(move, "STATE", new_state), contextlib.redirect_stdout(out):
            rows = move.cut_landing_rows()
            again = move.cut_landing_rows()
        self.assertEqual(len(rows), 1)
        self.assertRegex(rows[0]["why"], r"^A move's landing was cut midway on [^.]*: landing the same bundle again with its token, "
                                         r"from Controller settings, finishes it$", "one sentence")
        self.assertEqual(again, rows)
        # ...where what was here is kept, in the log, once.
        self.assertEqual(out.getvalue().count(c["aside"]), 1, out.getvalue())
        # The same bundle again, with its token: the landing finishes and the mark goes.
        move._into = real_into
        got = move.restore(bundle, r["token"], state_dir=new_state, workspace_dir=self.tmp / "new-ws", secrets_dir=self.tmp / "new-secrets")
        self.assertTrue(got.get("ok"), got)
        self.assertIsNone(move.cut_landing(new_state))
        self.assertTrue((new_state / "users.json").is_file())

    def test_a_landing_swaps_inside_a_state_folder_it_cannot_rename(self):
        # The parent is root's on an installed machine, a mount point's
        # in a container. Here the parent is read-only, as it is for the
        # controller's account there.
        r = move.prepare("user:ann", "https://new.example")
        parent = self.tmp / "locked"
        new_state = parent / "config"
        new_state.mkdir(parents=True)
        (new_state / "fresh.json").write_text("{}")
        (new_state / "logs").mkdir()
        (new_state / "logs" / "today").write_text("kept where it is")
        path = str(self.tmp / "config" / "move" / r["bundle"])
        os.chmod(parent, 0o555)
        self.addCleanup(os.chmod, parent, 0o755)
        got = move.restore(path, r["token"], state_dir=new_state, workspace_dir=self.tmp / "new-ws", secrets_dir=self.tmp / "new-secrets",
                           build_state_version=29, here_bare_metal=False)
        self.assertTrue(got.get("ok"), got)
        self.assertTrue((new_state / "users.json").is_file())
        self.assertTrue((Path(got["moved_aside"]) / "fresh.json").is_file(), "set aside, never deleted")
        self.assertEqual(Path(got["moved_aside"]).parent, new_state)

    def test_a_store_whose_path_cannot_be_made_lands_under_the_state(self):
        # And the record stops naming the path.
        (self.state / "paths.json").write_text(json.dumps({"gitrelay": "/nowhere/gitrelay"}))
        r = move.prepare("user:ann", "https://new.example")
        new_state = self.tmp / "new-config"
        blocker = self.tmp / "a-file"
        blocker.write_text("not a folder")
        with mock.patch.object(move, "store_paths", lambda: {"gitrelay": str(blocker / "gitrelay")}):
            got = move.restore(str(self.tmp / "config" / "move" / r["bundle"]), r["token"], state_dir=new_state, workspace_dir=self.tmp / "new-ws",
                               secrets_dir=self.tmp / "new-secrets", build_state_version=29, here_bare_metal=False)
        self.assertTrue(got.get("ok"), got)
        self.assertTrue((new_state / "gitrelay" / "alpha.git" / "HEAD").is_file())
        self.assertNotIn("gitrelay", json.loads((new_state / "paths.json").read_text()))

    def test_a_state_this_build_does_not_read_is_refused(self):
        # Before it lands, not at the next start.
        r = move.prepare("user:ann", "https://new.example")
        with mock.patch.object(move.stateversion, "SUPPORTED_FROM", 99):
            got = self._land(self.tmp / "config" / "move" / r["bundle"], r["token"])
        self.assertIn("which nothing updates from, so it cannot land here", got.get("error", ""))

    def test_what_a_landing_sets_aside_is_never_carried(self):
        # ...nor the state's own copies (copies of copies: 2.1 GB of the dev
        # instance's 2.2 GB bundle, 18 Nov).
        for name in (".moved-1", ".move-upload-2", ".reset-3", "backups", "backup"):
            (self.state / name).mkdir()
            (self.state / name / "big").write_text("x")
        move.prepare("user:ann", "https://new.example")
        import tarfile
        raw, _ = move.pack()
        with tarfile.open(fileobj=__import__("io").BytesIO(raw)) as t:
            self.assertEqual([n for n in t.getnames() if ".mov" in n or ".reset" in n or "/backup" in n], [])

    def test_the_running_dashboards_own_files_are_never_carried_nor_swapped(self):
        # The supervisor watches .server.pid and the lock keeps one server on
        # the folder: a landing that swapped in the old controller's had a
        # second dashboard started on the half-swapped state (walked 18 Nov).
        (self.state / ".server.pid").write_text("4242\n")
        (self.state / ".server.lock").write_text("")
        r = move.prepare("user:ann", "https://new.example")
        import tarfile
        raw, _ = move.pack()
        with tarfile.open(fileobj=__import__("io").BytesIO(raw)) as t:
            self.assertEqual([n for n in t.getnames() if ".server." in n], [])
        new_state = self.tmp / "new-config"
        new_state.mkdir()
        (new_state / ".server.pid").write_text("777\n")
        (new_state / ".server.lock").write_text("")
        self.configure(new_state, bare=False)
        got = move.restore(str(self.tmp / "config" / "move" / r["bundle"]), r["token"], state_dir=new_state,
                           workspace_dir=self.tmp / "new-ws", secrets_dir=self.tmp / "new-secrets")
        self.assertTrue(got.get("ok"), got)
        self.assertEqual((new_state / ".server.pid").read_text(), "777\n", "the running dashboard's pid stays in place")
        self.assertTrue((new_state / ".server.lock").is_file())
        self.assertFalse((Path(got["moved_aside"]) / ".server.pid").exists(), "never set aside with the old state")

    def test_deploy_keys_go_to_the_helper_where_this_home_cannot_write_them(self):
        # The home's deploy-keys folder is the root helper's; a landing
        # that merged into it stopped there and went back whole.
        dk = self.state / "deploy-keys"
        dk.mkdir()
        (dk / "web-deploy.sealed").write_text("sealed")
        (dk / "web-deploy.pub").write_text("ssh-ed25519 AAAA web-deploy")
        r = move.prepare("user:ann", "https://new.example")
        new_state = self.tmp / "new-config"
        (new_state / "deploy-keys").mkdir(parents=True)
        os.chmod(new_state / "deploy-keys", 0o500)
        self.addCleanup(os.chmod, new_state / "deploy-keys", 0o700)
        self.configure(new_state, bare=False)
        handed = []

        def keep(folder):
            handed.append(sorted(os.listdir(folder)))
            return "1 deploy keys came with it, loaded"
        with mock.patch.object(move, "place_deploy_keys", keep):
            got = move.restore(str(self.tmp / "config" / "move" / r["bundle"]), r["token"], state_dir=new_state,
                               workspace_dir=self.tmp / "new-ws", secrets_dir=self.tmp / "new-secrets")
        self.assertTrue(got.get("ok"), got)
        self.assertEqual(handed, [["web-deploy.pub", "web-deploy.sealed"]])
        self.assertIn("1 deploy keys came with it, loaded", got["said"])
        self.assertEqual(os.listdir(new_state / "deploy-keys"), [], "nothing written there by the landing itself")

    def test_a_landing_says_a_key_left_behind_and_spaces_with_no_folder(self):
        # What stays locked, and the spaces whose repositories
        # did not come, said in the landing's result.
        (self.state / "claude-prefs.json").write_text(json.dumps({"projects": {"alpha": {}, "gone": {}}}))
        r = move.prepare("user:ann", "https://new.example")
        new_state, new_ws = self.tmp / "new-config", self.tmp / "new-ws"
        new_state.mkdir()
        (new_ws / "alpha").mkdir(parents=True)
        self.configure(new_state, bare=False)
        got = move.restore(str(self.tmp / "config" / "move" / r["bundle"]), r["token"], state_dir=new_state,
                           workspace_dir=new_ws, secrets_dir=self.tmp / "new-secrets")
        said = " | ".join(got.get("said") or [])
        self.assertIn("the old install's key did not come with it", said)
        self.assertIn("1 of the moved spaces have no folder here (gone)", said)

    def test_a_prepared_move_is_forgotten_and_a_bad_address_refused(self):
        self.assertIn("http://", move.prepare("user:ann", "new.example")["error"])
        r = move.prepare("user:ann", "")
        self.assertTrue(r.get("ok"), "an address may be named later")
        self.assertEqual(move.for_node("n_1"), {}, "no address yet: the nodes are told nothing")
        self.assertTrue(move.forget("user:ann")["ok"])
        self.assertIsNone(move.bundle_path())
        self.assertIn("no move", move.forget("user:ann")["error"])
        m, why = move.read_manifest(str(self.state / "users.json"))
        self.assertIsNone(m)
        self.assertIn("not an AerieOS move bundle", why)


    def test_a_pull_is_told_which_pack_it_was_handed_and_holds_the_bundle_to_it(self):
        # Every pack of one move is sealed under the move's one key: an
        # older pack of it stood in for the newest with nothing to say so.
        r = move.prepare("user:ann", "https://new.example")
        token, key = r["token"], move.key_of(r["token"])
        first = (self.tmp / "config" / "move" / r["bundle"]).read_bytes()
        again = move.pack_bundle()
        newest = (self.tmp / "config" / "move" / again["bundle"]).read_bytes()
        ids = [json.loads(b.split(b"\n", 2)[1])["pack"] for b in (first, newest)]
        self.assertTrue(all(len(i) == 32 for i in ids) and ids[0] != ids[1], ids)
        self.assertEqual(move.status().get("bundle"), again["bundle"])

        def pull(body, headers):
            class Answer:
                def __init__(self, nonce):
                    self.headers = {"Content-Length": str(len(body)), **headers(nonce)}
                    self.left = [body]

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def read(self, n=-1):
                    return self.left.pop() if self.left else b""

            def urlopen(req, **kw):
                q = move.urllib.parse.parse_qs(move.urllib.parse.urlparse(req.full_url).query)
                return Answer(q["nonce"][0])
            with mock.patch.object(move.urllib.request, "urlopen", urlopen):
                return move.fetch_bundle("https://old.example/", token, str(self.tmp / "pulled"))
        said = lambda pack: lambda nonce: {"X-Aerie-Pack": pack, "X-Aerie-Pack-Proof": move.pack_proof(key, nonce, pack)}  # noqa: E731
        # The old controller's own words for a pull are its newest pack's.
        self.assertEqual(move.pulled_headers({"nonce": "n1"}), said(ids[1])("n1"))
        self.assertEqual(pull(newest, said(ids[1])), "")
        # A controller from before packs had an id says none: updated first.
        self.assertIn("update it, then move again", pull(newest, lambda nonce: {}))
        # A word that is not the key's, or was made for another pull.
        self.assertIn("does not verify", pull(newest, lambda nonce: {"X-Aerie-Pack": ids[1], "X-Aerie-Pack-Proof": "0" * 64}))
        self.assertIn("does not verify", pull(newest, lambda nonce: said(ids[1])("another pull's nonce")))
        # ...and the older pack of the same move in the newest's place.
        self.assertIn("not the one the old controller packed for this pull", pull(first, said(ids[1])))

    def test_a_body_under_another_pack_s_details_is_refused(self):
        # The details and the body are sealed apart under one key: the id in
        # both is what holds a body to its own details.
        r = move.prepare("user:ann", "https://new.example")
        one = (self.tmp / "config" / "move" / r["bundle"]).read_bytes()
        two = (self.tmp / "config" / "move" / move.pack_bundle()["bundle"]).read_bytes()
        head, line, _ = one.split(b"\n", 2)
        body = two.split(b"\n", 2)[2]
        bad = self.tmp / "spliced.aeriemove"
        bad.write_bytes(head + b"\n" + line + b"\n" + body)
        self.assertIn("body is not the one its outer details were written for", self._land(bad, r["token"]).get("error", ""))

    def test_a_bundle_file_from_before_packs_had_an_id_still_lands(self):
        # A file kept from an earlier build names no pack in its details or
        # its body, and lands as it did; its id taken off the details of one
        # that has it, by somebody holding the key, does not.
        r = move.prepare("user:ann", "https://new.example")
        with mock.patch.object(move.secrets, "token_hex", return_value=""):
            old = self.tmp / "config" / "move" / move.pack_bundle()["bundle"]
        self.assertEqual(json.loads(old.read_bytes().split(b"\n", 2)[1])["pack"], "")
        kept = self.tmp / "kept.aeriemove"
        kept.write_bytes(old.read_bytes())
        with_id = (self.tmp / "config" / "move" / move.pack_bundle()["bundle"]).read_bytes()
        head, line, body = with_id.split(b"\n", 2)
        m = json.loads(line)
        m.pop("pack")
        m["mac"] = move._manifest_mac(move.key_of(r["token"]), m)
        bad = self.tmp / "stripped.aeriemove"
        bad.write_bytes(head + b"\n" + json.dumps(m).encode() + b"\n" + body)
        self.assertIn("body is not the one its outer details were written for", self._land(bad, r["token"]).get("error", ""))
        got = self._land(kept, r["token"])
        self.assertTrue(got.get("ok"), got)

    def test_a_pull_sends_the_timed_proof_and_the_one_an_older_controller_reads(self):
        asked = []

        class Answer:
            headers = {"Content-Length": "5"}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, n=-1):
                self.read = lambda n=-1: b""
                return b"hello"

        def urlopen(req, **kw):
            asked.append(req.full_url)
            return Answer()
        token = move.new_token()
        key = move.key_of(token)
        with mock.patch.object(move.urllib.request, "urlopen", urlopen):
            # The answer here says no pack, as a controller from before
            # packs had an id: the pull is made whole and then refused.
            self.assertIn("update it, then move again", move.fetch_bundle("https://old.example/", token, str(self.tmp / "pulled")))
        q = {k: v[0] for k, v in move.urllib.parse.parse_qs(move.urllib.parse.urlparse(asked[0]).query).items()}
        self.assertEqual(q["hash"], move.token_hash(token))
        self.assertEqual(q["tproof"], move.fetch_proof(key, q["nonce"], int(q["at"])))
        self.assertEqual(q["proof"], move.fetch_proof(key, q["nonce"]))
        self.assertNotEqual(q["proof"], q["tproof"])
        self.assertLess(abs(int(q["at"]) - time.time()), 5)

    def test_the_landing_is_told_both_ways_and_the_pull_is_proved(self):
        r = move.prepare("user:ann", "https://new.example")
        token, key = r["token"], move.key_of(r["token"])
        th = move.token_hash(token)
        # The old side taking the new one's word: the wrong hash, a wrong
        # proof, then the right one, which marks this controller moved.
        self.assertEqual(move.take_landing({"hash": "x", "at": 5, "proof": "y"})[1], 403)
        self.assertEqual(move.take_landing({"hash": th, "at": 5, "proof": move.landed_proof(key, 6)})[1], 403)
        out, st = move.take_landing({"hash": th, "at": 5, "proof": move.landed_proof(key, 5), "here": "https://new.example"})
        self.assertEqual((st, out["moved"], out["to"]), (200, True, "https://new.example"))
        self.assertEqual((move.status()["how"], move.status()["landed_at"]), ("told", 5))
        self.assertEqual(self.audits[-1][0], "moved-by-landing")
        self.assertEqual(move.take_landing({"hash": th, "at": 5, "proof": move.landed_proof(key, 5)})[0]["moved"], True, "told twice is one answer")
        # The pull's proof: refused after the move, so a
        # fresh old controller is armed for it.
        now = int(time.time())
        pull = lambda nonce, at=now, **kw: move.serve_fetch({"hash": th, "nonce": nonce, "at": at, "tproof": move.fetch_proof(key, nonce, at), **kw})  # noqa: E731
        self.assertEqual(pull("n1")[2], 410)
        self.configure(self.state, bare=False)
        move.forget("user:ann") if not move.moved_to() else None
        state2 = self.tmp / "config2"
        shutil.copytree(self.state, state2, ignore=shutil.ignore_patterns("move.json", "move"))
        self.configure(state2, bare=False)
        r = move.prepare("user:ann", "")
        token, key, th = r["token"], move.key_of(r["token"]), move.token_hash(r["token"])
        self.assertEqual(move.serve_fetch({"hash": th, "nonce": "n1", "at": now, "tproof": "bad"})[2], 403)
        # A proof with no time in it, which is all an older install sends,
        # is refused in a sentence that says what to do; so is a time that
        # is not now by this clock, and a proof made for another time.
        got = move.serve_fetch({"hash": th, "nonce": "n0", "proof": move.fetch_proof(key, "n0")})
        self.assertEqual(got[2], 403)
        self.assertIn("update the install that is pulling", got[1])
        for late in (now - move.NONCE_LIFE, now + move.NONCE_LIFE):
            got = pull("n0", late)
            self.assertEqual(got[2], 403, late)
            self.assertIn("clocks differ", got[1])
        self.assertEqual(move.serve_fetch({"hash": th, "nonce": "n0", "at": now, "tproof": move.fetch_proof(key, "n0", now - 60)})[2], 403)
        path, why, st = pull("n1")
        self.assertTrue(st == 200 and Path(path).is_file() and Path(path).name == move.status()["bundle"], (path, why))
        self.assertEqual(pull("n1")[2], 403, "a nonce is good once")
        self.assertEqual(self.audits[-1][0], "move-bundle-pulled")
        # ...and its nonce is remembered for as long as its time could pass.
        self.assertGreaterEqual(move.NONCE_LIFE, 2 * (move.NONCE_LIFE // 2))
        # The bundle is packed fresh: a record written after Prepare is in it.
        (state2 / "later.json").write_text("{}")
        path, why, st = pull("n2")
        m, _ = move.read_manifest(path)
        self.assertEqual(m["counts"]["state"], 3, "the record, the users and the later file")
        # The new side answering the old one's asking, once
        # the bundle landed there.
        new_state = self.tmp / "new-config"
        new_state.mkdir()
        self.configure(new_state, bare=True, url="https://new.example/")
        got = move.restore(path, token, state_dir=new_state, workspace_dir=self.tmp / "new-ws", secrets_dir=self.tmp / "new-secrets")
        self.assertTrue(got.get("ok"), got)
        self.assertEqual(move.answer_asked({"hash": th, "nonce": "q", "proof": "bad"})[1], 403)
        out, st = move.answer_asked({"hash": th, "nonce": "q", "proof": move.asked_proof(key, "q")})
        self.assertEqual((st, out["ok"], out["here"]), (200, True, "https://new.example/"))
        self.assertEqual(out["landed_at"], move.restored()["restored_at"])
        self.assertEqual(move.restored()["from"], "https://old.example/")
        self.assertFalse(move.tell_old(force=True), "the old address does not answer from here; told again next tick")
        self.assertIn("tell_error", move.restored())

    def test_a_secrets_folder_the_dashboard_cannot_list_is_said_on_its_piece(self):
        # Root's folder on a machine of its own was walked as empty,
        # and the piece said nothing of it.
        os.chmod(self.secrets, 0o100)
        self.addCleanup(os.chmod, self.secrets, 0o700)
        if os.access(self.secrets, os.R_OK):
            self.skipTest("run as root: every folder reads")
        pc = next(p for p in move.pieces() if p["key"] == "secrets")
        self.assertFalse(pc["on"])
        self.assertIn("root's alone here, so a bundle carries none of it", pc["about"])

    def test_the_pieces_say_their_sizes_and_the_ticks_hold(self):
        pcs = {p["key"]: p for p in move.pieces()}
        self.assertTrue(pcs["state"]["fixed"] and pcs["state"]["on"] and pcs["state"]["size"] > 0)
        self.assertTrue(pcs["store:gitrelay"]["on"] and not pcs["store:logs"]["on"], "the logs store is off unless ticked")
        self.assertFalse(pcs["repos"]["on"] or pcs["install_key"]["on"])
        self.assertEqual((pcs["repos"]["size"], pcs["repos"]["over"]), (len("ref: refs/heads/main\n"), False))
        move._sizes.clear()
        move.SIZE_BUDGET_S = -1
        self.assertTrue(move.pieces()[0]["over"], "past the budget a size is a floor, said so (B432)")
        move.SIZE_BUDGET_S = 1.0
        move._sizes.clear()
        (self.tmp / "logs").mkdir()
        (self.tmp / "logs" / "a.log").write_text("x")
        r = move.prepare("user:ann", "", stores=["gitrelay", "logs"])
        self.assertEqual((r["counts"].get("gitrelay"), r["counts"].get("logs")), (1, 1))
        self.assertEqual(move.status()["stores"], ["gitrelay", "logs"])
        self.assertTrue(move.forget("user:ann")["ok"])
        r = move.prepare("user:ann", "", stores=[])
        self.assertNotIn("gitrelay", r["counts"], "no store ticked, none carried")

    def test_the_install_key_under_the_secrets_travels_only_by_its_tick(self):
        # An install keeps its key at secrets/install-key (lib/boot.sh);
        # the secrets are packed whole, and the key went with them unticked.
        (self.secrets / "install-key").mkdir()
        (self.secrets / "install-key" / "key").write_bytes(b"k" * 32)
        (self.secrets / "install-key" / "key-previous").write_bytes(b"p" * 32)
        for carry in (False, True):
            raw, counts = move.pack(carry_key=carry)
            names = tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz").getnames()
            self.assertIn("secrets/deploy.env", names)
            self.assertFalse([n for n in names if n.startswith("secrets/install-key")], f"carry_key={carry}: the key's folder stays out of the secrets")
            self.assertEqual(("install-key" in names, counts.get("install_key")), (carry, 1 if carry else None))
            self.assertEqual(counts["secrets"], 1, "the deploy key alone")
        pcs = {p["key"]: p for p in move.pieces()}
        self.assertEqual(pcs["secrets"]["size"], len("DEPLOY=1\n"), "the tick's size leaves the key's folder out too")

    def test_the_install_key_beside_the_state_travels_only_by_its_tick(self):
        # An install with no secrets folder keeps its key at
        # /config/.install-key (lib/boot.sh), which the state's walk packed.
        (self.state / ".install-key").mkdir()
        (self.state / ".install-key" / "key").write_bytes(b"k" * 32)
        for carry in (False, True):
            raw, counts = move.pack(carry_key=carry)
            names = tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz").getnames()
            self.assertFalse([n for n in names if ".install-key" in n], f"carry_key={carry}: the state's key folder stays out")
            self.assertEqual("install-key" in names, carry)

    def test_the_database_goes_as_a_snapshot_never_a_file_copy(self):
        # The server writes its database all the while; a copy of the
        # file read across a write is torn. What a backup reads is whole,
        # its log folded in, with no -wal or -shm beside it.
        import sqlite3
        db = sqlite3.connect(str(self.state / "builderbot.db"))
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE t (x)")
        db.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(100)])
        db.commit()
        self.assertTrue((self.state / "builderbot.db-wal").exists(), "the rows are in the log, not yet the file")
        raw, _counts = move.pack()
        tf = tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz")
        names = tf.getnames()
        db.close()
        self.assertEqual([n for n in names if "builderbot.db" in n], ["state/builderbot.db"])
        self.assertFalse([n for n in names if "/.move-" in n], "the snapshot's own file is never packed by its name")
        out = self.tmp / "out.db"
        out.write_bytes(tf.extractfile("state/builderbot.db").read())
        self.assertEqual(sqlite3.connect(str(out)).execute("SELECT count(*) FROM t").fetchone()[0], 100)
        self.assertFalse([p for p in self.state.iterdir() if p.name.startswith(".move-db-")], "the snapshot is gone after")


if __name__ == "__main__":
    unittest.main()
