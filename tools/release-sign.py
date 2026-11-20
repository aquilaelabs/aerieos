#!/usr/bin/env python3
"""Sign an AerieOS release's list of its files (R199): SHA256SUMS, which every
install holds a file it takes to, and SHA256SUMS.sig, which it verifies
against its own config/release-signers. The namespace says the channel, and
so who holds the key:

    tools/release-sign.py key [--hardware] [--file PATH]
        make the stable release key with ssh-keygen (Ed25519; --hardware on
        a security key: ed25519-sk) and print the line for
        config/release-signers
    tools/release-sign.py sign TAG [--key PATH] [--commit SHA] [--attested] [--upload]
        on the stable key holder's own machine, never in the repository, CI
        or a controller: sign in the namespace aerieos-release, which a
        stable release must carry and a pre-release may. Shows the commit
        the tag names (it must be one you cut: --commit holds it to one) and
        asks; with --upload attaches both files with gh, else says where
        they are to attach
    tools/release-sign.py seal TAG [--commit SHA] [--attested] [--wait SECONDS] [--out DIR]
        in CI, for a build that publishes by itself: sign in the namespace
        aerieos-dev with the release build's key, the 64 hex characters in
        AERIEOS_RELEASE_KEY (the Ed25519 seed tools/sign-agent.py reads). A
        stable tag is refused: a stable release is signed by its key's
        holder, not by CI. Reads the release with GH_TOKEN, leaves the two
        files in DIR for the job to attach (tools/release-attach.sh), and
        prints what it signed. --wait is how long it waits for the release
        to carry every file .release-files names (the signed Android app is
        attached on a controller's clock); exit 3 when it still lacks one

Either way the list is made from the files themselves: each file of the
release is downloaded and its bytes hashed here, never read from the sha256
beside it, since whoever can replace a file on a release can replace that
too. A file whose sha256 file says otherwise stops the signing; so does a
release short of a file .release-files names, since a file attached after
the list is one no install takes. Where gh is here each file's build
attestation is verified against the release workflow at this tag, and a
file with neither a matching sha256 beside it nor an attestation that
verifies is refused; --attested refuses any file without one.

SHA256SUMS lists every file but itself, its signature, the .sha256 files and
the attestation bundles.

ssh-keygen is OpenSSH's, on Linux, a Mac and Windows 10 or later. seal
needs the cryptography library, to write the seed as a key ssh-keygen reads.
Python's own library otherwise.
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
# A tag by its shape, as the verifiers read it (releasecheck.tag_kind).
STABLE_TAG = re.compile(r"v\d+\.\d+\.\d+")
PRE_TAG = re.compile(r"v\d+\.\d+\.\d+-[a-z][a-z0-9]*\.\d+")
# The workflows whose attestation says a file is this release's build: the
# release workflow, which attests the bundle, the ISO and the stick's image.
# A workflow it calls that comes to attest its own file is named here then.
WORKFLOWS = ("build-image.yml",)
LISTS = ("SHA256SUMS", "SHA256SUMS.sig")
# How often a release that is not whole yet is looked at again, in seconds.
POLL = 30


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


def get(url, raw=False):
    with _open(url, raw) as r:
        body = r.read()
    return body if raw else json.loads(body)


def download(url, dest):
    """A release's file into `dest`, by chunks; the sha256 of its bytes."""
    h = hashlib.sha256()
    with _open(url, True) as r, open(dest, "wb") as f:
        for chunk in iter(lambda: r.read(1 << 20), b""):
            h.update(chunk)
            f.write(chunk)
    return h.hexdigest()


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


def identity(tag):
    """Who may have built a file of release `tag`: one of WORKFLOWS, run on
    this very tag."""
    flows = "|".join(re.escape(w) for w in WORKFLOWS)
    return rf"^https://github\.com/{re.escape(REPO)}/\.github/workflows/({flows})@refs/tags/{re.escape(tag)}$"


def attested(gh, path, tag):
    """Whether gh verifies a build attestation for the file, made by the
    release workflow at this tag."""
    r = subprocess.run([gh, "attestation", "verify", path, "--repo", REPO, "--cert-identity-regex", identity(tag)],
                       capture_output=True, text=True, check=False)
    return r.returncode == 0


