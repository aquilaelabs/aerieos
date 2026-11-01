#!/usr/bin/env python3
"""Sign an AerieOS release (R199), on the release key holder's own machine:
never in the repository, CI or a controller, so whoever changes those can
build and attest a release but not sign one, and every install refuses an
update its release key did not sign.

    tools/release-sign.py key [--hardware] [--file PATH]
        make the release key with ssh-keygen (Ed25519; --hardware on a
        security key: ed25519-sk) and print the line for config/release-signers
    tools/release-sign.py sign TAG [--key PATH] [--commit SHA] [--upload]
        gather every file of release TAG into SHA256SUMS from the sha256 the
        release carries beside each, show the commit the tag names (it must
        be one you cut: --commit holds it to one), sign SHA256SUMS, and with
        --upload attach both with gh; else say where they are to attach

ssh-keygen is OpenSSH's, on Linux, a Mac and Windows 10 or later. Python's
own library otherwise.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from typing import NoReturn

REPO = "aquilaelabs/aerieos"
API = f"https://api.github.com/repos/{REPO}"
NS = "builderbot-release"
DEFAULT_KEY = os.path.join(os.path.expanduser("~"), ".builderbot-release", "key")


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


def get(url, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": "builderbot-release-sign",
                                               "Accept": "application/octet-stream" if raw else "application/vnd.github+json"})
    t = token()
    if t:
        req.add_unredirected_header("Authorization", f"Bearer {t}")
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (GitHub's own addresses)
        body = r.read()
    return body if raw else json.loads(body)


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


def keygen() -> str:
    tool = shutil.which("ssh-keygen")
    if not tool:
        die("ssh-keygen is not here: install OpenSSH (on Windows: Settings, Optional features, OpenSSH Client)")
    return tool


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
    if not os.path.isfile(key):
        die(f"no release key at {key}: make it with tools/release-sign.py key, or name it with --key")
    try:
        rel = release_of(a.tag)
        ref = get(f"{API}/git/ref/tags/{a.tag}")
    except OSError as e:
        die(f"GitHub does not answer for {a.tag}: {e}")
    sha = ref["object"]["sha"]
    if ref["object"]["type"] == "tag":
        sha = get(f"{API}/git/tags/{sha}")["object"]["sha"]
    print(f"{a.tag} names commit {sha}")
    if a.commit and not sha.startswith(a.commit.lower()):
        die(f"{a.tag} names {sha[:12]}, not {a.commit}: not signed (the tag was moved, or this is not the release you cut)")
    if not a.commit and input("Is that the commit you cut this release from? Type yes: ").strip().lower() != "yes":
        die("not signed")
    # By the API's own address, which a draft's files answer at too.
    assets = {x["name"]: x["url"] for x in rel.get("assets") or []}
    lines = []
    for name in sorted(assets):
        # The attestation vouches for the files by their hash itself.
        if name.endswith((".sha256", ".attestation.jsonl")) or name in ("SHA256SUMS", "SHA256SUMS.sig"):
            continue
        if name + ".sha256" not in assets:
            die(f"{name} has no {name}.sha256 beside it: the release is not whole yet; wait for its builds")
        digest = (get(assets[name + ".sha256"], raw=True).decode().split() or [""])[0].lower()
        if len(digest) != 64:
            die(f"{name}.sha256 does not hold a sha256")
        lines.append(f"{digest}  {name}")
    if not lines:
        die(f"{a.tag} carries no files yet")
    out = tempfile.mkdtemp(prefix=f"sign-{a.tag}-")
    sums = os.path.join(out, "SHA256SUMS")
    with open(sums, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{len(lines)} files in SHA256SUMS; signing")
    if subprocess.run([tool, "-Y", "sign", "-f", key, "-n", NS, sums]).returncode != 0:
        die("ssh-keygen did not sign")
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


def main():
    ap = argparse.ArgumentParser(prog="release-sign.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("key", help="make the release key")
    k.add_argument("--hardware", action="store_true", help="on a security key (ed25519-sk)")
    k.add_argument("--file", help=f"where (default {DEFAULT_KEY})")
    k.set_defaults(fn=cmd_key)
    s = sub.add_parser("sign", help="sign a release's SHA256SUMS")
    s.add_argument("tag")
    s.add_argument("--key", help=f"the private key (default {DEFAULT_KEY})")
    s.add_argument("--commit", help="the commit the tag must name")
    s.add_argument("--upload", action="store_true", help="attach the two files with gh")
    s.set_defaults(fn=cmd_sign)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
