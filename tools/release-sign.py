#!/usr/bin/env python3
"""Sign an AerieOS release's list of its files: SHA256SUMS, which every
install holds a file it takes to, and SHA256SUMS.sig, which it verifies
against its own config/release-signers. The namespace says the channel, and
so who holds the key:

    tools/release-sign.py key [--hardware] [--file PATH]
        make the stable release key with ssh-keygen (Ed25519; --hardware on
        a security key: ed25519-sk) and print the line for
        config/release-signers
    tools/release-sign.py sign TAG [--key PATH] [--commit SHA] [--apk-signers FILE] [--upload]
        on the stable key holder's own machine, never in the repository, CI
        or a controller: sign in the namespace aerieos-release, which a
        stable release must carry and a pre-release may. Shows the commit
        the tag names (it must be one you cut: --commit holds it to one) and
        asks; with --upload attaches both files with gh, else says where
        they are to attach
    tools/release-sign.py seal TAG [--commit SHA] [--wait SECONDS] [--out DIR]
                               [--apk-signers FILE] [--signers FILE] [--from FOLDER]
        in CI, for a build that publishes by itself: sign in the namespace
        aerieos-dev with the release build's key, the 64 hex characters in
        AERIEOS_RELEASE_KEY (the Ed25519 seed tools/sign-agent.py reads). A
        stable tag is refused: a stable release is signed by its key's
        holder, not by CI. Reads the release with GH_TOKEN, leaves the two
        files in DIR for the job to attach (tools/release-attach.sh), and
        prints what it signed. --wait is how long it waits for the release
        to carry every file .release-files names (the signed Android app is
        attached on a controller's clock); exit 3 when it still lacks one.
        A release sealed already is sealed again with the same list; one
        whose files have changed since gets a new list, each change said.
        --from FOLDER seals the files of a folder and reads no release: a
        rehearsal's (release-rehearsal.yml), with a key made for the run and
        --signers naming the file written for it. The folder is held to no
        list of what a release carries, and nothing made is a release's
    tools/release-sign.py signer
        the config/release-signers line of the key in AERIEOS_RELEASE_KEY,
        for dev builds: what a rehearsal writes its own key's file with

Either way the list is made from the files themselves: each file of the
release is downloaded and its bytes hashed here, never read from the sha256
beside it, since whoever can replace a file on a release can replace that
too. A file whose sha256 file says otherwise stops the signing; so does a
release short of a file .release-files names, since a file attached after
the list is one no install takes. Each file's build attestation is
verified with gh against the workflow that builds it, run on this tag
(WORKFLOWS), at the commit the tag names and on a hosted runner (gh
attestation verify's --source-digest and --deny-self-hosted-runners): a
tag's name can be moved to another commit and a run started again there,
and the name alone would take that run's files. A file with no
attestation that verifies is refused, whatever sha256 sits beside it,
since whoever replaced the file could replace that too; gh missing
refuses the release. A rehearsal's folder (seal --from) is the one
exception: nothing attests a branch's files, so each is held to the
sha256 beside it.

The Android app is the one file no build attests: its build hands it over
unsigned, and a controller signs it with the app's own key and attaches it
later (scripts/dashboard/releasesign.py). What vouches for it is that
signature: apksigner must verify it as signed by a certificate
config/apk-signers names (--apk-signers names another file), and an APK it
cannot check is refused, apksigner missing included, so the stable key's
holder signs where the Android SDK's build-tools are.

GitHub's answers, a download and gh's check are each asked again after a
short wait where they failed: the transparency log answers 404 for a
minute after an attestation is made, and a dropped connection on the ISO
would end the signing.

SHA256SUMS lists every file but itself, its signature, the .sha256 files and
the attestation bundles.

ssh-keygen is OpenSSH's, on Linux, a Mac and Windows 10 or later. seal
needs the cryptography library, to write the seed as a key ssh-keygen reads
(CI installs it from tools/release-requirements.txt, each file held to its
hash). apksigner is the Android SDK build-tools', found on PATH or under
ANDROID_HOME. Python's own library otherwise.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from typing import NoReturn

REPO = "aquilaelabs/aerieos"
API = f"https://api.github.com/repos/{REPO}"
NS = "aerieos-release"
DEV_NS = "aerieos-dev"
DEFAULT_KEY = os.path.join(os.path.expanduser("~"), ".aerieos-release", "key")
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
# What every install verifies a signature against, and what a release carries.
SIGNERS = os.path.join(ROOT, "config", "release-signers")
FILES = os.path.join(ROOT, ".release-files")
# The certificates a release's Android app may be signed by.
APK_SIGNERS = os.path.join(ROOT, "config", "apk-signers")
# A tag by its shape, as the verifiers read it (releasecheck.tag_kind).
STABLE_TAG = re.compile(r"v\d+\.\d+\.\d+")
PRE_TAG = re.compile(r"v\d+\.\d+\.\d+-[a-z][a-z0-9]*\.\d+")
# The workflows whose attestation says a file is this release's build, and
# the files each attests. A build attestation's certificate names the
# workflow file the attesting job is defined in, at the ref the run is on:
# for a job of a workflow another calls (`uses: ./.github/workflows/...`)
# that is the called file, with the caller in the certificate's other
# claims, as GitHub documents for reusable workflows. So the release
# workflow is named for what its own jobs attest (the bundle, the ISO, the
# stick's image, the container image's digest), and the companion workflow
# it calls for what that one builds. Each file is held to its own row; a
# file no row names is taken from any workflow here and from no other: a
# workflow that comes to attest a release's file is named here first.
WORKFLOWS = {
    "build-image.yml": ("aerieos-controller-*.tar.gz", "aerieos-os-*.iso", "aerieos-os-*.stick.raw.xz",
                        "aerieos-image-*.digest"),
    "companion-app.yml": ("aerieos-companion-*.exe", "aerieos-usb-maker-*.exe", "aerieos-companion-*.pyz",
                          "aerieos-vscode-*.vsix"),
}
LISTS = ("SHA256SUMS", "SHA256SUMS.sig")
# How often a release that is not whole yet is looked at again, in seconds.
POLL = 30
# How many times a network question is asked, and the first wait between
# two, in seconds (doubled after each).
TRIES, RETRY_WAIT = 3, 10


def die(s) -> NoReturn:
    print(f"release-sign: {s}", file=sys.stderr)
    sys.exit(1)


def token():
    """Who is asking: a release starts as a draft, which GitHub shows only to
    the repository's own people. GH_TOKEN, or gh's own sign-in."""
    if os.environ.get("GH_TOKEN"):
        return os.environ["GH_TOKEN"]
    gh = shutil.which("gh")
    if gh:
        r = subprocess.run([gh, "auth", "token"], capture_output=True, text=True, check=False)
        return r.stdout.strip() if r.returncode == 0 else ""
    return ""


def _open(url, raw):
    req = urllib.request.Request(url, headers={"User-Agent": "aerieos-release-sign",
                                               "Accept": "application/octet-stream" if raw else "application/vnd.github+json"})
    t = token()
    if t:
        req.add_unredirected_header("Authorization", f"Bearer {t}")
    return urllib.request.urlopen(req, timeout=60)  # noqa: S310 (GitHub's own addresses)


def retried(fn):
    """fn's answer, asked again after a wait where the network failed it: a
    dropped connection, a timeout, a 5xx or a 429. Any other answer from
    the server (a 404, a 403) is the same the next time, and is raised."""
    for n in range(TRIES):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if (e.code < 500 and e.code != 429) or n == TRIES - 1:
                raise
        except OSError:
            if n == TRIES - 1:
                raise
        time.sleep(RETRY_WAIT * 2 ** n)


def get(url, raw=False):
    def ask():
        with _open(url, raw) as r:
            return r.read()
    body = retried(ask)
    return body if raw else json.loads(body)


def download(url, dest):
    """A release's file into `dest`, by chunks, from the start again where
    the connection dropped; the sha256 of its bytes."""
    def fetch():
        h = hashlib.sha256()
        with _open(url, True) as r, open(dest, "wb") as f:
            for chunk in iter(lambda: r.read(1 << 20), b""):
                h.update(chunk)
                f.write(chunk)
        return h.hexdigest()
    return retried(fetch)


def release_of(tag):
    """The release for `tag`, a draft too: GitHub's look-up by tag never finds
    one, so it is looked for among the listed."""
    for page in (1, 2, 3):
        rows = get(f"{API}/releases?per_page=50&page={page}")
        for r in rows:
            if r.get("tag_name") == tag:
                return r
        if len(rows) < 50:
            break
    die(f"no release for {tag} that you can see: a draft needs GH_TOKEN or gh signed in to an account of the repository")


def commit_of(tag):
    """The commit the tag names, through an annotated tag's own object."""
    ref = get(f"{API}/git/ref/tags/{tag}")
    sha = ref["object"]["sha"]
    if ref["object"]["type"] == "tag":
        sha = get(f"{API}/git/tags/{sha}")["object"]["sha"]
    return sha


