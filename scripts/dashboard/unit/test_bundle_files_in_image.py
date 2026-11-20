"""The image holds every file of the bundle a checkout lists (R267 step 6):
a release signs the list of the bundle's files as the tree holds them
(tools/sign-agent.py, scripts/lib/bundleparts.py), the controller packs the
bundle from the image's own, and a node that pinned the release key refuses
a bundle one listed file short. A file the tree lists and the image drops is
every pinned node refusing every bundle of that release.

What this reads, and what it does not: the Dockerfile and .dockerignore as
text. No image is built here. A COPY line is read in its plain form, `COPY
SRC DEST`, the one the Dockerfile keeps for what lands under /opt/aerieos
(install-controller.sh lays a release out from the same lines). A
.dockerignore rule is read as Docker documents it: matched from the
context's root against the path and each folder above it, `*` within one
name, `**` across folders, the last rule that matches deciding. It is read
a second time with a rule that names no folder matched at any depth, the
wider reading, so the file holds under either. What a RUN line does to a
file after it was copied is not read: the Dockerfile's only one that touches
these is the bytecode it compiles, which the list leaves out."""
import os
import re
import sys
import unittest

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "lib"))
import bundleparts  # noqa: E402


def copies():
    """(source in the tree, destination in the image) of every plain COPY line."""
    out = []
    with open(os.path.join(REPO, "Dockerfile"), encoding="utf-8") as f:
        for ln in f.read().splitlines():
            m = re.fullmatch(r"COPY (\S+) (\S+)", ln.strip())
            if m:
                out.append((m.group(1), m.group(2)))
    return out


def copied_to(name):
    """Where the image holds the tree's `name`, by the COPY lines: the file
    itself named, or a folder above it copied whole. [] when none does."""
    out = []
    for src, dst in copies():
        s = src.rstrip("/")
        if name == s:
            out.append(dst.rstrip("/"))
        elif name.startswith(s + "/"):
            out.append(dst.rstrip("/") + name[len(s):])
    return out


def rules():
    """.dockerignore's rules in order: (whether it keeps, its pattern)."""
    out = []
    with open(os.path.join(REPO, ".dockerignore"), encoding="utf-8") as f:
        for ln in f.read().splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                out.append((ln.startswith("!"), ln.lstrip("!").strip("/")))
    return out


def pattern(pat):
    """A .dockerignore pattern as a regular expression over a whole path."""
    rx, i = "", 0
    while i < len(pat):
        if pat.startswith("**/", i):
            rx, i = rx + "(?:[^/]+/)*", i + 3
        elif pat.startswith("**", i):
            rx, i = rx + ".*", i + 2
        elif pat[i] == "*":
            rx, i = rx + "[^/]*", i + 1
        elif pat[i] == "?":
            rx, i = rx + "[^/]", i + 1
        else:
            rx, i = rx + re.escape(pat[i]), i + 1
    return re.compile(rx)


def dropped(name, anywhere=False):
    """Whether .dockerignore keeps `name` out of the build: the last rule
    that matches it, or a folder above it, decides. With `anywhere`, a rule
    that names no folder is matched at any depth too."""
    parts = name.split("/")
    above = ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]
    out = False
    for keeps, pat in rules():
        pats = [pat] + (["**/" + pat] if anywhere and "/" not in pat else [])
        if any(pattern(p).fullmatch(a) for p in pats for a in above):
            out = not keeps
    return out


class InTheImage(unittest.TestCase):
    def test_the_two_readers_read_what_they_say(self):
        self.assertEqual(copied_to("scripts/lib/sdk.sh"), ["/opt/aerieos/scripts/lib/sdk.sh"])
        self.assertEqual(copied_to("nodes/bb-session"), ["/opt/aerieos/nodes/bb-session"])
        self.assertEqual(copied_to("nodes/not-copied"), [])
        self.assertTrue(dropped("README.md") and dropped("docs/img/shot.png") and dropped(".git/config"))
        self.assertFalse(dropped("docs/install.md") or dropped("CHANGELOG.md") or dropped("scripts/lib/sdk.sh"))
        self.assertTrue(dropped("scripts/lib/__pycache__/sdkmeta.cpython-312.pyc"))
        self.assertFalse(dropped("config/notes.md"), "Docker matches *.md at the context's root alone")
        self.assertTrue(dropped("config/notes.md", anywhere=True), "the wider reading drops it at any depth")

    def test_every_listed_file_is_copied_to_the_same_place(self):
        listed = [name for name, _path in bundleparts.files(REPO)]
        self.assertGreater(len(listed), 50, "the tree lists the bundle's files")
        # One or two are copied to a second place as well, for the build's own steps.
        wrong = [name for name in listed if "/opt/aerieos/" + name not in copied_to(name)]
        self.assertEqual(wrong, [], "the Dockerfile copies these to no place, or not to /opt/aerieos/<the same name>: "
                                    "the bundle an image packs would be short of what its release signed")

    def test_no_listed_file_is_dropped_by_dockerignore(self):
        listed = [name for name, _path in bundleparts.files(REPO)]
        self.assertIn("config/release-keys/README.md", listed, "the one file a *.md rule would drop")
        for anywhere in (False, True):
            gone = [name for name in listed if dropped(name, anywhere)]
            self.assertEqual(gone, [], ".dockerignore keeps these out of the image" + (", read the wider way" if anywhere else "")
                             + ": the bundle an image packs would be short of what its release signed")

    def test_what_the_list_leaves_out_is_what_an_image_and_a_checkout_differ_by(self):
        # The image compiles the scripts' bytecode (the Dockerfile's
        # compileall), a checkout has none, and the list counts neither.
        with open(os.path.join(REPO, "Dockerfile"), encoding="utf-8") as f:
            self.assertIn("python3 -m compileall", f.read())
        self.assertIn("__pycache__", bundleparts.SKIP_DIRS)
        self.assertTrue(all(not n.endswith(".pyc") and "__pycache__" not in n for n, _p in bundleparts.files(REPO)))


if __name__ == "__main__":
    unittest.main()
