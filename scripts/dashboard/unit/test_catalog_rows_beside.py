"""The catalog's newer rows reach a node as a file beside the shipped
catalog, and the three readers there take it.

The bundle carried config/toolchains.json rewritten with the vetted
catalog's newer rows, so the file a node read was never the one its release
shipped and no release could sign it. It goes as it is now, and the merged
rows ride as config/toolchains.catalog.json: aerie's shell half
(sdk.sh sdk_meta_file), its python half (sdkmeta.CATALOG) and the agent's own
reader (toolchains.read_catalog) read that file where it is there and the
shipped one where it is not. BB_TOOLCHAINS_JSON still names another catalog
outright."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "agent"))
sys.path.insert(0, os.path.join(REPO, "scripts", "lib"))
import sdkmeta  # noqa: E402
from aerieos_agent import toolchains as agent_toolchains  # noqa: E402

SHIPPED = {"toolchains": [{"name": "zig", "rev": 1}, {"name": "go", "rev": 1}]}
NEWER = {"toolchains": [{"name": "zig", "rev": 2}, {"name": "go", "rev": 1}]}


class Beside(unittest.TestCase):
    def setUp(self):
        # A bundle as a node unpacks it: scripts/lib with the two readers,
        # config/ with the shipped catalog.
        self.b = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.b, True)
        os.makedirs(os.path.join(self.b, "scripts", "lib"))
        os.makedirs(os.path.join(self.b, "config"))
        for name in ("sdkmeta.py", "sdk.sh", "common.sh"):
            shutil.copy(os.path.join(REPO, "scripts", "lib", name), os.path.join(self.b, "scripts", "lib"))
        self.shipped = os.path.join(self.b, "config", "toolchains.json")
        self.newer = os.path.join(self.b, "config", "toolchains.catalog.json")
        with open(self.shipped, "w") as f:
            json.dump(SHIPPED, f)

    def carry_newer(self, doc=NEWER):
        with open(self.newer, "w") as f:
            f.write(doc if isinstance(doc, str) else json.dumps(doc))

    def env(self, **more):
        return {**{k: v for k, v in os.environ.items() if k != "BB_TOOLCHAINS_JSON"}, "PATH": "/usr/bin:/bin",
                "BB_SCRIPTS": os.path.join(self.b, "scripts"), "BB_LIB": os.path.join(self.b, "scripts", "lib"), **more}

    def sh(self, script):
        lib = os.path.join(self.b, "scripts", "lib")
        r = subprocess.run(["bash", "-c", f'. "{lib}/common.sh"; . "{lib}/sdk.sh"; {script}'],
                           capture_output=True, text=True, env=self.env(), timeout=60, check=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def py(self, code, **more):
        r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import sdkmeta; " + code,
                            os.path.join(self.b, "scripts", "lib")], capture_output=True, text=True, env=self.env(**more),
                           timeout=60, check=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def revs(self, rows):
        return {r["name"]: r["rev"] for r in rows}

    def test_the_shell_half_reads_the_rows_beside_where_they_are(self):
        self.assertEqual(os.path.realpath(self.sh("sdk_meta_file")), os.path.realpath(self.shipped))
        self.carry_newer()
        self.assertEqual(os.path.realpath(self.sh("sdk_meta_file")), os.path.realpath(self.newer))
        self.assertEqual(self.sh("sdk_checkable").split(), ["zig", "go"], "and what reads the catalog through it still does")

    def test_the_python_half_reads_them_too_and_a_catalog_is_named_by_words(self):
        show = "import json; print(json.dumps([sdkmeta.CATALOG, sdkmeta.catalog()]))"
        path, rows = json.loads(self.py(show))
        self.assertEqual((os.path.realpath(path), self.revs(rows)), (os.path.realpath(self.shipped), {"zig": 1, "go": 1}))
        self.carry_newer()
        path, rows = json.loads(self.py(show))
        self.assertEqual((os.path.realpath(path), self.revs(rows)), (os.path.realpath(self.newer), {"zig": 2, "go": 1}))
        other = os.path.join(self.b, "other.json")
        with open(other, "w") as f:
            json.dump({"toolchains": [{"name": "fake", "rev": 9}]}, f)
        # An install's copy reads no catalog an environment names: it is
        # handed one as its first words, as held-run.sh hands it a row.
        path, rows = json.loads(self.py(show, BB_TOOLCHAINS_JSON=other))
        self.assertEqual(os.path.realpath(path), os.path.realpath(self.newer))
        r = subprocess.run([sys.executable, os.path.join(self.b, "scripts", "lib", "sdkmeta.py"), "--catalog", other, "names"],
                           capture_output=True, text=True, env=self.env(), timeout=60, check=False)
        self.assertEqual((r.returncode, r.stdout.split()), (0, ["fake"]), r.stderr)

    def test_the_file_is_chosen_by_what_is_beside_the_shipped_one(self):
        self.assertEqual(sdkmeta.catalog_file(self.shipped), self.shipped)
        self.carry_newer()
        self.assertEqual(sdkmeta.catalog_file(self.shipped), self.newer)
        # A controller's own install has no such file beside its catalog.
        self.assertFalse(os.path.exists(os.path.join(REPO, "config", sdkmeta.CATALOG_ROWS)))
        self.assertEqual(os.path.realpath(sdkmeta.CATALOG), os.path.realpath(os.path.join(REPO, "config", "toolchains.json")))

    def test_the_packs_beside_the_catalog_are_still_read(self):
        self.carry_newer()
        with open(os.path.join(self.b, "config", "toolpacks.json"), "w") as f:
            json.dump({"toolchains": [{"name": "hexkit", "rev": 1}]}, f)
        self.assertEqual(self.revs(sdkmeta.catalog_at(sdkmeta.catalog_file(self.shipped))), {"zig": 2, "go": 1, "hexkit": 1})
        self.assertEqual(self.revs(agent_toolchains.read_catalog(self.b)["toolchains"]), {"zig": 2, "go": 1, "hexkit": 1})

    def test_the_agent_reads_them_and_falls_back_to_the_shipped_file(self):
        self.assertEqual(self.revs(agent_toolchains.read_catalog(self.b)["toolchains"]), {"zig": 1, "go": 1})
        self.carry_newer()
        self.assertEqual(self.revs(agent_toolchains.read_catalog(self.b)["toolchains"]), {"zig": 2, "go": 1})
        self.carry_newer("{ not json")
        self.assertEqual(self.revs(agent_toolchains.read_catalog(self.b)["toolchains"]), {"zig": 1, "go": 1},
                         "rows that cannot be read leave the shipped ones")
        os.unlink(self.newer)
        os.unlink(self.shipped)
        self.assertEqual(agent_toolchains.read_catalog(self.b), {})


if __name__ == "__main__":
    unittest.main()
