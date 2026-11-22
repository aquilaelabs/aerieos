"""`aerie toolchains update NAME` runs nothing a vendor serves that day
(R267 step 17). A row its entry pins updates to what the entry names, by its
own recipe (sdk_update's first branch, held in test_sdk_pin.py); the
branches after it are for a row with nothing on offer. Two of them could no
longer be reached by a shipped row, since flutter is pinned at a commit and
dotnet at a version: flutter's fetch of the head of stable, and dotnet's
freshly fetched dotnet-install.sh, which was run as it came. Both are gone,
and so is the half of the check that piped the same script into a shell to
ask what was newest.

Read out of scripts/lib/sdk.sh and the shipped table: every name the
dashboard and the agent send to `update` is either a row with an offer or
one of the branches that are left. Swift, which carries the version its
publisher's signature holds, is a row with an offer too."""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import toolchains  # noqa: E402
from sdkstore import REPO, sdkmeta  # noqa: E402


def sdk():
    with open(os.path.join(REPO, "scripts", "lib", "sdk.sh"), encoding="utf-8") as f:
        return f.read()


def update_body():
    src = sdk()
    a = src.index("sdk_update() {")
    return src[a:src.index("\n}\n", a)]


def shipped():
    with open(os.path.join(REPO, "config", "toolchains.json"), encoding="utf-8") as f:
        return {r["name"]: r for r in json.load(f)["toolchains"]}


class UpdateBranches(unittest.TestCase):
    def branches(self):
        """The names sdk_update's case has a branch for, after the pinned path."""
        body = update_body()
        case = body[body.index('    case "$what" in'):]
        return [m for m in re.findall(r"^        ([a-z:*|-]+)\)$", case, re.M)]

    def test_the_branches_left_are_the_rows_with_nothing_on_offer(self):
        self.assertEqual(self.branches(), ["playwright", "android:*"])
        rows = shipped()
        for name in ("playwright",):
            self.assertIsNone(sdkmeta.offered(rows[name]), f"{name} has no pinned version of its own: its branch is how it updates")
        android = [n for n in rows if n.startswith("android:")]
        self.assertTrue(android)
        for name in android:
            self.assertIsNone(sdkmeta.offered(rows[name]), name)

    def test_flutter_and_dotnet_update_by_what_their_entries_pin(self):
        rows = shipped()
        # Swift carries the version its signature holds (signed_version):
        # an offer too, which the pinned path takes before any branch.
        for name in ("flutter", "dotnet", "swift"):
            self.assertIsNotNone(sdkmeta.offered(rows[name]), f"{name} is a row with an offer, so the pinned path takes its update")
            self.assertNotRegex(update_body(), rf"^        {name}\)$")
        body = update_body()
        # The pinned path comes before any branch, and returns.
        self.assertLess(body.index('sdk_meta offer "$what"'), body.index('    case "$what" in'))
        for gone in ("head of stable", "dotnet-install", "FETCH_HEAD", "current LTS"):
            self.assertNotIn(gone, body)

    def test_every_name_sent_to_update_is_answered(self):
        # The dashboard's worker and the agent send these to `update` when the toolchain is installed.
        rows = shipped()
        for name in toolchains.UPDATE_VERBS:
            self.assertIn(name, rows)
            answered = sdkmeta.offered(rows[name]) is not None or any(name in b.split("|") for b in self.branches())
            self.assertTrue(answered, f"{name}: neither a row with an offer nor a branch of its own")

    def test_nothing_fetched_is_run_as_it_came(self):
        code = "\n".join(ln for ln in sdk().splitlines() if not ln.lstrip().startswith("#"))
        self.assertEqual(re.findall(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba|da|z)?sh\b", code), [], "no download piped to a shell")
        self.assertNotIn("dot.net/v1/dotnet-install.sh", code)
        self.assertEqual(re.findall(r"^\s*(?:ba)?sh /tmp/\S+\.sh\b.*$", code, re.M), [], "no script fetched to /tmp and run")
        self.assertNotIn("| bash -s", code)


if __name__ == "__main__":
    unittest.main()
