"""Moving a project's own container to another project (devapp.move_instance):
rekeyed under the new project with the compose name it
already had, so its containers, env file and data directory are untouched,
pinned to the node it is on, its owner and branch said for the new home."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import devactions  # noqa: E402
import devapp  # noqa: E402
import relocate  # noqa: E402


def write_json(p, d, mode=0o644):
    Path(p).write_text(json.dumps(d))


class Scripts(unittest.TestCase):
    """The pack and unpack scripts ride the plan's argv, where the agent
    rewrites the {cdir} placeholder wherever it stands: a variable of that
    name in the python pointed the helper's mount at the compose directory
    while the tar had gone into in/. And a failed stage's row says
    what the job last wrote, not where to look."""

    def test_the_scripts_never_spell_the_placeholder(self):
        for text in (relocate.PACK_PY, relocate.UNPACK_PY):
            self.assertNotIn("{cdir}", text)
            self.assertNotIn("cdir", text, "not even as a name, so an edit cannot bring it back")
        self.assertIn("filling the empty volume", relocate.UNPACK_PY, "an empty volume from a failed try is filled")
        self.assertIn("writing over what the volume", relocate.UNPACK_PY,
                      "one with files is written over, said in the log (the dialog warned; the operator, 14 Oct)")
        self.assertNotIn("remove it first", relocate.UNPACK_PY, "no longer refused")

    def test_a_failed_step_says_its_last_telling_line(self):
        """A compose step's row carries the last line that says something
        (the whole tail, newlines flattened, read as a wall)."""
        out = (" Network x_default Creating \n Network x_default Created \n Container x-db-1 Creating \n"
               " service:db:1 Error response from daemon: No such image: mariadb:11 \n Container x-web-1 Creating \n"
               "Error response from daemon: No such image: mariadb:11\n")
        self.assertEqual(devactions.last_line(out), "Error response from daemon: No such image: mariadb:11")
        self.assertEqual(devactions.last_line("$ docker compose up\n Container x Creating \n"), "Container x Creating",
                         "with nothing telling, the last line there is")
        self.assertEqual(devactions.last_line(""), "")
        # Docker's port refusal said whole, and a long line its end.
        self.assertEqual(devactions.last_line(
            "Error response from daemon: driver failed programming external connectivity on endpoint site-web-1 "
            "(3f1c2a9b8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b): Bind for 0.0.0.0:8381 failed: port is already allocated"),
            "port 8381 is already taken on the node (another container or program holds it): pick another port")
        long = "a" * 250 + " the reason"
        self.assertTrue(devactions.last_line(long).endswith("the reason") and len(devactions.last_line(long)) == 200)

    def test_a_failed_stage_carries_the_last_line_written(self):
        class Q:
            def job(self, jid, with_log=False):
                return {"id": jid, "log": "compose\n$ python3 -c\n    code\nmaking the volume x\ntar: can't open '/i/vol-0.tgz': No such file or directory\nTraceback (most recent call last):\n    more\n"}
        saved = devapp.queue
        devapp.queue = Q()
        try:
            self.assertEqual(relocate._last_said({"id": "j_1"}), "tar: can't open '/i/vol-0.tgz': No such file or directory")
        finally:
            devapp.queue = saved


class Move(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        ws = Path(self.tmp) / "ws"
        for p in ("MeadowPress-Dev", "MeadowPress", "Bare"):
            (ws / p).mkdir(parents=True)
        for p in ("MeadowPress-Dev", "MeadowPress"):
            (ws / p / "docker-compose.yml").write_text("services: {}\n")
        self.nodes = {"MeadowPress-Dev": ["n1"], "MeadowPress": ["n1"], "Bare": ["n1"], "Far": ["n2"]}
        devapp.configure(workspace=ws, state=self.tmp, write_json=write_json,
                         project_nodes=lambda p: self.nodes.get(p, []),
                         project_node=lambda p: (self.nodes.get(p) or [""])[0])
        write_json(devapp.FILE, {
            "MeadowPress-Dev": {"main": {"ref": "claude/aquilaelabs-links", "built_ref": "abc"}},
            "meadowpress-test-plex": {"main": {"source": "file", "for": "MeadowPress-Dev"}}})

    def test_it_keeps_its_name_env_and_data(self):
        was = (devapp._pname("MeadowPress-Dev"), devapp.env_path("MeadowPress-Dev"))
        r = devapp.move_instance("MeadowPress-Dev", "main", "MeadowPress")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual((r["instance"], r["name"], r["dropped_ref"]),
                         ("meadowpress-dev", "meadowpress-dev", "claude/aquilaelabs-links"))
        self.assertEqual((devapp._pname("MeadowPress", "meadowpress-dev"),
                          devapp.env_path("MeadowPress", "meadowpress-dev")), was)
        d = devapp._load()
        self.assertNotIn("MeadowPress-Dev", d)
        rec = d["MeadowPress"]["meadowpress-dev"]
        self.assertEqual(rec.get("node"), "n1", "pinned where its data is")
        self.assertNotIn("ref", rec)
        self.assertEqual(devapp.owner_of("MeadowPress", "meadowpress-dev"), "MeadowPress")
        self.assertEqual(devapp.compose_file("MeadowPress", "meadowpress-dev").parent.name, "MeadowPress")

    def test_what_it_refuses(self):
        self.assertIn("space picker", devapp.move_instance("meadowpress-test-plex", "main", "MeadowPress")["error"])
        self.assertIn("no compose file", devapp.move_instance("MeadowPress-Dev", "main", "Bare")["error"])
        self.assertIn("another space", devapp.move_instance("MeadowPress-Dev", "main", "MeadowPress-Dev")["error"])
        self.assertIn("no instance", devapp.move_instance("MeadowPress-Dev", "nope", "MeadowPress")["error"])
        (Path(self.tmp) / "ws" / "Far").mkdir()
        (Path(self.tmp) / "ws" / "Far" / "compose.yml").write_text("services: {}\n")
        self.assertIn("out of reach", devapp.move_instance("MeadowPress-Dev", "main", "Far")["error"])
        d = devapp._load()
        d["MeadowPress"] = {"meadowpress-dev": {}}
        write_json(devapp.FILE, d)
        self.assertIn("already has", devapp.move_instance("MeadowPress-Dev", "main", "MeadowPress")["error"])


if __name__ == "__main__":
    unittest.main()
