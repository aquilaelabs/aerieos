"""How a newer pin is found, and what an install does with what the entry
carries for it (pack format 5). An entry says how its newest version is
found (source.version, a declared download's track, a repository's
source.track) and how the new file's digest is learned (found): for the
tool that proposes a pin, tools/pins.py, and for no install. Here: the
resolvers that tool asks, each for the platform it names; an install that
fills a declared download's {version} from the entry with nobody asked; and
a repository fetched at its pinned commit under the tag and the branch its
entry names."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sdkstore  # noqa: E402
from sdkstore import OTHER, PLATFORM, sdkmeta  # noqa: E402


def answers(pages):
    """sdkmeta.get standing in for the network: `pages` by address."""
    def get(url, decode=True):
        if url not in pages:
            raise AssertionError(f"asked for {url}")
        body = pages[url]
        body = body if isinstance(body, str) else json.dumps(body)
        return body if decode else body.encode()
    return mock.patch.object(sdkmeta, "get", get)


def day(ago):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 86400 * ago))


class Resolvers(unittest.TestCase):
    def row(self, version, **source):
        return {"name": "kit", "source": {"kind": "tarball", "version": version, **source}}

    def test_match_reads_a_version_out_of_a_document_its_publisher_serves(self):
        spec = {"resolver": "match", "url": "https://example.com/release.toml", "match": "^version = '([^']+)'"}
        with answers({spec["url"]: "schema-version = '1'\nversion = '1.29.3'\n"}):
            self.assertEqual(sdkmeta.newest(self.row(spec)), ("1.29.3", ""))
            # A pattern with no group is its whole match, and one that matches nothing is said.
            self.assertEqual(sdkmeta.newest(self.row({**spec, "match": "1\\.\\d+\\.\\d+"}))[0], "1.29.3")
            with mock.patch.object(sdkmeta, "die", side_effect=SystemExit) as die, self.assertRaises(SystemExit):
                sdkmeta.newest(self.row({**spec, "match": "^release = (.+)"}))
            self.assertIn("holds nothing its resolver's pattern matches", die.call_args[0][0])

    def test_a_release_s_tag_is_read_whole_and_with_its_last_part(self):
        spec = {"resolver": "github-release", "repo": "a/a"}
        for landed, version in (("https://github.com/a/a/releases/tag/jdk-21.0.13%2B9", "jdk-21.0.13+9"),
                                ("https://github.com/a/a/releases/tag/kit/v271.2085.0", "v271.2085.0")):
            with mock.patch.object(sdkmeta, "final_url", return_value=landed):
                self.assertEqual(sdkmeta.newest(self.row(spec)), (version, ""))

    def releases(self):
        asset = lambda tag, name: {"name": name, "browser_download_url": f"https://github.com/a/a/releases/download/{tag}/{name}"}  # noqa: E731
        return [{"tag_name": "latest", "published_at": day(0), "assets": [asset("latest", "kit-latest-linux64.tar.xz")]},
                {"tag_name": "build-9", "published_at": day(1), "prerelease": True, "assets": []},
                {"tag_name": "build-8", "published_at": day(2), "assets": [asset("build-8", "kit-N-8-linux64.tar.xz"), asset("build-8", "kit-N-8-linuxarm64.tar.xz")]},
                {"tag_name": "build-7", "published_at": day(20), "assets": [asset("build-7", "kit-N-7-linux64.tar.xz"), asset("build-7", "kit-N-7-linuxarm64.tar.xz")]}]

    def test_a_release_may_be_picked_by_its_tag_its_age_and_an_asset_s_name(self):
        pages = {"https://api.github.com/repos/a/a/releases?per_page=100": self.releases()}
        spec = {"resolver": "github-release", "repo": "a/a", "tag": "^build-",
                "asset": {"linux/amd64": "^kit-N-.*-linux64\\.tar\\.xz$", "linux/arm64": "^kit-N-.*-linuxarm64\\.tar\\.xz$"}}
        with answers(pages), mock.patch.object(sdkmeta, "AS_PLATFORM", "linux/amd64"):
            # The newest whose tag matches, a prerelease left out; the resolver supplies the address.
            self.assertEqual(sdkmeta.newest(self.row(spec)), ("build-8", "https://github.com/a/a/releases/download/build-8/kit-N-8-linux64.tar.xz"))
            # One that has been out long enough: a publisher that keeps only some builds for good.
            self.assertEqual(sdkmeta.newest(self.row({**spec, "settled": 15})), ("build-7", "https://github.com/a/a/releases/download/build-7/kit-N-7-linux64.tar.xz"))
            self.assertEqual(sdkmeta.newest(self.row({"resolver": "github-release", "repo": "a/a", "tag": "^build-", "trim_prefix": "build-"})), ("8", ""))
        with answers(pages), mock.patch.object(sdkmeta, "AS_PLATFORM", "linux/arm64"):
            self.assertEqual(sdkmeta.newest(self.row(spec))[1], "https://github.com/a/a/releases/download/build-8/kit-N-8-linuxarm64.tar.xz")
        with answers(pages), mock.patch.object(sdkmeta, "AS_PLATFORM", "darwin/arm64"), \
                mock.patch.object(sdkmeta, "die", side_effect=SystemExit) as die, self.assertRaises(SystemExit):
            sdkmeta.newest(self.row(spec))
        self.assertEqual(die.call_args[0][0], "kit: its resolver names no asset for darwin/arm64")

    def test_an_asset_alone_is_looked_for_in_the_release_called_latest_asked_for_by_itself(self):
        # A publisher with a thousand files a release: its list of releases is never asked for.
        pages = {"https://api.github.com/repos/a/a/releases/latest": self.releases()[2]}
        spec = {"resolver": "github-release", "repo": "a/a", "asset": "^kit-N-\\d+-linux64\\.tar\\.xz$"}
        with answers(pages):
            self.assertEqual(sdkmeta.newest(self.row(spec)), ("build-8", "https://github.com/a/a/releases/download/build-8/kit-N-8-linux64.tar.xz"))

    def test_a_repository_s_commit_is_found_at_its_newest_tag_or_a_branch_s_head(self):
        listing = "\n".join(f"{c * 40}\trefs/tags/{t}" for c, t in (("1", "3.9.0"), ("2", "3.10.0"), ("3", "3.10.1"), ("4", "3.11.0-0.1.pre"),
                                                                     ("5", "v1.0.0"), ("6", "3.10.2"), ("7", "3.10.2^{}"))) + "\n"
        row = {"name": "kit", "source": {"kind": "git", "url": "https://example.com/kit.git", "track": {"resolver": "git-tag", "match": "^\\d+\\.\\d+\\.\\d+$"}}}
        with mock.patch.object(sdkmeta, "git_refs", return_value=listing) as refs:
            # By version order, a pre-release and another naming left out; an annotated tag is the commit it names.
            self.assertEqual(sdkmeta.git_newest(row), ("3.10.2", "7" * 40))
            self.assertEqual(refs.call_args[0], ("https://example.com/kit.git", "refs/tags/*"))
        with mock.patch.object(sdkmeta, "git_refs", return_value=f"{'a' * 40}\trefs/heads/stable\n") as refs:
            self.assertEqual(sdkmeta.git_newest(row, {"resolver": "git-branch", "branch": "stable"}), ("stable", "a" * 40))
            self.assertEqual(refs.call_args[0], ("https://example.com/kit.git", "refs/heads/stable"))
        with self.assertRaises(ValueError):
            sdkmeta.git_refs("file:///etc")

    def test_a_field_answers_for_the_platform_the_tool_names(self):
        value = {"linux/amd64": "x64", "linux-musl/amd64": "x64-musl", "linux/*": "any", "darwin/*": "mac"}
        for plat, got in (("linux/amd64", "x64"), ("linux-musl/amd64", "x64-musl"), ("linux/arm64", "any"), ("linux-musl/arm64", "any"),
                          ("darwin/arm64", "mac"), ("darwin/*", "mac"), ("linux/*", "any")):
            with mock.patch.object(sdkmeta, "AS_PLATFORM", plat):
                self.assertEqual(sdkmeta.for_platform(value), got, plat)
        with mock.patch.object(sdkmeta, "AS_PLATFORM", "darwin/amd64"):
            self.assertEqual(sdkmeta.for_platform({"linux/amd64": "x64"}), "")
        # At an install nothing is named, and the machine's own answers.
        self.assertEqual(sdkmeta.AS_PLATFORM, "")
        self.assertEqual(sdkmeta.for_platform({PLATFORM: "mine", OTHER: "theirs"}), "mine")

    def test_a_digest_is_learned_by_a_pin_s_found_as_by_a_checksum(self):
        row = {"name": "kit", "source": {"kind": "tarball", "url": "https://example.com/{version}/kit.tgz",
                                         "checksum": {"from": "pin", "version": "1.0", "sha256": "ab" * 32, "found": {"from": "file", "url": "{url}.sha256"}}}}
        with answers({"https://example.com/2.0/kit.tgz.sha256": "cd" * 32 + " *kit.tgz\n"}):
            self.assertEqual(sdkmeta.checksum(row, "https://example.com/2.0/kit.tgz", "2.0", row["source"]["checksum"]["found"]),
                             ("sha256", "cd" * 32, "https://example.com/2.0/kit.tgz.sha256"))
        # With none handed over, it is the row's own: the pin, with nobody asked.
        with mock.patch.object(sdkmeta, "get", side_effect=AssertionError("the network was asked")):
            self.assertEqual(sdkmeta.checksum(row, "https://example.com/1.0/kit.tgz", "1.0")[1], "ab" * 32)


class Installs(sdkstore.KitCase):
    def test_a_declared_download_s_version_fills_its_address_with_nobody_asked(self):
        url, sha = self.s.file("data-4.2.bin", "forty-two")
        track = {"resolver": "text", "url": "https://nowhere.invalid/VERSION"}
        self.kit(fetch=[{"url": "file://" + self.s.files + "/data-{version}.bin", "version": "4.2", "sha256": sha, "to": "dl/data.bin",
                         "track": track, "found": {"from": "file", "url": "{url}.sha256"}}])
        rc, out = self.s.sh("sdk_install kit", PATH=self.s.can_cut())
        self.assertEqual(rc, 0, out)
        self.assertIn(f"fetching dl/data.bin from {url}", out)
        self.assertIn("kit holds forty-two", out)
        row = self.s.rows["kit"]
        self.assertEqual(sdkmeta.declared_plan(row)[1].split("\x1f")[:4], ["fetch", url, sha, "dl/data.bin"])
        self.assertEqual(sdkmeta.download_urls(row)[-1], url)
        signed = {"source": {"fetch": [{"url": "https://example.com/{version}/a", "version": "7", "to": "a",
                                        "signed": {"sig": "https://example.com/{version}/a.sig", "keys": "a.asc"}}]}}
        self.assertEqual(sdkmeta.declared_plan(signed)[1].split("\x1f"), ["fetch", "https://example.com/7/a", "", "a", "https://example.com/7/a.sig", "a.asc"])


class Repository(unittest.TestCase):
    """A shipped row's repository at the commit its entry pins."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.s = sdkstore.Store(self.root)
        self.repo = os.path.join(self.root, "repo")
        os.makedirs(os.path.join(self.repo, "bin"))
        with open(os.path.join(self.repo, "bin", "kit"), "w") as f:
            f.write("#!/bin/sh\ncd \"$(dirname \"$0\")/..\"\n"
                    "echo \"kit $(git describe --tags --exact-match 2>/dev/null || echo unknown) on $(git rev-parse --abbrev-ref HEAD) "
                    "from $(git config --get remote.origin.url || echo nowhere)\"\n")
        os.chmod(os.path.join(self.repo, "bin", "kit"), 0o755)
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "one")
        self.git("tag", "1.2.0")
        self.commit = self.git("rev-parse", "HEAD")

    def git(self, *args):
        return subprocess.run(["git", "-C", self.repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "init.defaultBranch=stable", *args],
                              check=True, capture_output=True, text=True).stdout.strip()

    def row(self, **source):
        return self.s.row("kit", {"kind": "git", "url": self.repo, "commit": self.commit, "fresh_only": True, "safe_directory": True,
                                  "verify": ["{dir}/bin/kit"], "offline": True, **source})

    def test_it_is_fetched_by_its_hash_and_keeps_the_tag_and_the_branch_its_entry_names(self):
        self.row(tag="1.2.0", branch="stable")
        rc, out = self.s.sh("sdk_install kit")
        self.assertEqual(rc, 0, out)
        self.assertIn(f"kit 1.2.0 on stable from {self.repo}", out, "the tool reads its version, its branch and its origin as from a clone")
        self.assertEqual(self.s.read("kit", ".bb-verified"), f"sha1\t{self.commit}\tthe commit its entry pins\n")
        # With neither named, the checkout is the commit and nothing more, as a pack's is.
        self.s.sh("sdk_remove kit")
        self.row()
        rc, out = self.s.sh("sdk_install kit")
        self.assertEqual(rc, 0, out)
        self.assertIn("kit unknown on HEAD from nowhere", out)
        # What a check has on offer is the commit, and an update goes through the entry.
        rc, out, _ = self.s.meta("offer", "kit")
        self.assertEqual(out, f"{self.commit[:8]}\t\n")

    def test_an_update_of_it_installs_the_commit_its_entry_pins_now(self):
        self.row(tag="1.2.0", branch="stable")
        rc, out = self.s.sh("sdk_install kit")
        self.assertEqual(rc, 0, out)
        # The pin moves in the entry: a second commit, under its own tag.
        with open(os.path.join(self.repo, "more"), "w") as f:
            f.write("two\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "two")
        self.git("tag", "1.3.0")
        first, self.commit = self.commit, self.git("rev-parse", "HEAD")
        self.row(tag="1.3.0", branch="stable")
        rc, out = self.s.sh("sdk_update kit")
        self.assertEqual(rc, 0, out)
        self.assertIn("updating kit to what its entry pins", out)
        self.assertIn(f"kit 1.3.0 on stable from {self.repo}", out)
        self.assertEqual(self.s.read("kit", ".bb-verified"), f"sha1\t{self.commit}\tthe commit its entry pins\n")
        self.assertNotEqual(first, self.commit)

    def test_a_tag_that_has_moved_off_the_pinned_commit_installs_nothing(self):
        with open(os.path.join(self.repo, "more"), "w") as f:
            f.write("two\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "two")
        self.git("tag", "-f", "1.2.0")
        # The entry still pins the first commit; the tag now names the second.
        self.git("branch", "old", self.commit)
        self.row(tag="1.2.0", branch="stable")
        rc, out = self.s.sh("sdk_install kit; echo went-on")
        self.assertNotEqual(rc, 0)
        self.assertIn(f"kit: the tag 1.2.0 is at {self.git('rev-parse', '--short', 'HEAD')} and its entry pins {self.commit[:12]}: nothing was installed", out)
        self.assertNotIn("went-on", out)
        self.assertFalse(os.path.exists(self.s.dir("kit")))


if __name__ == "__main__":
    unittest.main()
