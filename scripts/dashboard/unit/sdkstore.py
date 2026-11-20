"""A toolchain store and a catalog of made-up rows, for the unit tests of
the installer: `aerie toolchains` itself (scripts/lib/sdk.sh under aerie's
own set -e, with sdkmeta.py reading the rows), run against files on disk
through BB_TOOLCHAINS_JSON, so a whole install is proved with no network
and nowhere near the real store. Not a test: the tests import it."""
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "lib"))
import sdkmeta  # noqa: E402

# The machine the tests run on, as a row keys what differs by machine.
PLATFORM = sdkmeta.this_platform()
OTHER = "darwin/arm64" if PLATFORM != "darwin/arm64" else "linux/amd64"

PREAMBLE = """set -euo pipefail
. "$BB_LIB/common.sh"
. "$BB_LIB/sdk.sh"
sdk_operator_only() { :; }
"""


class Store:
    """One temporary directory: the store installs land in, the files the
    rows download, and the catalog that names them."""

    def __init__(self, root):
        self.root = root
        self.store = os.path.join(root, "store")
        self.files = os.path.join(root, "files")
        self.catalog = os.path.join(root, "toolchains.json")
        self.rows = {}
        for d in (self.store, self.files, os.path.join(root, "home"), os.path.join(root, "tmp")):
            os.makedirs(d)
        self.write()

    def file(self, name, data):
        """A file a row downloads: (its file:// address, its sha256)."""
        data = data if isinstance(data, bytes) else data.encode()
        path = os.path.join(self.files, name)
        with open(path, "wb") as f:
            f.write(data)
        return "file://" + path, hashlib.sha256(data).hexdigest()

    def tarball(self, name, members):
        """A .tar.gz of {path: text}, each file executable."""
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for path, text in sorted(members.items()):
                info = tarfile.TarInfo(path)
                info.size, info.mode = len(text.encode()), 0o755
                tar.addfile(info, io.BytesIO(text.encode()))
        return self.file(name, buf.getvalue())

    def row(self, name, source, **more):
        """Add or replace a row, and write the catalog."""
        self.rows[name] = {"name": name, "label": name, "probe": name, "about": name, "platforms": [PLATFORM],
                           "layout": {"bin": ["bin"], "env": {}, "tool": ""}, "source": source, **more}
        self.write()
        return self.rows[name]

    def write(self):
        with open(self.catalog, "w") as f:
            json.dump({"toolchains": list(self.rows.values())}, f)

    def can_cut(self):
        """A PATH whose `unshare` stands in for a node's that can cut the
        network for a step: it runs what it is handed with CUT=yes in its
        environment, so a step can say whether it ran behind the cut.
        Whether this machine lets an account make a network namespace is
        not what these tests ask."""
        d = os.path.join(self.root, "cutbin")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "unshare"), "w") as f:
            f.write('#!/bin/sh\nwhile [ $# -gt 0 ]; do case "$1" in --*) shift ;; *) break ;; esac; done\n'
                    '[ $# -gt 0 ] || exit 0\nCUT=yes exec "$@"\n')
        os.chmod(os.path.join(d, "unshare"), 0o755)
        return d + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin")

    def dir(self, name):
        return os.path.join(self.store, "here", name)

    def read(self, name, rel):
        with open(os.path.join(self.dir(name), rel), encoding="utf-8") as f:
            return f.read()

    def env(self, **more):
        keep = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "BB_AGENT", "ANDROID_HOME", "BB_NODE_TOOLCHAINS")}
        return {**keep, "BB_TOOLCHAINS_JSON": self.catalog, "BB_SCRIPTS": os.path.join(REPO, "scripts"),
                "BB_LIB": os.path.join(REPO, "scripts", "lib"), "SDK_ROOT": self.store, "BB_SDK_SCOPE": "here",
                "HOME": os.path.join(self.root, "home"), "BUILDER_HOME": os.path.join(self.root, "home"),
                "TMPDIR": os.path.join(self.root, "tmp"), "BB_TOOLPACKS_FILE_URLS": "1",
                "BUILDERBOT_NETCUT_BIN": os.path.join(self.root, "no-helper"), **more}

    def sh(self, script, **env):
        """Run `script` with sdk.sh sourced: (exit code, what it said)."""
        p = subprocess.run(["bash", "-c", PREAMBLE + script], capture_output=True, text=True, check=False,
                           env=self.env(**env), timeout=120)
        return p.returncode, p.stdout + p.stderr

    def meta(self, *args, **env):
        """sdkmeta.py as the shell calls it: (exit code, stdout, stderr)."""
        p = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "lib", "sdkmeta.py"), *args],
                           capture_output=True, text=True, check=False, env=self.env(**env), timeout=60)
        return p.returncode, p.stdout, p.stderr
