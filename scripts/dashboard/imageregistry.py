"""A container registry asked what it serves: one client for the protocol.

An image reference names a registry, a repository and a tag, and may carry
the digest of the manifest it means: `name[:tag][@sha256:<64 hex>]`. A
registry is whatever host speaks the
distribution protocol (the v2 API): a manifest is read at
/v2/REPOSITORY/manifests/REFERENCE, and where the host answers 401 its
challenge names where an anonymous token is given (realm, service, scope),
which is asked for once and sent back. Nothing here knows one registry
from another: the host is the one the reference names, and the two
defaults below are the reference grammar's own, what a name with no host
in it means to every client of the protocol.

What is asked: the digest a tag serves now (digest_of: the manifest
list's, for an image built for several platforms, which is what a pull by
digest takes and what covers every platform in it), and a manifest itself
with the platforms a list names (manifest_of), each body held to the
digest it was asked or answered by. Nothing is pulled, and a private
image says it could not be read.

No imports from the rest of the dashboard: tools/pins.py loads this as it
loads packformat.py, and imagecheck.py asks through it.
"""
import hashlib
import http.client
import json
import re
import urllib.error
import urllib.parse
import urllib.request

# What a reference with no host in it means, and a repository of one word
# there: the reference grammar's defaults.
DEFAULT_HOST = "registry-1.docker.io"
DEFAULT_NAMESPACE = "library"
# The kinds of manifest asked for: a list of several platforms' first.
INDEXES = ("application/vnd.oci.image.index.v1+json", "application/vnd.docker.distribution.manifest.list.v2+json")
ACCEPT = ", ".join([*INDEXES, "application/vnd.docker.distribution.manifest.v2+json", "application/vnd.oci.image.manifest.v1+json"])
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
# A reference's parts as they go into an address: nothing that could name
# another path or another host.
HOST = re.compile(r"[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?(:\d{1,5})?")
NAME = re.compile(r"[a-z0-9]+([._-]+[a-z0-9]+)*(/[a-z0-9]+([._-]+[a-z0-9]+)*)*")
TAG = re.compile(r"[\w][\w.-]{0,127}")
MANIFEST_MAX = 4_000_000
TIMEOUT = 20
# What opens an address: a test stands in for it.
_open = urllib.request.urlopen


def parse(ref):
    """(host, repository, tag, digest) of an image reference, or None for
    what is none. The tag is "latest" where it names neither a tag nor a
    digest, and "" beside a digest with no tag. A first part with a dot or
    a port in it is the registry's host."""
    ref, at, digest = str(ref or "").strip().partition("@")
    if not ref or any(c.isspace() for c in ref) or (at and not DIGEST.fullmatch(digest)):
        return None
    first, _, rest = ref.partition("/")
    if rest and ("." in first or ":" in first or first == "localhost"):
        host, path = first, rest
    else:
        host, path = DEFAULT_HOST, ref
    repo, _, tag = path.rpartition(":") if ":" in path.rsplit("/", 1)[-1] else (path, "", "")
    if not repo or not NAME.fullmatch(repo) or (tag and not TAG.fullmatch(tag)) or not HOST.fullmatch(host):
        return None
    if host == DEFAULT_HOST and "/" not in repo:
        repo = f"{DEFAULT_NAMESPACE}/{repo}"
    return host, repo, tag or ("" if digest else "latest"), digest


