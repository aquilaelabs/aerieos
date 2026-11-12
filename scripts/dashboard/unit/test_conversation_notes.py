"""What a person says of their own conversations (R236, the operator, 12
Nov): a label and a note kept beside them, and Kept, a second name for a
conversation's file where its agent's own cleanup does not reach, so it is
still listed, read and fetched for a resume once the original has gone."""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import transcripts  # noqa: E402


class Notes(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.ws, self.st = self.tmp / "ws", self.tmp / "state"
        self.st.mkdir()
        self.homes = {u: self.tmp / "share" / u / "projects" for u in ("ann", "bob")}
        saved = {k: getattr(transcripts, k) for k in ("WORKSPACE", "WORKTREES", "root_for", "SHARED", "NOTES", "write_json")}
        self.addCleanup(lambda: [setattr(transcripts, k, v) for k, v in saved.items()])
        transcripts.configure(workspace=self.ws, root_for=lambda uid: self.homes[uid], state=self.st,
                              write_json=lambda p, d: Path(p).write_text(json.dumps(d)))
        self.old = time.time() - 3600
        for uid, sid, agent in (("ann", "ann-1", ""), ("ann", "ann-2", ""), ("ann", "ann-cx", "codex"), ("bob", "bob-1", "")):
            self.put(uid, sid, f"hello from {sid}", agent)

    def folder(self, uid, agent=""):
        d = self.homes[uid] / transcripts._slug(self.ws / "web")
        return d / agent if agent else d

    def put(self, uid, sid, words, agent="", when=None):
        d = self.folder(uid, agent)
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{sid}.jsonl"
        line = {"type": "user", "message": {"role": "user", "content": words}} if not agent else \
            {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": words}]}}
        f.write_text(json.dumps(line) + "\n")
        os.utime(f, (when or self.old, when or self.old))
        return f

    def row(self, uid, sid):
        return next((r for r in transcripts.mine(uid, ["web"]) if r["id"] == sid), None)

    def test_a_label_and_a_note_ride_the_list_and_are_the_accounts_own(self):
        self.assertEqual((self.row("ann", "ann-1")["label"], self.row("ann", "ann-1")["note"], self.row("ann", "ann-1")["kept"]), ("", "", False))
        r, st = transcripts.annotate("ann", "web", "ann-1", label="  Fix the\tlogin   page ")
        self.assertEqual((st, r["label"]), (200, "Fix the login page"), "one line, its spaces single")
        self.assertEqual(transcripts.annotate("ann", "web", "ann-1", note="left off at the token test\nnext: the upgrade suite")[1], 200)
        got = self.row("ann", "ann-1")
        self.assertEqual((got["label"], got["note"]), ("Fix the login page", "left off at the token test\nnext: the upgrade suite"))
        self.assertEqual(got["first"], "hello from ann-1", "its first words are still its own")
        self.assertEqual(self.row("ann", "ann-2")["label"], "")
        self.assertEqual(transcripts.annotate("bob", "web", "ann-1", label="mine now")[1], 404, "only its person's to name")
        self.assertEqual(self.row("ann", "ann-1")["label"], "Fix the login page")

    def test_a_label_is_cut_to_a_line_and_a_note_to_a_few(self):
        r, _ = transcripts.annotate("ann", "web", "ann-1", label="x" * 200, note="y" * 2000)
        self.assertEqual((len(r["label"]), len(r["note"])), (transcripts.LABEL_MAX, transcripts.NOTE_MAX))
        r, _ = transcripts.annotate("ann", "web", "ann-1", note="a\x00b\x1b[31mc")
        self.assertEqual(r["note"], "a b [31mc", "no control characters in what the page draws")

    def test_no_words_takes_a_label_off_and_nothing_said_leaves_no_record(self):
        transcripts.annotate("ann", "web", "ann-1", label="A name")
        self.assertEqual(transcripts.annotate("ann", "web", "ann-1", label="")[0]["label"], "")
        self.assertEqual(json.loads((self.st / "conversations.json").read_text()), {})

    def test_another_agents_conversation_is_labeled_the_same_way(self):
        self.assertEqual(transcripts.annotate("ann", "web", "ann-cx", label="The Codex one")[1], 200)
        got = self.row("ann", "ann-cx")
        self.assertEqual((got["agent"], got["label"]), ("codex", "The Codex one"))

    def test_a_shared_conversation_is_read_by_the_others_under_its_persons_label(self):
        transcripts.annotate("ann", "web", "ann-1", label="Release gate", note="for me alone")
        transcripts.set_shared("ann", "web", "ann-1", True)
        seen = transcripts.visible("bob", "web")
        self.assertEqual([(r["id"], r["label"]) for r in seen], [("ann-1", "Release gate")])
        self.assertNotIn("note", seen[0], "a note is its person's own")

    def kept_file(self, uid, sid, agent="claude"):
        return self.homes[uid].parent / "kept" / "web" / agent / f"{sid}.jsonl"

    def test_kept_is_a_second_name_that_outlives_the_first(self):
        self.assertEqual(transcripts.annotate("ann", "web", "ann-1", kept=True)[0]["kept"], True)
        k = self.kept_file("ann", "ann-1")
        self.assertTrue(k.is_file())
        self.assertTrue(k.samefile(self.folder("ann") / "ann-1.jsonl"), "one file under two names where the share allows")
        self.assertTrue(self.row("ann", "ann-1")["kept"])
        self.assertNotIn("gone", self.row("ann", "ann-1"))
        # The agent's own cleanup takes the first name away.
        (self.folder("ann") / "ann-1.jsonl").unlink()
        got = self.row("ann", "ann-1")
        self.assertEqual((got["kept"], got.get("gone"), got["first"]), (True, True, "hello from ann-1"))
        self.assertEqual(transcripts.raw("ann", "web", "ann-1"), k, "what a node's resume fetches, from the kept copy")
        self.assertEqual(transcripts.owner_of("ann", "web", "ann-1"), "ann")
        self.assertIsNone(self.row("ann", "ann-2").get("gone"))

    def test_one_not_kept_goes_with_its_file(self):
        transcripts.annotate("ann", "web", "ann-2", label="Not kept")
        (self.folder("ann") / "ann-2.jsonl").unlink()
        self.assertIsNone(self.row("ann", "ann-2"))

    def test_a_kept_copy_follows_an_original_written_anew(self):
        transcripts.annotate("ann", "web", "ann-cx", kept=True)
        k = self.kept_file("ann", "ann-cx", "codex")
        # Another agent's log is copied over at each stop: a new file under the old name.
        f = self.folder("ann", "codex") / "ann-cx.jsonl"
        f.unlink()
        self.put("ann", "ann-cx", "hello again, longer now", "codex", when=time.time() - 600)
        self.assertFalse(k.samefile(f))
        transcripts.mine("ann", ["web"])
        self.assertEqual(k.read_text(), f.read_text(), "a listing brings the kept copy up to its original")

    def test_where_a_link_cannot_be_made_it_is_a_copy(self):
        real = os.link
        self.addCleanup(setattr, os, "link", real)

        def no_link(*_a, **_k):
            raise OSError(18, "Invalid cross-device link")
        os.link = no_link
        self.assertEqual(transcripts.annotate("ann", "web", "ann-1", kept=True)[1], 200)
        k = self.kept_file("ann", "ann-1")
        self.assertTrue(k.is_file() and not k.samefile(self.folder("ann") / "ann-1.jsonl"))
        self.assertEqual(k.read_text(), (self.folder("ann") / "ann-1.jsonl").read_text())

    def test_unkeep_lets_the_copy_go_but_never_the_last_one(self):
        transcripts.annotate("ann", "web", "ann-1", kept=True)
        self.assertEqual(transcripts.annotate("ann", "web", "ann-1", kept=False)[0]["kept"], False)
        self.assertFalse(self.kept_file("ann", "ann-1").exists())
        self.assertTrue((self.folder("ann") / "ann-1.jsonl").is_file())
        transcripts.annotate("ann", "web", "ann-1", kept=True)
        (self.folder("ann") / "ann-1.jsonl").unlink()
        r, st = transcripts.annotate("ann", "web", "ann-1", kept=False)
        self.assertEqual(st, 409)
        self.assertIn("only one left", r["error"])
        self.assertTrue(self.kept_file("ann", "ann-1").is_file())

    def test_delete_takes_the_kept_copy_and_what_was_said_with_it(self):
        transcripts.annotate("ann", "web", "ann-1", label="Going", note="soon", kept=True)
        self.assertEqual(transcripts.delete("ann", "web", "ann-1")[1], 200)
        self.assertFalse(self.kept_file("ann", "ann-1").exists())
        self.assertIsNone(self.row("ann", "ann-1"))
        self.assertEqual(transcripts.notes_of("ann", "web"), {})
        # ...and one whose original had already gone.
        transcripts.annotate("ann", "web", "ann-2", kept=True)
        (self.folder("ann") / "ann-2.jsonl").unlink()
        self.assertEqual(transcripts.delete("ann", "web", "ann-2")[1], 200)
        self.assertIsNone(self.row("ann", "ann-2"))

    def test_each_accounts_kept_copies_are_its_own(self):
        transcripts.annotate("ann", "web", "ann-1", kept=True)
        self.assertIsNone(transcripts._kept_find("bob", "web", "ann-1"))
        self.assertEqual(transcripts.annotate("bob", "web", "ann-1", kept=True)[1], 404)


if __name__ == "__main__":
    unittest.main()
