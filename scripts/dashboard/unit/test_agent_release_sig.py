"""An agent update is AerieOS's own release where the node pinned the
release key (R227 step 1): taken with a signature under that key over its
digest, refused without one, taken unsigned only where the node's console
said so, and taken as before by a node that pinned nothing. The console's
choices outlive the running agent's own writes of node.json."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "agent"))
from aerieos_agent import release, stores  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

DIGEST = "sha256:" + "ab" * 32


def pair():
    k = Ed25519PrivateKey.generate()
    return k, k.public_key().public_bytes_raw().hex()


class Verify(unittest.TestCase):
    def test_the_release_keys_signature_over_the_digest_passes(self):
        k, pub = pair()
        sig = k.sign(release.MESSAGE + DIGEST.encode()).hex()
        self.assertEqual(release.verify(pub, DIGEST, sig), "")
        ok, said = release.may_install({"release_key": pub}, DIGEST, sig)
        self.assertTrue(ok)
        self.assertIn("signed by the release key", said)

    def test_another_key_another_digest_or_no_signature_does_not(self):
        k, pub = pair()
        other, _ = pair()
        sig = k.sign(release.MESSAGE + DIGEST.encode()).hex()
        self.assertIn("not the pinned release key's", release.verify(pub, DIGEST, other.sign(release.MESSAGE + DIGEST.encode()).hex()))
        self.assertIn("not the pinned release key's", release.verify(pub, "sha256:" + "cd" * 32, sig))
        self.assertIn("no signature", release.verify(pub, DIGEST, ""))
        self.assertIn("not the pinned", release.verify(pub, DIGEST, k.sign(DIGEST.encode()).hex()), "a signature of the bare digest is not this one")

    def test_a_pinned_node_refuses_an_unsigned_update_unless_its_console_allows(self):
        _, pub = pair()
        ok, said = release.may_install({"release_key": pub}, DIGEST, "")
        self.assertFalse(ok)
        self.assertRegex(said, r"sudo (aerieos|builderbot)-agent unsigned on")
        ok, said = release.may_install({"release_key": pub, "unsigned_ok": True}, DIGEST, "")
        self.assertTrue(ok)
        self.assertIn("console allows unsigned", said)

    def test_an_update_signed_by_the_spare_is_taken_as_one_signed_by_the_key(self):
        # R232: the key the builds sign with is lost or replaced, the spare
        # signs in its place, and no node is cut off.
        k, pub = pair()
        s, spare = pair()
        other, _ = pair()
        state = {"release_key": pub, "release_spare": spare}
        self.assertEqual(release.keys(state), [pub, spare])
        for signer, words in ((k, "signed by the release key"), (s, "signed by the spare release key")):
            ok, said = release.may_install(state, DIGEST, signer.sign(release.MESSAGE + DIGEST.encode()).hex())
            self.assertTrue(ok, said)
            self.assertIn(words, said)
        # A third key's is refused, naming both that are pinned.
        ok, said = release.may_install(state, DIGEST, other.sign(release.MESSAGE + DIGEST.encode()).hex())
        self.assertFalse(ok)
        self.assertIn(pub[:16], said)
        self.assertIn(f"or its spare ({spare[:16]}", said)
        # A node that pinned no spare takes nothing the spare signed.
        ok, _said = release.may_install({"release_key": pub}, DIGEST, s.sign(release.MESSAGE + DIGEST.encode()).hex())
        self.assertFalse(ok)
        # ...and a spare alone still pins the node: nothing unsigned gets in.
        self.assertFalse(release.may_install({"release_spare": spare}, DIGEST, "")[0])

    def test_a_key_and_its_spare_are_read_as_one_word(self):
        _, a = pair()
        _, b = pair()
        _, c = pair()
        self.assertEqual(release.clean_keys(a), [a])
        self.assertEqual(release.clean_keys(f"{a},{b}"), [a, b])
        self.assertEqual(release.clean_keys(f"{a},{a}"), [a])
        for bad in ("", "nope", f"{a},nope", f"{a},{b},{c}"):
            self.assertEqual(release.clean_keys(bad), [], bad)

    def test_a_node_that_pinned_nothing_updates_as_before(self):
        self.assertEqual(release.may_install({}, DIGEST, ""), (True, ""))
        self.assertEqual(release.may_install({"release_key": "not a key"}, DIGEST, ""), (True, ""))


class Console(unittest.TestCase):
    def test_what_the_console_wrote_outlives_the_agents_own_save(self):
        d = tempfile.mkdtemp()
        was = stores.NODE_JSON
        stores.NODE_JSON = os.path.join(d, "node.json")
        self.addCleanup(setattr, stores, "NODE_JSON", was)
        running = {"node_id": "n_1", "token": "bbn_old"}                # the agent's copy, from before
        stores.save_state(dict(running), console=True)
        _, pub = pair()
        stores.save_state({"node_id": "n_1", "token": "bbn_old", "release_key": pub, "unsigned_ok": True}, console=True)
        stores.save_state(dict(running, token="bbn_new"))               # a token handed over: the agent writes its copy
        got = json.load(open(stores.NODE_JSON))
        self.assertEqual((got["token"], got["release_key"], got["unsigned_ok"]), ("bbn_new", pub, True))
        stores.save_state({"node_id": "n_1", "token": "bbn_new", "release_key": pub}, console=True)   # unsigned off, at the console
        stores.save_state(dict(running, token="bbn_3", unsigned_ok=True))                             # a stale copy cannot put it back
        self.assertNotIn("unsigned_ok", json.load(open(stores.NODE_JSON)))
        self.assertEqual(stores.console_said(), {"release_key": pub})
        # The spare is the console's too: the agent's own save keeps it, and cannot add one.
        _, spare = pair()
        stores.save_state({"node_id": "n_1", "token": "bbn_3", "release_key": pub, "release_spare": spare}, console=True)
        stores.save_state(dict(running, token="bbn_4"))
        self.assertEqual(stores.console_said(), {"release_key": pub, "release_spare": spare})
        stores.save_state({"node_id": "n_1", "token": "bbn_4", "release_key": pub}, console=True)
        stores.save_state(dict(running, token="bbn_5", release_spare=spare))
        self.assertEqual(stores.console_said(), {"release_key": pub})


class Enrolling(unittest.TestCase):
    def test_the_key_is_pinned_though_the_census_writes_the_record_midway(self):
        # Met on the dev node, 10 Nov: the census a node takes while it
        # enrolls saved the record (its check for the system's updates), on
        # a machine whose record held no key yet, and the key the enrollment
        # was pinning went with the file's own word for it.
        from aerieos_agent import cli, power
        d = tempfile.mkdtemp()
        was = (stores.NODE_JSON, cli.Controller, cli.census, cli.make_store, cli.store_path_ok)
        self.addCleanup(lambda: (setattr(stores, "NODE_JSON", was[0]), setattr(cli, "Controller", was[1]), setattr(cli, "census", was[2]),
                                 setattr(cli, "make_store", was[3]), setattr(cli, "store_path_ok", was[4])))
        stores.NODE_JSON = os.path.join(d, "node.json")
        json.dump({"node_id": "n_1", "token": "bbn_old", "stores": {}}, open(stores.NODE_JSON, "w"))

        class Ctl:
            CA = "ca"

            def __init__(self, url, token, pin):
                self.url, self.host, self.scheme = url, "h", "http"

            def call(self, verb, body, timeout=30):
                return 200, {"node_id": "n_1", "token": "bbn_x", "name": "box", "capabilities": []}

        def census(state):
            stores.save_state(state)            # as a census that writes midway did
            return {}
        cli.Controller, cli.census, cli.make_store, cli.store_path_ok = Ctl, census, lambda p: {}, lambda p: ""
        _, pub = pair()
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            cli.cmd_enroll(["--controller", "http://c", "--token", "bbe_t", "--release-key", pub])
        self.assertEqual(json.load(open(stores.NODE_JSON)).get("release_key"), pub)
        # The Enroll script carries the spare after a comma (R232): both are
        # pinned, and a script that names the key alone drops the spare.
        _, spare = pair()
        with contextlib.redirect_stdout(io.StringIO()) as out:
            cli.cmd_enroll(["--controller", "http://c", "--token", "bbe_t", "--release-key", f"{pub},{spare}"])
        got = json.load(open(stores.NODE_JSON))
        self.assertEqual((got.get("release_key"), got.get("release_spare")), (pub, spare))
        self.assertIn("and its spare", out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()):
            cli.cmd_enroll(["--controller", "http://c", "--token", "bbe_t"])
        got = json.load(open(stores.NODE_JSON))
        self.assertEqual((got.get("release_key"), got.get("release_spare")), (pub, spare), "an enrollment naming none keeps what was pinned")
        with contextlib.redirect_stdout(io.StringIO()):
            cli.cmd_enroll(["--controller", "http://c", "--token", "bbe_t", "--release-key", pub])
        self.assertNotIn("release_spare", json.load(open(stores.NODE_JSON)))
        with self.assertRaises(SystemExit):
            cli.cmd_enroll(["--controller", "http://c", "--token", "bbe_t", "--release-key", f"{pub},nope"])
        # ...and the check for updates no longer writes a record that is not a node's yet.
        saved = []
        w = (power.save_state, power.shutil.which, power.os.geteuid, power.os_release, power._out)
        self.addCleanup(lambda: (setattr(power, "save_state", w[0]), setattr(power.shutil, "which", w[1]), setattr(power.os, "geteuid", w[2]),
                                 setattr(power, "os_release", w[3]), setattr(power, "_out", w[4])))
        power.save_state = saved.append
        power.shutil.which = lambda name: "/usr/bin/apt-get"
        power.os.geteuid = lambda: 0
        power.os_release = lambda: ""
        power._out = lambda *a, **k: "0 upgraded, 0 newly installed"
        power.host_updates_now({"stores": {}})
        self.assertEqual(saved, [], "no id yet: nothing written")
        power.host_updates_now({"node_id": "n_1"})
        self.assertEqual(len(saved), 1)


class Signer(unittest.TestCase):
    """tools/sign-agent.py signs this tree's agent, and what it writes passes."""
    def test_what_the_build_signs_is_what_a_node_checks(self):
        tool = os.path.join(HERE, "..", "..", "..", "tools", "sign-agent.py")
        sig = os.path.join(HERE, "..", "..", "agent", "agent.sig")
        had = open(sig).read() if os.path.exists(sig) else None
        self.addCleanup(lambda: open(sig, "w").write(had) if had is not None else (os.path.exists(sig) and os.unlink(sig)))
        k, pub = pair()
        # A key of the test's own, named as the committed file names the real one.
        d = tempfile.mkdtemp()
        mine = os.path.join(d, "release.pub")
        open(mine, "w").write(f"# a test's key\naerieos-release-ed25519 {pub}\n")
        env = dict(os.environ, AERIEOS_RELEASE_PUB=mine)
        r = subprocess.run([sys.executable, tool], env=dict(env, AERIEOS_RELEASE_KEY=k.private_bytes_raw().hex()),
                           capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        got = json.load(open(sig))
        self.assertEqual(got["key"], pub)
        self.assertEqual(release.verify(pub, got["digest"], got["sig"]), "")
        r = subprocess.run([sys.executable, tool, "--check"], env=env, capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(r.returncode, 0, r.stdout)
        # A key that is not the one the file names signs nothing: nodes
        # pinned to the named one would refuse what it signed.
        os.unlink(sig)
        other, _ = pair()
        r = subprocess.run([sys.executable, tool], env=dict(env, AERIEOS_RELEASE_KEY=other.private_bytes_raw().hex()),
                           capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(r.returncode, 2)
        self.assertFalse(os.path.exists(sig))
        r = subprocess.run([sys.executable, tool], env={k2: v for k2, v in env.items() if k2 != "AERIEOS_RELEASE_KEY"},
                           capture_output=True, text=True, timeout=60, check=False)
        self.assertIn("ships unsigned", r.stdout)
        # Named on the file's second line, that other key is the spare
        # (R232): a build may sign with it, and the check passes under it.
        open(mine, "a").write(f"aerieos-release-ed25519 {other.public_key().public_bytes_raw().hex()}\n")
        r = subprocess.run([sys.executable, tool], env=dict(env, AERIEOS_RELEASE_KEY=other.private_bytes_raw().hex()),
                           capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("with the spare release key", r.stdout)
        r = subprocess.run([sys.executable, tool, "--check"], env=env, capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_the_enroll_script_carries_the_key_and_its_spare(self):
        sys.path.insert(0, os.path.join(HERE, ".."))
        import enrollscript
        _, a = pair()
        _, b = pair()
        _, c = pair()
        d = tempfile.mkdtemp()
        was = enrollscript.RELEASE_PUB
        self.addCleanup(setattr, enrollscript, "RELEASE_PUB", was)
        enrollscript.RELEASE_PUB = os.path.join(d, "release.pub")
        for lines, want in (([a], [a]), ([a, b], [a, b]), ([a, a], [a]), ([a, b, c], []), ([a, "nope"], []), ([], [])):
            open(enrollscript.RELEASE_PUB, "w").write("# the keys\n" + "".join(f"aerieos-release-ed25519 {k}\n" for k in lines))
            self.assertEqual(enrollscript.release_keys(), want, lines)
            self.assertEqual(enrollscript.release_key(), (want or [""])[0])
            self.assertEqual(release.clean_keys(",".join(want)), want)

    def test_the_committed_key_is_one_a_node_can_pin(self):
        sys.path.insert(0, os.path.join(HERE, ".."))
        import enrollscript
        key = enrollscript.release_key()
        self.assertEqual(release.clean_key(key), key)
        self.assertTrue(key, "the repository names AerieOS's release key")


if __name__ == "__main__":
    unittest.main()
