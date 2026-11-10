"""Moving a controller to another home (R90 step 12, move.py): the bundle
sealed under a token shown once, the nodes' challenges, the restore held to
the version gate and refused under another token, the old home marked
moved, and what the new home answers a node's knock; and the second pass
(R175): the move armed with no life and the bundle packed fresh, a late
node handed its challenge after the move, the landing told both ways under
the move key, the pull's proof, the pieces, and the nodes not yet here."""
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
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
                       seal_fn=signing.seal, open_fn=signing.open_with, state_version_fn=lambda: 19, build_version_fn=lambda: "0.9.0",
                       install_key_fn=lambda: b"k" * 32, store_paths_fn=lambda: {"gitrelay": str(self.store), "logs": str(self.tmp / "logs")},
                       page_url_fn=lambda: url, node_ids_fn=lambda: ["n_1", "n_2"], bare_metal_fn=lambda: bare,
                       node_name_fn=lambda nid: {"n_1": "alpha", "n_2": "beta"}.get(nid, nid),
                       audit_fn=lambda who, what, detail: self.audits.append((what, detail)))

    def _land(self, path, token):
        return move.restore(str(path), token, state_dir=self.tmp / "new-config", workspace_dir=self.tmp / "new-ws",
                            secrets_dir=self.tmp / "new-secrets", build_state_version=19, here_bare_metal=False)

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
        # B558: never whole in memory; here pieces of 4 KiB over a
        # repository of 64 KiB of noise, so a bundle is many pieces.
        (self.ws / "alpha" / "big.bin").write_bytes(os.urandom(64 << 10))
        move.PIECE, was = 4096, move.PIECE
        self.addCleanup(setattr, move, "PIECE", was)
        r = move.prepare("user:ann", "https://new.example", repos=True)
        path = move.bundle_path()
        head, pieces = self._pieces(path)
        self.assertEqual(json.loads(head.split(b"\n")[1])["format"], 2)
        self.assertGreater(len(pieces), 10)
        bad = self.tmp / "bad.bbmove"
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
        # A full disk on the old home (the operator, 8 Nov): the body went to
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
                b"--XYZ\r\nContent-Disposition: form-data; name=\"bundle\"; filename=\"b.bbmove\"\r\n"
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
        # B588: a stick before a system pool lands on its own partition.
        from unittest import mock
        with mock.patch.object(move.shutil, "disk_usage", return_value=mock.Mock(free=2 << 30)):
            why = move.room_for(5 << 30, self.tmp)
        self.assertIn("without the repositories", why)
        self.assertIn("spaces folder on the Nodes page", why)
        with mock.patch.object(move.shutil, "disk_usage", return_value=mock.Mock(free=20 << 30)):
            self.assertEqual(move.room_for(5 << 30, self.tmp), "")

    def test_a_bundle_of_the_format_before_still_lands(self):
        r = move.prepare("user:ann", "https://new.example")
        token = r["token"]
        raw, counts = move.pack()
        m = {"format": 1, "version": "0.9.0", "state_version": 19, "made_at": 1, "packed_at": 1, "from": "https://old.example/",
             "to": "https://new.example", "repos": False, "carries_key": False, "nodes": ["n_1"], "bare_metal": False, "counts": counts,
             "token_hash": move.token_hash(token)}
        old = self.tmp / "old.bbmove"
        old.write_bytes(move.HEADER + json.dumps(m).encode() + b"\n" + signing.seal(raw, move.key_of(token)))
        got = self._land(old, token)
        self.assertTrue(got.get("ok"), got)
        self.assertTrue((self.tmp / "new-config" / "users.json").is_file())

    def test_a_manifest_changed_after_the_bundle_was_made_is_refused(self):
        # B724: the plain line's origin, kind and versions were believed.
        r = move.prepare("user:ann", "https://new.example")
        path = self.tmp / "config" / "move" / r["bundle"]
        head, line, body = path.read_bytes().split(b"\n", 2)
        m = json.loads(line)
        self.assertTrue(m.get("mac"))
        for why, edit in (("origin", lambda x: x.update({"from": "https://elsewhere.example/"})),
                          ("mac taken off", lambda x: x.pop("mac"))):
            changed = dict(m)
            edit(changed)
            bad = self.tmp / f"bad-{len(why)}.bbmove"
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
        # The nodes not yet here (R175 step 3): both, until each says hello
        # after the landing; each with its follow line.
        self.configure(new_state, bare=True, url="https://new.example/")
        nh = move.not_yet_here()
        self.assertEqual([x["name"] for x in nh], ["alpha", "beta"])
        self.assertEqual(nh[0]["line"], f"aerieos-agent follow https://new.example/ {fn['expect']}")
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
        # node still hears the move with its challenge (R175 step 2).
        self.configure(self.state, bare=False)
        self.assertEqual(move.mark_moved("https://new.example")["to"], "https://new.example")
        self.assertEqual(move.moved_to(), "https://new.example")
        fn2 = move.challenge(move.key_of(token), "n_2")
        self.assertEqual(move.for_node("n_2"), {"url": "https://new.example", "expect": fn2})
        self.assertEqual(move.answer_for("n_2"), "", "the old home answers no knock")
        # A node enrolled at the home tunnel's public hostname is told that
        # hostname, never the new home's local address (the operator, 10 Nov:
        # a server elsewhere could not follow a move to a LAN address).
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
        # B556: links were skipped, so a moved repository showed them deleted.
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
        # B707: the new controller's own alpha and the moved alpha's files
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
        # B725: the copy's error escaped restore() after this controller's
        # alpha had gone to the trash, and the line saying so was lost.
        got, new_state = self.land_with_copy_failing("workspace")
        self.assertIn("could not be copied", got.get("error", ""), got)
        self.assertIn("alpha: this controller had a space folder", got["error"])
        self.assertTrue((new_state / "fresh.json").is_file(), "the state here not changed")
        self.assertFalse((new_state / "users.json").exists())

    def test_secrets_the_home_cannot_take_are_said_and_the_rest_lands(self):
        # B728: a secrets folder that is root's stopped the whole landing.
        got, new_state = self.land_with_copy_failing("secrets")
        self.assertTrue(got.get("ok"), got)
        self.assertIn("secrets were not written", " ".join(got.get("said") or []))
        self.assertTrue((new_state / "users.json").exists())

    def test_share_users_made_here_are_kept_through_a_landing(self):
        # B716: the accounts a stick made from the old system's share users
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
        # The operator, 6 Nov: a copy of the controller to keep, under a token
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
        # B557: a failure after the swap left the new state half restored
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
        # B623: INSTALL_KEY in the new home's environment, so the carried key
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
        # B622: the power goes between the renames; the next start finds the
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
        with mock.patch.object(move, "STATE", new_state):
            rows = move.cut_landing_rows()
        self.assertEqual(len(rows), 1)
        self.assertIn("cut midway", rows[0]["why"])
        self.assertIn(os.path.basename(c["aside"]), rows[0]["why"])
        self.assertIn("Land the same bundle again", rows[0]["why"])
        # The same bundle again, with its token: the landing finishes and the mark goes.
        move._into = real_into
        got = move.restore(bundle, r["token"], state_dir=new_state, workspace_dir=self.tmp / "new-ws", secrets_dir=self.tmp / "new-secrets")
        self.assertTrue(got.get("ok"), got)
        self.assertIsNone(move.cut_landing(new_state))
        self.assertTrue((new_state / "users.json").is_file())

    def test_a_landing_swaps_inside_a_state_folder_it_cannot_rename(self):
        # B594: the parent is root's on an installed machine, a mount point's
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
                           build_state_version=19, here_bare_metal=False)
        self.assertTrue(got.get("ok"), got)
        self.assertTrue((new_state / "users.json").is_file())
        self.assertTrue((Path(got["moved_aside"]) / "fresh.json").is_file(), "set aside, never deleted")
        self.assertEqual(Path(got["moved_aside"]).parent, new_state)

    def test_a_store_whose_path_cannot_be_made_lands_under_the_state(self):
        # B598: and the record stops naming the path.
        (self.state / "paths.json").write_text(json.dumps({"gitrelay": "/nowhere/gitrelay"}))
        r = move.prepare("user:ann", "https://new.example")
        new_state = self.tmp / "new-config"
        blocker = self.tmp / "a-file"
        blocker.write_text("not a folder")
        with mock.patch.object(move, "store_paths", lambda: {"gitrelay": str(blocker / "gitrelay")}):
            got = move.restore(str(self.tmp / "config" / "move" / r["bundle"]), r["token"], state_dir=new_state, workspace_dir=self.tmp / "new-ws",
                               secrets_dir=self.tmp / "new-secrets", build_state_version=19, here_bare_metal=False)
        self.assertTrue(got.get("ok"), got)
        self.assertTrue((new_state / "gitrelay" / "alpha.git" / "HEAD").is_file())
        self.assertNotIn("gitrelay", json.loads((new_state / "paths.json").read_text()))

    def test_a_state_this_build_no_longer_upgrades_from_is_refused(self):
        # B600: before it lands, not at the next start.
        r = move.prepare("user:ann", "https://new.example")
        with mock.patch.object(move.stateversion, "SUPPORTED_FROM", 99):
            got = self._land(self.tmp / "config" / "move" / r["bundle"], r["token"])
        self.assertIn("upgrades from 99 on", got.get("error", ""))

    def test_what_a_landing_sets_aside_is_never_carried(self):
        for name in (".moved-1", ".move-upload-2", ".reset-3"):
            (self.state / name).mkdir()
            (self.state / name / "big").write_text("x")
        move.prepare("user:ann", "https://new.example")
        import tarfile
        raw, _ = move.pack()
        with tarfile.open(fileobj=__import__("io").BytesIO(raw)) as t:
            self.assertEqual([n for n in t.getnames() if ".mov" in n or ".reset" in n], [])

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
        # The pull's proof (R175 step 5): refused after the move, so a
        # fresh old controller is armed for it.
        self.assertEqual(move.serve_fetch({"hash": th, "nonce": "n1", "proof": move.fetch_proof(key, "n1")})[2], 410)
        self.configure(self.state, bare=False)
        move.forget("user:ann") if not move.moved_to() else None
        state2 = self.tmp / "config2"
        shutil.copytree(self.state, state2, ignore=shutil.ignore_patterns("move.json", "move"))
        self.configure(state2, bare=False)
        r = move.prepare("user:ann", "")
        token, key, th = r["token"], move.key_of(r["token"]), move.token_hash(r["token"])
        self.assertEqual(move.serve_fetch({"hash": th, "nonce": "n1", "proof": "bad"})[2], 403)
        path, why, st = move.serve_fetch({"hash": th, "nonce": "n1", "proof": move.fetch_proof(key, "n1")})
        self.assertTrue(st == 200 and Path(path).is_file() and Path(path).name == move.status()["bundle"], (path, why))
        self.assertEqual(move.serve_fetch({"hash": th, "nonce": "n1", "proof": move.fetch_proof(key, "n1")})[2], 403, "a nonce is good once")
        self.assertEqual(self.audits[-1][0], "move-bundle-pulled")
        # The bundle is packed fresh: a record written after Prepare is in it.
        (state2 / "later.json").write_text("{}")
        path, why, st = move.serve_fetch({"hash": th, "nonce": "n2", "proof": move.fetch_proof(key, "n2")})
        m, _ = move.read_manifest(path)
        self.assertEqual(m["counts"]["state"], 3, "the record, the users and the later file")
        # The new side answering the old one's asking (R175 step 4), once
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
        # B728: root's folder on a machine of its own was walked as empty,
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
        # B619: an install keeps its key at secrets/install-key (lib/boot.sh);
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
        # B720: an install with no secrets folder keeps its key at
        # /config/.install-key (lib/boot.sh), which the state's walk packed.
        (self.state / ".install-key").mkdir()
        (self.state / ".install-key" / "key").write_bytes(b"k" * 32)
        for carry in (False, True):
            raw, counts = move.pack(carry_key=carry)
            names = tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz").getnames()
            self.assertFalse([n for n in names if ".install-key" in n], f"carry_key={carry}: the state's key folder stays out")
            self.assertEqual("install-key" in names, carry)

    def test_the_database_goes_as_a_snapshot_never_a_file_copy(self):
        # B720: the server writes its database all the while; a copy of the
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
