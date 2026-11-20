"""Release signing (R199): a release's SHA256SUMS, signed by a key the install
already holds, is what a file is taken on, so whoever changes the
repository or a release can build one, attest it and put a sha256 beside
it, and still not hand it to an install. The namespace a signer is named
for says the channel: the key the release build holds signs dev builds,
which publish by themselves, and a stable release takes its own key's
signature alone.

Four verifiers follow the one rule, each in its own code because of where it
runs: the OS updater (the agent's osimage.py, online and from a folder), the
installer's fetch_tree (shell), the stick maker (one file a person
downloads) and the Library's downloads (apps.py). Here each is run against
the same table of cases, with real keys and real signatures made by
ssh-keygen in a temporary folder, and must give the table's verdict in the
table's words."""
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import agentpkg  # noqa: E402
import apps  # noqa: E402
import releasecheck  # noqa: E402
import test_osimage  # noqa: E402  (its World: an AerieOS machine in a folder)

INSTALLER = os.path.join(ROOT, "nodes", "install-controller.sh")
osimage = agentpkg.load("aerieos_agent_signing").module("osimage")
spec = importlib.util.spec_from_file_location("bbstick_signing", os.path.join(ROOT, "tools", "aerieos-stick.py"))
stick = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stick)

REL, DEV = "aerieos-release", "aerieos-dev"
PRE, STABLE = "v0.9.1-dev.7", "v0.9.1"
KEYS = {}


def setUpModule():
    """Three keys: a stable release's, the release build's, and one no
    install names."""
    if not shutil.which("ssh-keygen"):
        return
    d = tempfile.mkdtemp()
    unittest.addModuleCleanup(shutil.rmtree, d, True)
    for who in ("release", "dev", "stranger"):
        path = os.path.join(d, who)
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", who, "-f", path], check=True,
                       stdin=subprocess.DEVNULL, timeout=30)
        with open(path + ".pub", encoding="utf-8") as f:
            kt, kb = f.read().split()[:2]
        KEYS[who] = (path, f"{kt} {kb}")


def line(who, ns):
    """A signer's line as config/release-signers holds it; the stable
    signer's with the comment tools/release-sign.py key prints after it."""
    return f'{ns} namespaces="{ns}" {KEYS[who][1]}' + (f" {ns}" if ns == REL else "")