def gather(tag, rel, work, need_attested=False):
    """SHA256SUMS' lines for release `rel`: every listed file downloaded
    into `work` and its bytes hashed, held to the sha256 beside it and to
    its build attestation; stops at a file the release itself contradicts,
    or one nothing vouches for. Each is said as it is read."""
    # By the API's own address, which a draft's files answer at too.
    assets = {x["name"]: x["url"] for x in rel.get("assets") or []}
    gh = shutil.which("gh")
    if not gh:
        if need_attested:
            die("gh is not here to verify the build attestations with (cli.github.com), and --attested asks for them: not signed")
        print("gh is not here, so no build attestation is checked: the sha256 beside each file is what vouches for it")
    lines = []
    for name in sorted(n for n in assets if listed(n)):
        path = os.path.join(work, "file")
        try:
            digest = download(assets[name], path)
            beside = None
            if name + ".sha256" in assets:
                beside = (get(assets[name + ".sha256"], raw=True).decode("utf-8", "replace").split() or [""])[0].lower()
        except OSError as e:
            die(f"{name} did not download ({e}): not signed")
        if beside is not None and beside != digest:
            die(f"{name}.sha256 says {beside[:12] or 'nothing'} and the file's bytes hash to {digest[:12]}: "
                "the release contradicts itself, so it is not signed (a file or its sha256 was replaced)")
        att = bool(gh) and attested(gh, path, tag)
        os.unlink(path)
        if beside is None and not att:
            die(f"{name} has neither a sha256 beside it that matches nor a build attestation that verifies: "
                "nothing says it is this release's build, so it is not signed")
        if need_attested and not att:
            die(f"{name} has no build attestation by the release workflow at {tag} that verifies, and --attested asks for one: not signed")
        how = " and ".join(([f"{name}.sha256 matches"] if beside is not None else []) + (["its build attestation verifies"] if att else []))
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


def write_sums(out, lines):
    sums = os.path.join(out, "SHA256SUMS")
    with open(sums, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    # ssh-keygen asks before it replaces a signature.
    if os.path.exists(sums + ".sig"):
        os.unlink(sums + ".sig")
    return sums


def names_signer(ns):
    """Whether config/release-signers names a signer for the namespace; None
    when the file is not here to read."""
    try:
        with open(SIGNERS, encoding="utf-8") as f:
            return any(ln.split(None, 1)[0] == ns for ln in f if ln.strip() and not ln.lstrip().startswith("#"))
    except OSError:
        return None


def verifies(tool, sums, ns):
    """Whether the signature beside `sums` is one an install built from this
    tree takes in the namespace: the question every verifier asks."""
    with open(sums, "rb") as f:
        r = subprocess.run([tool, "-Y", "verify", "-f", SIGNERS, "-I", ns, "-n", ns, "-s", sums + ".sig"],
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
        lines = gather(a.tag, rel, work, a.attested)
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


def seed_key(folder):
    """The release build's key, AERIEOS_RELEASE_KEY's seed, written into
    `folder` as an OpenSSH private key only its owner reads: its path."""
    seed = (os.environ.get("AERIEOS_RELEASE_KEY") or "").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{64}", seed):
        die("AERIEOS_RELEASE_KEY is not the release build's key (64 hex characters, its secret): nothing is signed")
    try:
        from cryptography.hazmat.primitives import serialization as ser  # noqa: PLC0415
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: PLC0415
    except ImportError:
        die("the cryptography library is not here to write the key for ssh-keygen with (pip install cryptography)")
    pem = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed)).private_bytes(
        ser.Encoding.PEM, ser.PrivateFormat.OpenSSH, ser.NoEncryption())
    path = os.path.join(folder, "key")
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(pem)
    return path


def cmd_seal(a):
    if STABLE_TAG.fullmatch(a.tag):
        die(f"{a.tag} is a stable release: a stable release is signed by its key's holder, not by CI "
            "(tools/release-sign.py sign, on their own machine)")
    if not PRE_TAG.fullmatch(a.tag):
        die(f"{a.tag} is not a pre-release's tag (vX.Y.Z-dev.N): nothing is signed")
    tool = keygen()
    if not names_signer(DEV_NS):
        die(f"{SIGNERS} names no signer for dev builds (or is not in this checkout), so no install would take the signature: nothing is signed")
    try:
        rel = whole(a.tag, a.wait)
        sha = commit_of(a.tag)
    except OSError as e:
        die(f"GitHub does not answer for {a.tag}: {e}")
    print(f"{a.tag} names commit {sha}")
    if a.commit and not sha.startswith(a.commit.lower()):
        die(f"{a.tag} names {sha[:12]}, not {a.commit}: not signed (the tag was moved since this build started)")
    out = a.out or tempfile.mkdtemp(prefix=f"seal-{a.tag}-")
    os.makedirs(out, exist_ok=True)
    work = tempfile.mkdtemp(prefix="files-", dir=out)
    try:
        lines = gather(a.tag, rel, work, a.attested)
    finally:
        shutil.rmtree(work, ignore_errors=True)
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
    if not verifies(tool, sums, DEV_NS):
        os.unlink(sums + ".sig")
        die("the key in AERIEOS_RELEASE_KEY is not one config/release-signers names for dev builds, so no install would take "
            "this signature: nothing is left to attach (the secret and config/aerieos-release.pub have come apart)")
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
    c.set_defaults(fn=cmd_seal)
    for p in (s, c):
        p.add_argument("--commit", help="the commit the tag must name")
        p.add_argument("--attested", action="store_true", help="refuse a file with no build attestation that verifies")
        p.add_argument("--out", help="the folder SHA256SUMS and SHA256SUMS.sig are left in (default: a new temporary one)")
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