def keygen() -> str:
    tool = shutil.which("ssh-keygen")
    if not tool:
        die("ssh-keygen is not here: install OpenSSH (on Windows: Settings, Optional features, OpenSSH Client)")
    return tool


def listed(name):
    """Whether SHA256SUMS lists the file: every one but the list, its
    signature, the sha256 files and the attestation bundles, which vouch for
    the files by their hash themselves."""
    return not (name in LISTS or name.endswith((".sha256", ".attestation.jsonl")))


def missing(names, ver, path=None):
    """The files .release-files names (@VER@ the version, * a pattern) that
    are not among `names`, but the list and its signature, which are what is
    being made. None where there is no .release-files to read."""
    try:
        with open(path or FILES, encoding="utf-8") as f:
            want = [ln.strip().replace("@VER@", ver) for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    except OSError:
        return None
    return [w for w in want if w not in LISTS and not any(fnmatch.fnmatchcase(n, w) for n in names)]


def builders(name):
    """The workflows whose attestation is taken for the file `name`: the one
    WORKFLOWS names it under, or all of them for a file it names nowhere."""
    named = tuple(w for w, pats in WORKFLOWS.items() if any(fnmatch.fnmatchcase(name, p) for p in pats))
    return named or tuple(WORKFLOWS)


def identity(tag, name=""):
    """Who may have built the file `name` of release `tag`, as its
    attestation's certificate names them: the workflow that builds it, run
    on this very tag."""
    flows = "|".join(re.escape(w) for w in builders(name))
    return rf"^https://github\.com/{re.escape(REPO)}/\.github/workflows/({flows})@refs/tags/{re.escape(tag)}$"


def attested(gh, path, tag, name="", commit=""):
    """"" when gh verifies a build attestation for the file, made by the
    workflow that builds it at this tag, on a hosted runner, and, where
    `commit` is the commit the tag names, from that very commit: the
    certificate's source digest, which a tag moved since does not carry.
    Else gh's own last line on why. gh is asked again after a wait where it
    said no: it says no alike for a transparency log or an API that did
    not answer and for a file nothing attested."""
    held = ["--source-digest", commit] if re.fullmatch(r"[0-9a-f]{40}", commit or "") else []
    why = ""
    for n in range(TRIES):
        if n:
            time.sleep(RETRY_WAIT * 2 ** (n - 1))
        r = subprocess.run([gh, "attestation", "verify", path, "--repo", REPO, "--cert-identity-regex", identity(tag, name),
                            "--deny-self-hosted-runners", *held],
                           capture_output=True, text=True, check=False)
        if r.returncode == 0:
            return ""
        why = ((r.stderr or r.stdout).strip().splitlines() or ["it gave no reason"])[-1][-300:]
    return why


def apk_signers(path=None):
    """The certificates a release's APK may be signed by: the SHA-256
    fingerprints config/apk-signers names, one a line, as 64 hex characters
    each. None of them where the file names none or is not here."""
    try:
        with open(path or APK_SIGNERS, encoding="utf-8") as f:
            rows = [ln.split("#", 1)[0].strip().replace(":", "").lower() for ln in f]
    except OSError:
        return []
    return [r for r in rows if re.fullmatch(r"[0-9a-f]{64}", r)]


def apksigner():
    """Android's apksigner: on PATH, or the newest build-tools' under the
    SDK a GitHub-hosted runner carries (ANDROID_HOME). "" where it is not."""
    tool = shutil.which("apksigner")
    if tool:
        return tool
    found = []
    for sdk in (os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT")):
        tools = os.path.join(sdk, "build-tools") if sdk else ""
        for ver in os.listdir(tools) if os.path.isdir(tools) else []:
            exe = os.path.join(tools, ver, "apksigner")
            if os.path.isfile(exe) and os.access(exe, os.X_OK):
                found.append(([int(n) for n in re.findall(r"\d+", ver)], exe))
    return max(found)[1] if found else ""


# A signer's certificate as apksigner verify --print-certs says it: "Signer #1
# certificate SHA-256 digest: HEX" up to build-tools 36, "V3.0 Signer:
# certificate SHA-256 digest: HEX" from 37, the scheme first (the runner's
# newest said only the second, and v0.9.0-dev.6049's seal found no signer).
# A source stamp's line starts with its own words and is never one.
SIGNER_CERT = re.compile(r"^(?:V\d+(?:\.\d+)? )?Signer\b[^\n]*?certificate SHA-256 digest:\s*([0-9a-fA-F]{64})\s*$", re.M)


def fingerprint(hexes):
    """64 hex characters as a certificate's fingerprint is written."""
    return ":".join(re.findall("..", hexes)).upper()


def apk_signed(tool, path, named):
    """"" when apksigner verifies the APK at `path` and every certificate
    that signed it is one of `named`; else why it is not taken."""
    try:
        r = subprocess.run([tool, "verify", "--print-certs", path], capture_output=True, text=True, check=False, timeout=300)
    except (OSError, subprocess.SubprocessError) as e:
        return f"could not be checked: apksigner did not run ({e})"
    if r.returncode != 0:
        return f"is not an APK apksigner verifies as signed: {(r.stderr or r.stdout).strip()[-300:] or 'it gave no reason'}"
    # Its signers' lines, never a source stamp's, which a device does not
    # hold an install to.
    certs = [m.group(1).lower() for m in SIGNER_CERT.finditer(r.stdout)]
    if not certs:
        return "is signed by no certificate apksigner names"
    other = [c for c in certs if c not in named]
    if other:
        return (f"is signed by a certificate config/apk-signers does not name ({fingerprint(other[0])}): "
                "it was not signed with the key AerieOS's app is signed with")
    return ""


class Release:
    """A release's files, read from GitHub by the API's own address, which a
    draft's files answer at too."""

    def __init__(self, rel):
        self.assets = {x["name"]: x["url"] for x in rel.get("assets") or []}

    def names(self):
        return list(self.assets)

    def fetch(self, name, work):
        """(where the file is, the sha256 of its bytes, whether the copy is
        this run's to delete)."""
        path = os.path.join(work, "file")
        return path, download(self.assets[name], path), True

    def read(self, name):
        return get(self.assets[name], raw=True)


class Folder:
    """A folder's files, read where they are: a rehearsal's (seal --from)."""

    def __init__(self, path):
        self.path = path

    def names(self):
        return sorted(n for n in os.listdir(self.path) if os.path.isfile(os.path.join(self.path, n)))

    def fetch(self, name, work):
        h = hashlib.sha256()
        with open(os.path.join(self.path, name), "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return os.path.join(self.path, name), h.hexdigest(), False

    def read(self, name):
        with open(os.path.join(self.path, name), "rb") as f:
            return f.read()


def gather(tag, source, work, release=True, apk_file=None, commit=""):
    """SHA256SUMS' lines for the files of `source`, a release or a folder:
    every listed file's bytes hashed (a release's downloaded into `work`),
    held to the sha256 beside it and to what vouches for it, its build
    attestation or, for the Android app, its signature; stops at a file the
    release itself contradicts, or one nothing vouches for. Each is said as
    it is read. `release` off is a rehearsal's folder, which nothing
    attested: each file is held to the sha256 beside it, and the app to its
    signature where apksigner is here. `commit` is the commit the tag names,
    which each attestation is held to."""
    names = source.names()
    gh = shutil.which("gh") if release else None
    if release and not gh:
        die("gh is not here to verify each file's build attestation with (cli.github.com): not signed")
    aps, named = None, []
    if any(n.endswith(".apk") for n in names if listed(n)):
        aps, named = apksigner(), apk_signers(apk_file)
        if not aps and release:
            die("apksigner is not here to check the Android app's signature with (the Android SDK's build-tools, on PATH or "
                "under ANDROID_HOME): not signed")
        if not aps:
            print("apksigner is not here, so the Android app's signing certificate is not checked")
    lines = []
    for name in sorted(n for n in names if listed(n)):
        try:
            path, digest, mine = source.fetch(name, work)
            beside = None
            if name + ".sha256" in names:
                beside = (source.read(name + ".sha256").decode("utf-8", "replace").split() or [""])[0].lower()
        except OSError as e:
            die(f"{name} did not download ({e}): not signed")
        if beside is not None and beside != digest:
            die(f"{name}.sha256 says {beside[:12] or 'nothing'} and the file's bytes hash to {digest[:12]}: "
                "the release contradicts itself, so it is not signed (a file or its sha256 was replaced)")
        # The Android app: its signature is what says whose it is, and no
        # build attests the file a controller signed.
        app = name.endswith(".apk")
        unattested = attested(gh, path, tag, name, commit) if gh and not app else None
        why = apk_signed(aps, path, named) if app and aps else ""
        if mine:
            os.unlink(path)
        if why:
            die(f"{name} {why}: not signed")
        att, signed = unattested == "", app and bool(aps)
        if release and not app and not att:
            flow = " or ".join(builders(name))
            die(f"{name} has no build attestation by {flow} at {tag}" + (f", from commit {commit[:12]}," if commit else "")
                + f" that verifies (gh said: {unattested}): nothing says it is this release's build, so it is not signed")
        if beside is None and not att and not signed:
            die(f"{name} has no sha256 beside it, and nothing else vouches for it: not signed")
        how = " and ".join(([f"{name}.sha256 matches"] if beside is not None else [])
                           + (["its build attestation verifies"] if att else [])
                           + (["apksigner verifies it as signed by a certificate config/apk-signers names"] if signed else
                              ["its signing certificate is not checked"] if app else []))
        print(f"  {digest}  {name}  ({how})")
        lines.append(f"{digest}  {name}")
    if not lines:
        die(f"{tag} carries no files yet")
    return lines


def whole(tag, wait=0):
    """The release once it carries every file .release-files names, waited
    for up to `wait` seconds; exit 3 naming what it still lacks."""
    end = time.time() + wait
    while True:
        rel = release_of(tag)
        lacks = missing([x["name"] for x in rel.get("assets") or []], tag[1:])
        if lacks is None:
            print(f"no .release-files at {FILES}, so the release is signed as it is")
            return rel
        if not lacks:
            return rel
        if time.time() >= end:
            print(f"release-sign: {tag} is not whole: {' '.join(lacks)} still missing, and a file attached after the list is "
                  "signed is one no install takes: not signed", file=sys.stderr)
            sys.exit(3)
        time.sleep(min(POLL, max(0.1, end - time.time())))


def changed(old, lines):
    """What differs between a list a release carries (`old`, its text) and
    the lines just made, a sentence each; nothing when they are the same."""
    was = dict(reversed(ln.split()[:2]) for ln in old.splitlines() if len(ln.split()) >= 2)
    now = dict(reversed(ln.split()) for ln in lines)
    out = [f"{n} was {was[n][:12]} and is {now[n][:12]} now" for n in sorted(was) if n in now and was[n] != now[n]]
    out += [f"{n} is new" for n in sorted(now) if n not in was]
    out += [f"{n} is gone" for n in sorted(was) if n not in now]
    return out


def write_sums(out, lines):
    sums = os.path.join(out, "SHA256SUMS")
    with open(sums, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    # ssh-keygen asks before it replaces a signature.
    if os.path.exists(sums + ".sig"):
        os.unlink(sums + ".sig")
    return sums


def names_signer(ns, path=None):
    """Whether config/release-signers names a signer for the namespace; None
    when the file is not here to read."""
    try:
        with open(path or SIGNERS, encoding="utf-8") as f:
            return any(ln.split(None, 1)[0] == ns for ln in f if ln.strip() and not ln.lstrip().startswith("#"))
    except OSError:
        return None


def verifies(tool, sums, ns, path=None):
    """Whether the signature beside `sums` is one an install built from this
    tree takes in the namespace: the question every verifier asks."""
    with open(sums, "rb") as f:
        r = subprocess.run([tool, "-Y", "verify", "-f", path or SIGNERS, "-I", ns, "-n", ns, "-s", sums + ".sig"],
                           stdin=f, capture_output=True, check=False)
    return r.returncode == 0


def cmd_key(a):
    tool = keygen()
    path = a.file or DEFAULT_KEY
    if os.path.exists(path):
        die(f"{path} is there already: a release key is made once; keep it, and back it up somewhere offline")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    kind = "ed25519-sk" if a.hardware else "ed25519"
    print(f"making the release key ({kind}) at {path}; give it a passphrase when asked")
    if subprocess.run([tool, "-t", kind, "-C", NS, "-f", path]).returncode != 0:
        die("ssh-keygen did not make the key")
    with open(path + ".pub", encoding="utf-8") as f:
        kt, kb = f.read().split()[:2]
    fp = subprocess.run([tool, "-l", "-f", path + ".pub"], capture_output=True, text=True, check=False).stdout.strip()
    print("\nThe line for config/release-signers (commit it; it is public):")
    print(f'{NS} namespaces="{NS}" {kt} {kb} {NS}')
    print(f"\nIts fingerprint, to publish where people can check it (aerieos.org): {fp}")
    print("Keep the private key and its passphrase off the repository, CI and every controller, and back it up offline.")


def cmd_sign(a):
    tool = keygen()
    key = a.key or DEFAULT_KEY
    if not (STABLE_TAG.fullmatch(a.tag) or PRE_TAG.fullmatch(a.tag)):
        die(f"{a.tag} is not a release's tag (vX.Y.Z, or vX.Y.Z-dev.N for a pre-release)")
    if not os.path.isfile(key):
        die(f"no release key at {key}: make it with tools/release-sign.py key, or name it with --key")
    try:
        rel = whole(a.tag)
        sha = commit_of(a.tag)
    except OSError as e:
        die(f"GitHub does not answer for {a.tag}: {e}")
    print(f"{a.tag} names commit {sha}")
    if a.commit and not sha.startswith(a.commit.lower()):
        die(f"{a.tag} names {sha[:12]}, not {a.commit}: not signed (the tag was moved, or this is not the release you cut)")
    if not a.commit and input("Is that the commit you cut this release from? Type yes: ").strip().lower() != "yes":
        die("not signed")
    out = a.out or tempfile.mkdtemp(prefix=f"sign-{a.tag}-")
    os.makedirs(out, exist_ok=True)
    work = tempfile.mkdtemp(prefix="files-", dir=out)
    try:
        lines = gather(a.tag, Release(rel), work, apk_file=a.apk_signers, commit=sha)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    sums = write_sums(out, lines)
    print(f"{len(lines)} files in SHA256SUMS; signing")
    if subprocess.run([tool, "-Y", "sign", "-f", key, "-n", NS, sums]).returncode != 0:
        die("ssh-keygen did not sign")
    named = names_signer(NS)
    if named and not verifies(tool, sums, NS):
        os.unlink(sums + ".sig")
        die(f"{key} is not the stable signer config/release-signers names, so no install would take this signature: not signed")
    if not named:
        print("config/release-signers names no stable signer yet: until this key's line (tools/release-sign.py key prints it) "
              "is committed and an install runs a build that carries it, no install takes this signature")
    if a.upload:
        gh = shutil.which("gh")
        if not gh:
            die(f"gh is not here to attach them: attach {sums} and {sums}.sig to the {a.tag} release by hand")
        r = subprocess.run([gh, "release", "upload", a.tag, sums, sums + ".sig", "--repo", REPO, "--clobber"])
        if r.returncode != 0:
            die("gh did not attach them")
        print(f"signed and attached to {a.tag}")
    else:
        print(f"signed: attach {sums} and {sums}.sig to the {a.tag} release (its Edit page, or gh release upload)")


def seed():
    """The release build's key as the cryptography library holds it:
    AERIEOS_RELEASE_KEY's 64 hex characters, an Ed25519 seed."""
    hexes = (os.environ.get("AERIEOS_RELEASE_KEY") or "").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{64}", hexes):
        die("AERIEOS_RELEASE_KEY is not the release build's key (64 hex characters, its secret): nothing is signed")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: PLC0415
    except ImportError:
        die("the cryptography library is not here to write the key for ssh-keygen with (pip install cryptography)")
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(hexes))


def seed_key(folder):
    """The release build's key, AERIEOS_RELEASE_KEY's seed, written into
    `folder` as an OpenSSH private key only its owner reads: its path."""
    key = seed()
    from cryptography.hazmat.primitives import serialization as ser  # noqa: PLC0415
    pem = key.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.OpenSSH, ser.NoEncryption())
    path = os.path.join(folder, "key")
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(pem)
    return path


def cmd_signer(a):
    key = seed()
    from cryptography.hazmat.primitives import serialization as ser  # noqa: PLC0415
    pub = key.public_key().public_bytes(ser.Encoding.OpenSSH, ser.PublicFormat.OpenSSH).decode()
    print(f'{DEV_NS} namespaces="{DEV_NS}" {pub}')


def cmd_seal(a):
    if STABLE_TAG.fullmatch(a.tag):
        die(f"{a.tag} is a stable release: a stable release is signed by its key's holder, not by CI "
            "(tools/release-sign.py sign, on their own machine)")
    if not PRE_TAG.fullmatch(a.tag):
        die(f"{a.tag} is not a pre-release's tag (vX.Y.Z-dev.N): nothing is signed")
    tool = keygen()
    signers = a.signers or SIGNERS
    if not names_signer(DEV_NS, signers):
        die(f"{signers} names no signer for dev builds (or is not in this checkout), so no install would take the signature: nothing is signed")
    old, sha = None, ""
    if a.folder:
        # A folder's files: a rehearsal's, which no release carries and
        # nothing attested.
        if not os.path.isdir(a.folder):
            die(f"{a.folder} is not a folder of files to seal")
        source = Folder(a.folder)
        print(f"sealing the files in {a.folder}, which are no release's: nothing made here is one's")
    else:
        try:
            rel = whole(a.tag, a.wait)
            sha = commit_of(a.tag)
            source = Release(rel)
            if "SHA256SUMS" in source.names():
                old = source.read("SHA256SUMS").decode("utf-8", "replace")
        except OSError as e:
            die(f"GitHub does not answer for {a.tag}: {e}")
        print(f"{a.tag} names commit {sha}")
        if a.commit and not sha.startswith(a.commit.lower()):
            die(f"{a.tag} names {sha[:12]}, not {a.commit}: not signed (the tag was moved since this build started)")
    out = a.out or tempfile.mkdtemp(prefix=f"seal-{a.tag}-")
    os.makedirs(out, exist_ok=True)
    work = tempfile.mkdtemp(prefix="files-", dir=out)
    try:
        lines = gather(a.tag, source, work, release=not a.folder, apk_file=a.apk_signers, commit=sha)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    # A release sealed before: the same list is signed again and changes
    # nothing; another list replaces a signature installs may hold a file
    # to, which every file's attestation or signature vouches for, and each
    # change is said.
    if old is not None:
        differs = changed(old, lines)
        if not differs:
            print(f"{a.tag} is sealed already with this very list: the same list is signed again")
        else:
            said = (f"{a.tag} carries a signed list already, and its files have changed since: {'; '.join(differs)}. "
                    "Each is vouched for by its build attestation or its signature, so the list is replaced by the one made now")
            print(said)
            # ...on the run's own page too, where a job's log is not opened.
            if os.environ.get("GITHUB_ACTIONS") == "true":
                print(f"::warning title=The release's signed list is replaced::{said}")
    sums = write_sums(out, lines)
    # The key is on disk only while ssh-keygen reads it.
    keydir = tempfile.mkdtemp(prefix="aerieos-seal-")
    try:
        key = seed_key(keydir)
        r = subprocess.run([tool, "-Y", "sign", "-q", "-f", key, "-n", DEV_NS, sums], stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, check=False)
    finally:
        shutil.rmtree(keydir, ignore_errors=True)
    if r.returncode != 0:
        die(f"ssh-keygen did not sign: {(r.stderr or r.stdout).strip()[-300:]}")
    if not verifies(tool, sums, DEV_NS, signers):
        os.unlink(sums + ".sig")
        die(f"the key in AERIEOS_RELEASE_KEY is not one {a.signers or 'config/release-signers'} names for dev builds, so no "
            "install would take this signature: nothing is left to attach (the secret and config/aerieos-release.pub have "
            "come apart)")
    if a.folder:
        print(f"sealed the folder: {len(lines)} files in SHA256SUMS, signed in {DEV_NS} and verified against {signers}")
        print(f"left in {out}, to attach to nothing")
        return
    print(f"sealed {a.tag}: {len(lines)} files in SHA256SUMS, signed in {DEV_NS} with the release build's key")
    print(f"to attach to the release: {sums} {sums}.sig")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="release-sign.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("key", help="make the stable release key")
    k.add_argument("--hardware", action="store_true", help="on a security key (ed25519-sk)")
    k.add_argument("--file", help=f"where (default {DEFAULT_KEY})")
    k.set_defaults(fn=cmd_key)
    s = sub.add_parser("sign", help="sign a release's SHA256SUMS with the stable key, on its holder's machine")
    s.add_argument("tag")
    s.add_argument("--key", help=f"the private key (default {DEFAULT_KEY})")
    s.add_argument("--upload", action="store_true", help="attach the two files with gh")
    s.set_defaults(fn=cmd_sign)
    c = sub.add_parser("seal", help="sign a dev build's SHA256SUMS with the release build's key, in CI")
    c.add_argument("tag")
    c.add_argument("--wait", type=int, default=0, help="seconds to wait for the release to carry every file .release-files names")
    c.add_argument("--from", dest="folder", help="seal this folder's files and read no release (a rehearsal)")
    c.add_argument("--signers", help="the signers file the signature must verify against (default config/release-signers)")
    c.set_defaults(fn=cmd_seal)
    g = sub.add_parser("signer", help="print the signers line of the key in AERIEOS_RELEASE_KEY, for dev builds")
    g.set_defaults(fn=cmd_signer)
    for p in (s, c):
        p.add_argument("--commit", help="the commit the tag must name")
        p.add_argument("--apk-signers", help="the certificates the Android app may be signed by (default config/apk-signers)")
        p.add_argument("--out", help="the folder SHA256SUMS and SHA256SUMS.sig are left in (default: a new temporary one)")
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