class Case:
    """One row of the table: the release's tag, the signers the install
    names, who signed the list and in which namespace (None: the release
    carries no list), what the list says of the file, and the verdict."""
    def __init__(self, name, tag, signers, signed, taken, says, lists="the file", changed=False):
        self.name, self.tag, self.signers, self.signed = name, tag, signers, signed
        self.taken, self.says, self.lists, self.changed = taken, says, lists, changed

    def lines(self):
        return [line(who, ns) for who, ns in self.signers]

    def publish(self, where, name, digest):
        """The release's SHA256SUMS and its signature in the folder `where`,
        for the file `name` whose bytes hash to `digest`."""
        if self.signed is None:
            return
        rows = {"the file": [f"{digest}  {name}", "c" * 64 + "  another-file.bin"],
                "other bytes": ["b" * 64 + f"  {name}"],
                "not the file": ["c" * 64 + "  another-file.bin"]}[self.lists]
        sums = os.path.join(where, "SHA256SUMS")
        with open(sums, "w", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
        who, ns = self.signed
        subprocess.run(["ssh-keygen", "-Y", "sign", "-q", "-f", KEYS[who][0], "-n", ns, sums], check=True,
                       stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
        if self.changed:
            with open(sums, "a", encoding="utf-8") as f:
                f.write("d" * 64 + "  slipped-in.bin\n")


BOTH = (("dev", DEV), ("release", REL))
TABLE = [
    Case("a dev build signed by the release build's key", PRE, BOTH, ("dev", DEV), True, "the key AerieOS's dev builds are signed with"),
    Case("a dev build signed by the stable key", PRE, BOTH, ("release", REL), True, "AerieOS's release key"),
    Case("a stable release signed by the release build's key", STABLE, BOTH, ("dev", DEV), False,
         "its list is signed by the key dev builds are signed with"),
    Case("a stable release signed by the stable key", STABLE, BOTH, ("release", REL), True, "AerieOS's release key"),
    Case("a stable release while no stable signer is named", STABLE, (("dev", DEV),), ("release", REL), False,
         "no stable signer is named yet"),
    Case("a release with no signed list, the install naming a signer", PRE, BOTH, None, False, "made before releases were signed"),
    Case("a release with no signed list, the install naming no signer", PRE, (), None, True, "signature is not checked"),
    Case("a list signed by a key the install does not name", PRE, BOTH, ("stranger", DEV), False, "signed by no key"),
    Case("the release build's key signing as the stable key", STABLE, BOTH, ("dev", REL), False, "signed by no key"),
    Case("a list changed after it was signed", PRE, BOTH, ("dev", DEV), False, "signed by no key", changed=True),
    Case("a file whose bytes are not the list's, its sha256 beside it matching", PRE, BOTH, ("dev", DEV), False,
         "is not the file", lists="other bytes"),
    Case("a file the list does not name", PRE, BOTH, ("dev", DEV), False, "is not in the list of files", lists="not the file"),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Table(unittest.TestCase):
    """What each verifier's test class shares: a folder, and the table run
    through `verdict(case)`, which answers (taken, what was said)."""
    def setUp(self):
        if not KEYS:
            self.skipTest("no ssh-keygen here")
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.n = 0

    def fresh(self):
        self.n += 1
        d = os.path.join(self.d, str(self.n))
        os.makedirs(d)
        return d

    def signers_file(self, case, d):
        path = os.path.join(d, "release-signers")
        with open(path, "w", encoding="utf-8") as f:
            f.write("# who may sign a release\n" + "".join(ln + "\n" for ln in case.lines()))
        return path

    def run_table(self):
        for case in TABLE:
            with self.subTest(case.name):
                taken, said = self.verdict(case)
                self.assertEqual(taken, case.taken, f"{case.name}: {said}")
                self.assertIn(case.says, said, case.name)


class TheOsUpdater(Table):
    """osimage.py: a release named by its tag, and a folder with its files."""
    def setUp(self):
        super().setUp()
        real = osimage.shutil.which
        gh = os.path.join(self.d, "gh")
        with open(gh, "w") as f:
            f.write('#!/bin/sh\necho "gh $*"\nexit 0\n')
        os.chmod(gh, stat.S_IRWXU)
        p = mock.patch.object(osimage.shutil, "which", side_effect=lambda n: gh if n == "gh" else real(n))
        p.start()
        self.addCleanup(p.stop)

        class A(osimage.OsImageMixin):
            def _sh(self, job, argv, timeout=0, **kw):
                # mount needs root: the test's ISO is a tar, unpacked where
                # it would be mounted (test_osimage.py).
                if argv[0] == "mount":
                    with tarfile.open(argv[-2]) as t:
                        t.extractall(argv[-1], filter="data")
                    return 0
                if argv[0] == "umount":
                    return 0
                r = subprocess.run(argv, capture_output=True, text=True, check=False)
                job.say(r.stdout + r.stderr)
                return r.returncode

            def hello_again(self, why):
                pass
        self.A = A

    def update(self, case, folder):
        w = test_osimage.World(slot="a")
        self.addCleanup(shutil.rmtree, w.d, True)
        ver = case.tag[1:]
        d, _ = w.publish(ver)
        with open(os.path.join(d, f"aerieos-os-{ver}.iso"), "rb") as f:
            digest = sha(f.read())
        case.publish(d, f"aerieos-os-{ver}.iso", digest)
        env = dict(w.env, BB_RELEASE_SIGNERS=self.signers_file(case, w.d))
        job = test_osimage.Job()
        with mock.patch.dict(os.environ, env):
            state, _ = self.A()._apply_os_update(job, {"from": d} if folder else {"release": case.tag})
        with open(w.dev["b"], "rb") as f:
            written = f.read() != b"\0" * 4096
        self.assertEqual(written, state == "succeeded", "a refused update writes nothing to the other slot")
        return state == "succeeded", job.text()

    def test_a_release_named_by_its_tag(self):
        self.verdict = lambda case: self.update(case, False)
        self.run_table()

    def test_a_folder_with_the_releases_files(self):
        self.verdict = lambda case: self.update(case, True)
        self.run_table()

    def test_a_release_it_may_not_take_is_refused_before_the_image_is_fetched(self):
        # Every release from before releases were signed is one: said in a
        # moment, not after the image's download.
        case = TABLE[5]
        taken, said = self.update(case, False)
        self.assertFalse(taken)
        self.assertNotIn("fetching", said)
        self.assertNotIn("matches its sha256", said)


class TheInstaller(Table):
    """install-controller.sh's fetch_tree, its own lines under bash, with
    curl and gh stood in on the PATH."""
    def verdict(self, case):
        d = self.fresh()
        ver = case.tag[1:]
        tree = os.path.join(d, "t", "aerieos-9")
        os.makedirs(os.path.join(tree, "nodes"))
        for rel, text in (("Dockerfile", "FROM x\n"), ("nodes/install-controller.sh", "#!/bin/sh\n")):
            with open(os.path.join(tree, rel), "w") as f:
                f.write(text)
        served = os.path.join(d, "release")
        os.makedirs(served)
        name = f"aerieos-controller-{ver}.tar.gz"
        tgz = os.path.join(served, name)
        with tarfile.open(tgz, "w:gz") as t:
            t.add(tree, arcname="aerieos-9")
        with open(tgz, "rb") as f:
            digest = sha(f.read())
        with open(tgz + ".sha256", "w") as f:
            f.write(f"{digest}  {name}\n")
        case.publish(served, name, digest)
        bin_ = os.path.join(d, "bin")
        os.makedirs(bin_)
        # A curl that serves the release's folder by a file's name, and
        # answers 404 as curl -f does for one that is not there.
        with open(os.path.join(bin_, "curl"), "w") as f:
            f.write(f"""#!/bin/bash
out=""; url=""; w=""
while [ $# -gt 0 ]; do case "$1" in -o) out="$2"; shift 2;; -w) w="$2"; shift 2;; -H) shift 2;; -*) shift;; *) url="$1"; shift;; esac; done
case "$url" in *attestations/sha256:*) echo '{{"attestations":[{{"bundle":{{"x":1}}}}]}}' > "$out"; exit 0;; esac
f="{served}/${{url##*/}}"
if [ -f "$f" ]; then cp "$f" "$out"; [ -z "$w" ] || printf 200; exit 0; fi
[ -z "$w" ] || printf 404
exit 22
""")
        with open(os.path.join(bin_, "gh"), "w") as f:
            f.write('#!/bin/bash\n[ "$3" = --help ] && { echo "  -b, --bundle string"; exit 0; }\nexit 0\n')
        for n in ("curl", "gh"):
            os.chmod(os.path.join(bin_, n), 0o755)
        pre = f'set -euo pipefail\nBB_CONTROLLER_LIB=1 . "{INSTALLER}"\n'
        env = dict(os.environ, BB_INSTALL_ROOT=d, NO_FETCH="1", PATH=bin_ + ":" + os.environ["PATH"],
                   BB_RELEASE_SIGNERS=self.signers_file(case, d))
        r = subprocess.run(["bash", "-c", pre + f"fetch_tree {case.tag}"], capture_output=True, text=True, timeout=120,
                           check=False, env=env)
        if r.returncode == 0:
            self.assertTrue(os.path.isfile(os.path.join(r.stdout, "Dockerfile")), "a bundle taken is unpacked and its tree named")
        return r.returncode == 0, r.stderr

    def test_the_bundle_an_update_fetches(self):
        self.run_table()

    def test_the_signers_are_the_running_releases_own_outside_the_tests(self):
        # The file named in the environment is read only under the unit
        # tests' prefix; a real run reads the tree the script is in.
        r = subprocess.run(["bash", "-c", f'BB_CONTROLLER_LIB=1 . "{INSTALLER}"; printf %s "$SIGNERS"'], capture_output=True,
                           text=True, timeout=30, check=False,
                           env={k: v for k, v in dict(os.environ, BB_RELEASE_SIGNERS="/tmp/other").items() if k != "BB_INSTALL_ROOT"})
        self.assertEqual(r.stdout, os.path.join(ROOT, "config", "release-signers"), r.stderr)


class TheStickMaker(Table):
    """tools/aerieos-stick.py: a release's image fetched, and an image file
    a person has."""
    def world(self, case):
        d = self.fresh()
        name = f"aerieos-os-{case.tag[1:]}.stick.raw.xz"
        served = os.path.join(d, "release")
        os.makedirs(served)
        with open(os.path.join(served, name), "wb") as f:
            f.write(b"the stick's image")
        with open(os.path.join(served, name + ".sha256"), "w") as f:
            f.write(sha(b"the stick's image") + f"  {name}\n")
        case.publish(served, name, sha(b"the stick's image"))
        said = []

        def fetch(url, dest, say_progress=True):
            src = os.path.join(served, url.rsplit("/", 1)[1])
            if not os.path.isfile(src):
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
            shutil.copyfile(src, dest)

        def die(s):
            raise SystemExit(s)
        patches = mock.patch.multiple(stick, RELEASE_SIGNERS="\n" + "".join(ln + "\n" for ln in case.lines()), fetch=fetch,
                                      say=said.append, die=die, attested=lambda path: None)
        return d, served, name, said, patches

    def fetched(self, case):
        d, _, name, said, patches = self.world(case)
        was = os.getcwd()
        os.chdir(d)                 # an image is fetched beside where the tool runs
        try:
            with patches:
                stick.release_image(case.tag)
        except SystemExit as e:
            return False, str(e)
        finally:
            os.chdir(was)
        return os.path.isfile(os.path.join(d, name)), "\n".join(said)

    def a_file(self, case):
        _, served, name, said, patches = self.world(case)
        path = os.path.join(served, name)
        try:
            with patches:
                stick.signed(stick.tag_of(path), path)
        except SystemExit as e:
            return False, str(e)
        return True, "\n".join(said)

    def test_a_releases_image_fetched(self):
        self.verdict = self.fetched
        self.run_table()

    def test_an_image_file_a_person_has(self):
        self.verdict = self.a_file
        self.run_table()

    def test_a_release_it_may_not_write_is_refused_before_the_image_is_fetched(self):
        d, _, name, said, patches = self.world(TABLE[5])
        was = os.getcwd()
        os.chdir(d)
        try:
            with patches, self.assertRaises(SystemExit):
                stick.release_image(TABLE[5].tag)
        finally:
            os.chdir(was)
        self.assertFalse(os.path.exists(os.path.join(d, name)))
        self.assertFalse([s for s in said if "fetching" in s])

    def test_an_image_is_held_to_the_release_workflows_identity(self):
        img = os.path.join(self.d, "aerieos-os-1.0.0.stick.raw.xz")
        with open(img, "wb") as f:
            f.write(b"image")
        gh = os.path.join(self.d, "gh")
        with open(gh, "w") as f:
            f.write(f'#!/bin/sh\necho "$*" > "{self.d}/gh.log"\nexit 0\n')
        os.chmod(gh, stat.S_IRWXU)
        answer = json.dumps({"attestations": [{"bundle": {"x": 1}}]}).encode()
        import io
        with mock.patch.object(stick.shutil, "which", return_value=gh), mock.patch.object(stick, "say"), \
                mock.patch.object(stick.urllib.request, "urlopen", return_value=io.BytesIO(answer)):
            stick.attested(img)
        with open(os.path.join(self.d, "gh.log")) as f:
            self.assertIn("--cert-identity-regex " + stick.SIGNER_IDENTITY, f.read())


class TheLibrarysDownloads(Table):
    """apps.py: the Android app from the release that matches the controller."""
    def verdict(self, case):
        d = Path(self.fresh())
        ver = case.tag[1:]

        def write(path, data):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps(data))
        apps.configure(state=d / "state", version=lambda: ver, setting={"apps_android": True}.get, write_json=write)
        rel = d / "rel"
        rel.mkdir()
        name = f"aerieos-app-{ver}.apk"
        (rel / name).write_bytes(b"an apk")
        (rel / (name + ".sha256")).write_text(sha(b"an apk") + f"  {name}\n")
        case.publish(str(rel), name, sha(b"an apk"))
        assets = [{"name": p.name, "browser_download_url": f"file://{p}"} for p in sorted(rel.iterdir())]
        (d / "releases.json").write_text(json.dumps([{"tag_name": case.tag, "assets": assets}]))
        with mock.patch.multiple(apps, RELEASES_URL=f"file://{d / 'releases.json'}", SIGNERS=self.signers_file(case, str(d)),
                                 unvetted_ok=lambda: False):
            v = apps.check()
            held = apps.path("android", name)
        self.assertEqual(bool(held), bool(v["apps"][0]["files"]))
        return bool(held), f"{v['problem']}\n{v['signature']}"

    def test_an_app_the_library_offers(self):
        self.run_table()

    def test_a_release_with_no_list_is_said_as_that_and_nothing_of_the_lookup_that_missed(self):
        # The sentence a person reads on the Library names the two files and
        # why a release may lack them, with no quoted key of a failed lookup.
        d = Path(self.fresh())

        def write(path, data):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps(data))
        apps.configure(state=d / "state", version=lambda: PRE[1:], setting={"apps_android": True}.get, write_json=write)
        name = f"aerieos-app-{PRE[1:]}.apk"
        (d / name).write_bytes(b"an apk")
        (d / "releases.json").write_text(json.dumps([{"tag_name": PRE, "assets": [{"name": name, "browser_download_url": f"file://{d / name}"}]}]))
        with mock.patch.multiple(apps, RELEASES_URL=f"file://{d / 'releases.json'}", SIGNERS=self.signers_file(TABLE[0], str(d)),
                                 unvetted_ok=lambda: False):
            v = apps.check()
        self.assertIn("carries no signed list of its files (SHA256SUMS and SHA256SUMS.sig): it was made before releases were signed", v["problem"])
        self.assertNotIn("'", v["problem"].split("its key's holder")[0])

    def test_a_file_held_from_before_the_list_was_asked_goes_when_the_list_names_other_bytes(self):
        # An install that came from a build with no signer holds what the
        # sha256 beside the file passed; the first look with a signer holds
        # it to the list.
        d = Path(self.fresh())

        def write(path, data):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps(data))
        apps.configure(state=d / "state", version=lambda: PRE[1:], setting={"apps_android": True}.get, write_json=write)
        rel = d / "rel"
        rel.mkdir()
        name = f"aerieos-app-{PRE[1:]}.apk"
        (rel / name).write_bytes(b"not the app")
        (rel / (name + ".sha256")).write_text(sha(b"not the app") + f"  {name}\n")

        def look(case):
            assets = [{"name": p.name, "browser_download_url": f"file://{p}"} for p in sorted(rel.iterdir())]
            (d / "releases.json").write_text(json.dumps([{"tag_name": PRE, "assets": assets}]))
            with mock.patch.multiple(apps, RELEASES_URL=f"file://{d / 'releases.json'}", SIGNERS=self.signers_file(case, str(d)),
                                     unvetted_ok=lambda: False):
                return apps.check(), apps.path("android", name)
        v, held = look(TABLE[6])
        self.assertTrue(held, v)
        self.assertEqual(v["signature"], apps.UNCHECKED)
        TABLE[0].publish(str(rel), name, sha(b"an apk"))
        v, held = look(TABLE[0])
        self.assertIsNone(held)
        self.assertFalse((d / "state" / "apps" / "android" / name).exists())
        self.assertIn("is not the file", v["problem"])


