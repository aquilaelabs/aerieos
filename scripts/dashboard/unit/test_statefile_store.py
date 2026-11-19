"""statefile.Store is one module's JSON object in a file of its own: load
answers {} for a file that is missing or holds anything but an object, a
module's validate and defaults shape the answer, the path and the writer are
asked on every call, and save moves the revision where write does not."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import statefile  # noqa: E402


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(statefile.end_request)
        self.file = self.tmp / "thing.json"

    def test_a_file_that_is_not_an_object_reads_as_empty(self):
        s = statefile.Store(lambda: self.file)
        self.assertEqual(s.load(), {})
        for text in ("{not json", "", "[1, 2]", "null", '"x"', "7"):
            self.file.write_text(text)
            self.assertEqual(s.load(), {}, text)
        self.file.write_bytes(b"\xff\xfe")
        self.assertEqual(s.load(), {})
        self.file.write_text('{"a": 1}')
        self.assertEqual(s.load(), {"a": 1})

    def test_defaults_fill_what_is_missing_in_their_order_and_are_never_shared(self):
        s = statefile.Store(lambda: self.file, defaults=lambda: {"first": {"on": False}, "second": {}})
        self.file.write_text('{"second": {"kept": 1}}')
        self.assertEqual(list(s.load().items()), [("second", {"kept": 1}), ("first", {"on": False})])
        self.file.unlink()
        self.assertEqual(list(s.load()), ["first", "second"])
        s.load()["second"]["mine"] = 1
        self.assertEqual(s.load()["second"], {})

    def test_validate_is_handed_a_dict_before_the_defaults(self):
        seen = []

        def shape(d):
            seen.append(dict(d))
            return d if isinstance(d.get("nodes"), dict) else {"nodes": {}}
        s = statefile.Store(lambda: self.file, validate=shape, defaults=lambda: {"ips": {}})
        self.file.write_text("[]")
        self.assertEqual(s.load(), {"nodes": {}, "ips": {}})
        self.file.write_text('{"nodes": {"n1": {}}, "other": 1}')
        self.assertEqual(s.load(), {"nodes": {"n1": {}}, "other": 1, "ips": {}})
        self.assertEqual(seen, [{}, {"nodes": {"n1": {}}, "other": 1}])

    def test_the_path_and_the_writer_are_asked_on_every_call(self):
        where, wrote = {"f": self.file}, []
        writer = {"fn": lambda p, d: wrote.append(("first", Path(p).name, d))}
        s = statefile.Store(lambda: where["f"], write=lambda: writer["fn"])
        s.save({"a": 1})
        where["f"] = self.tmp / "elsewhere.json"
        writer["fn"] = lambda p, d: wrote.append(("second", Path(p).name, d))
        s.save({"b": 2})
        self.assertEqual(wrote, [("first", "thing.json", {"a": 1}), ("second", "elsewhere.json", {"b": 2})])
        where["f"].write_text('{"c": 3}')
        self.assertEqual(s.load(), {"c": 3})

    def test_the_write_is_statefiles_own_with_the_files_mode(self):
        plain, private = statefile.Store(lambda: self.file), statefile.Store(lambda: self.tmp / "keys.json", mode=0o600)
        plain.save({"a": 1})
        private.save({"k": "v"})
        self.assertEqual(self.file.read_text(), json.dumps({"a": 1}, indent=2) + "\n")
        self.assertEqual(self.file.stat().st_mode & 0o7777, 0o644)
        self.assertEqual((self.tmp / "keys.json").stat().st_mode & 0o7777, 0o600)
        asked = []
        statefile.Store(lambda: self.file, write=lambda: lambda p, d, **kw: asked.append(kw)).save({})
        statefile.Store(lambda: self.file, write=lambda: lambda p, d, **kw: asked.append(kw), mode=0o600).save({})
        self.assertEqual(asked, [{}, {"mode": 0o600}], "a writer is handed a mode only where the file has one")

    def test_a_save_moves_the_revision_and_a_write_does_not(self):
        s = statefile.Store(lambda: self.file)
        self.assertEqual(s.rev(), 0)
        s.save({"a": 1})
        self.assertEqual(s.rev(), 1)
        s.write({"a": 2})
        self.assertEqual((s.rev(), s.load()), (1, {"a": 2}))
        s.bump()
        self.assertEqual(s.rev(), 2)

        def full(p, d):
            raise OSError(28, "No space left on device")
        failing = statefile.Store(lambda: self.file, write=lambda: full)
        with self.assertRaises(OSError):
            failing.save({"a": 3})
        self.assertEqual(failing.rev(), 0, "a save that did not land moves nothing")

    def test_only_a_cached_store_keeps_a_requests_look_at_the_file(self):
        own, kept = statefile.Store(lambda: self.file), statefile.Store(lambda: self.file, cached=True)
        self.file.write_text('{"n": 1}')
        statefile.begin_request()
        self.assertEqual((own.load(), kept.load()), ({"n": 1}, {"n": 1}))
        self.file.write_text('{"n": 2, "more": true}')                 # another process, not through statefile
        self.assertEqual(own.load(), {"n": 2, "more": True})
        self.assertEqual(kept.load(), {"n": 1}, "a request is one moment")
        kept.save({"n": 3})
        self.assertEqual(kept.load(), {"n": 3}, "this thread's own save is read at once")
        statefile.end_request()


if __name__ == "__main__":
    unittest.main()