def _ask(host, repo, reference, method):
    """(headers, body) of a manifest's answer, with the anonymous token its
    host's challenge names where it asks for one. HTTPError for an answer
    that is no manifest."""
    url = f"https://{host}/v2/{repo}/manifests/{reference}"

    def once(token=""):
        req = urllib.request.Request(url, method=method, headers={"Accept": ACCEPT} | ({"Authorization": f"Bearer {token}"} if token else {}))
        with _open(req, timeout=TIMEOUT) as r:   # noqa: S310 (https to the registry the reference names)  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            return r.headers, (r.read(MANIFEST_MAX + 1) if method == "GET" else b"")
    try:
        return once()
    except urllib.error.HTTPError as e:
        if e.code != 401:
            raise
        # The anonymous token the challenge names: realm, service, scope.
        ch = dict(re.findall(r'(\w+)="([^"]*)"', e.headers.get("WWW-Authenticate") or ""))
        if not ch.get("realm", "").startswith("https://"):
            raise PermissionError(f"{host} asks for a sign-in this check does not have") from e
        q = urllib.parse.urlencode({k: v for k, v in (("service", ch.get("service")), ("scope", ch.get("scope") or f"repository:{repo}:pull")) if v})
        with _open(f"{ch['realm']}?{q}", timeout=TIMEOUT) as r:   # noqa: S310 (the realm the registry named, https)  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            tok = json.loads(r.read(200_000).decode("utf-8", "replace"))
        return once(tok.get("token") or tok.get("access_token") or "")


def _said(e, host, repo, reference):
    """Why a registry gave no answer, in a line."""
    if isinstance(e, PermissionError):
        return str(e)
    if isinstance(e, urllib.error.HTTPError):
        return (f"{host} has no {repo}:{reference}" if e.code == 404
                else f"{host} would not say ({e.code}): a private image needs a sign-in this check does not have")
    return f"could not reach {host}: {e}"[:200]


ERRORS = (OSError, http.client.HTTPException, ValueError)


def manifest_of(ref, by_digest=False):
    """(digest, document, error) for the manifest a reference means: the
    one its tag serves now, or with `by_digest` the one its digest names.
    The body is held to its digest: the one asked by, or the one the host
    answered with, and a body that is neither is refused."""
    parts = parse(ref)
    if not parts or (by_digest and not parts[3]):
        return "", {}, f"{ref} is no image reference" if not parts else f"{ref} names no digest"
    host, repo, tag, pinned = parts
    reference = pinned if by_digest or not tag else tag
    try:
        headers, body = _ask(host, repo, reference, "GET")
        if len(body) > MANIFEST_MAX:
            return "", {}, f"{host} answered more than a manifest for {repo}:{reference}"
        got = "sha256:" + hashlib.sha256(body).hexdigest()
        want = reference if DIGEST.fullmatch(reference) else headers.get("Docker-Content-Digest") or got
        if got != want:
            return "", {}, f"{host} answered a manifest for {repo}:{reference} that is not {want}"
        doc = json.loads(body.decode("utf-8"))
    except ERRORS as e:
        return "", {}, _said(e, host, repo, reference)
    return got, doc if isinstance(doc, dict) else {}, ""


def digest_of(ref):
    """(digest, error): what the registry serves for this reference's tag
    now. Asked by HEAD, which answers the digest and no body; a host that
    names none there is asked for the manifest, which is hashed here."""
    parts = parse(ref)
    if not parts or not parts[2]:
        return "", f"{ref} names no tag to ask a registry about"
    host, repo, tag, _pinned = parts
    try:
        headers, _ = _ask(host, repo, tag, "HEAD")
    except ERRORS as e:
        return "", _said(e, host, repo, tag)
    got = headers.get("Docker-Content-Digest") or ""
    if not DIGEST.fullmatch(got):
        got, _doc, err = manifest_of(f"{ref.partition('@')[0]}")
        if err or not got:
            return "", err or f"{host} gave no digest for {repo}:{tag}"
    return got, ""


def platforms_of(doc):
    """The platforms a manifest list names, as "<os>/<arch>", in its order
    and each once; [] for one image's own manifest, which names none. What
    a list carries besides images (an attestation, under unknown/unknown)
    is left out."""
    out = []
    for m in doc.get("manifests") if isinstance(doc.get("manifests"), list) else []:
        p = m.get("platform") if isinstance(m, dict) and isinstance(m.get("platform"), dict) else {}
        plat = f"{p.get('os')}/{p.get('architecture')}"
        if p.get("os") and p.get("architecture") and "unknown" not in plat and plat not in out:
            out.append(plat)
    return out