class OneRule(unittest.TestCase):
    """What the four must agree on before any signature is read."""
    TAGS = {"v1.2.3": "stable", "v0.10.0": "stable",
            "v1.2.3-dev.45": "pre", "v1.2.3-rc.1": "pre", "v1.2.3-beta.2": "pre",
            "1.2.3": "", "v1.2": "", "v1.2.3.4": "", "v1.2.3-dev": "", "v1.2.3-dev.4+abc1234": "", "v1.2.3-Dev.1": "",
            "latest": "", "": ""}

    def test_a_tags_shape_says_who_may_sign_in_every_verifier(self):
        want = {"stable": (REL,), "pre": (REL, DEV), "": ()}
        for tag, kind in self.TAGS.items():
            self.assertEqual(releasecheck.tag_kind(tag), kind, tag)
            self.assertEqual(osimage.tag_namespaces(tag), want[kind], tag)
            self.assertEqual(stick.tag_namespaces(tag), want[kind], tag)

    @unittest.skipUnless(shutil.which("ssh-keygen"), "no ssh-keygen here")
    def test_the_installer_reads_a_tag_the_same_way(self):
        # Asked of its own lines: with only a dev signer named and nothing to
        # fetch, a stable tag stops at the signer, a pre-release at the list,
        # and anything else at the tag.
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        with open(os.path.join(d, "signers"), "w") as f:
            f.write(line("dev", DEV) + "\n")
        os.makedirs(os.path.join(d, "bin"))
        with open(os.path.join(d, "bin", "curl"), "w") as f:
            f.write("#!/bin/sh\nexit 22\n")
        os.chmod(os.path.join(d, "bin", "curl"), 0o755)
        says = {"stable": "no stable signer is named yet", "pre": "carries no signed list of its files", "": "is not a release's tag"}
        pre = f'set -euo pipefail\nBB_CONTROLLER_LIB=1 . "{INSTALLER}"\n'
        env = dict(os.environ, BB_INSTALL_ROOT=d, PATH=os.path.join(d, "bin") + ":" + os.environ["PATH"],
                   BB_RELEASE_SIGNERS=os.path.join(d, "signers"))
        for tag, kind in self.TAGS.items():
            r = subprocess.run(["bash", "-c", pre + 'release_signed "$1" /dev/null x "$2"', "bash", tag, d], capture_output=True,
                               text=True, timeout=30, check=False, env=env)
            self.assertNotEqual(r.returncode, 0, tag)
            self.assertIn(says[kind], r.stderr, tag)

    def test_the_three_that_ask_who_built_a_file_name_one_workflow(self):
        want = osimage.signer_identity("aquilaelabs/aerieos")
        self.assertEqual(stick.SIGNER_IDENTITY, want)
        r = subprocess.run(["bash", "-c", f'BB_CONTROLLER_LIB=1 . "{INSTALLER}"; printf %s "$SIGNER_IDENTITY"'],
                           capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(r.stdout, want, r.stderr)
        self.assertIn("build-image\\.yml@refs/tags/v", want)


if __name__ == "__main__":
    unittest.main()
