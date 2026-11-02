"""tools/release-attach.sh: one release per tag, found among the drafts,
made once, every file uploaded to it by id (2 Nov: v0.9.0-dev.4797 got two
drafts, the apps on one and the OS image on the other)."""
import json
import os
import stat
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "..", "..", "..", "tools", "release-attach.sh")

# A gh that records its calls and answers the release list from a file the
# test writes: no release, then the one `release create` made.
FAKE_GH = r'''#!/usr/bin/env bash
echo "$*" >> "$GH_LOG"
case "$1 $2" in
  "api repos/*/releases?per_page=100"*|"api repos/"*"/releases?per_page=100")
    case "$*" in
      *startswith*)
        python3 -c '
import json,sys
rows=json.load(open(sys.argv[2])); tag=sys.argv[1]
for r in rows:
    if r.get("name")==tag and r["tag_name"].startswith("untagged-"): print(r["id"], r["tag_name"])' "$GH_TAG" "$GH_RELEASES" ;;
      *)
        python3 -c '
import json,sys
rows=json.load(open(sys.argv[2])); tag=sys.argv[1]
for r in rows:
    if r["tag_name"]==tag: print(r["id"])' "$GH_TAG" "$GH_RELEASES" ;;
    esac ;;
  "release create")
    python3 - "$GH_RELEASES" <<EOF
import json,sys
p=sys.argv[1]; rows=json.load(open(p)); rows.append({"id": 777, "tag_name": "$3", "draft": True}); json.dump(rows, open(p,"w"))
EOF
    ;;
  "api repos/"*"/assets?per_page=100")
    echo "" ;;
  "api --method")
    ;;
esac
exit 0
'''


class ReleaseAttach(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.gh = os.path.join(self.d, "gh")
        with open(self.gh, "w", encoding="utf-8") as f:
            f.write(FAKE_GH)
        os.chmod(self.gh, os.stat(self.gh).st_mode | stat.S_IEXEC)
        self.releases = os.path.join(self.d, "releases.json")
        self.log = os.path.join(self.d, "gh.log")
        self.env = dict(os.environ, PATH=self.d + os.pathsep + os.environ["PATH"], GITHUB_REPOSITORY="x/y",
                        GH_TOKEN="t", GH_RELEASES=self.releases, GH_LOG=self.log, GH_TAG="v1.2.3-dev.9")
        self.f = os.path.join(self.d, "aerieos-os-1.2.3-dev.9.iso")
        with open(self.f, "wb") as f:
            f.write(b"iso")

    def run_tool(self, *a):
        return subprocess.run(["bash", TOOL, "v1.2.3-dev.9", *a], env=self.env, capture_output=True, text=True,
                              timeout=60, check=False)

    def calls(self):
        with open(self.log, encoding="utf-8") as f:
            return f.read().splitlines()

    def test_the_first_job_makes_the_draft_and_the_next_finds_it(self):
        with open(self.releases, "w", encoding="utf-8") as f:
            json.dump([{"id": 1, "tag_name": "v1.0.0", "draft": False}], f)
        r = self.run_tool(self.f)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("release 777 made for v1.2.3-dev.9 (a draft)", r.stdout)
        made = [c for c in self.calls() if c.startswith("release create")]
        self.assertEqual(len(made), 1)
        self.assertIn("--draft", made[0])
        self.assertIn("--prerelease", made[0], "a dev tag is a pre-release")
        self.assertIn("--latest=false", made[0])
        up = [c for c in self.calls() if "uploads.github.com" in c]
        self.assertEqual(len(up), 1)
        self.assertIn("/releases/777/assets?name=aerieos-os-1.2.3-dev.9.iso", up[0])
        # The next job, with its own file: the draft found, none made.
        os.unlink(self.log)
        g = os.path.join(self.d, "aerieos-app-1.2.3-dev.9.apk")
        with open(g, "wb") as f:
            f.write(b"apk")
        r = self.run_tool(g)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("release 777 is v1.2.3-dev.9's", r.stdout)
        self.assertFalse([c for c in self.calls() if c.startswith("release create")], "one draft, never two")
        self.assertTrue([c for c in self.calls() if "/releases/777/assets?name=aerieos-app" in c])

    def test_a_release_published_under_an_untagged_name_gets_its_tag_back(self):
        # 2 Nov: the 4818 draft was published from GitHub's form with its tag
        # field lost, so it went out as untagged-ID with a git tag of that
        # name; the OS job would have made a second release.
        with open(self.releases, "w", encoding="utf-8") as f:
            json.dump([{"id": 55, "tag_name": "untagged-2a746c4a", "name": "v1.2.3-dev.9", "draft": False}], f)
        r = self.run_tool(self.f)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("release 55 is v1.2.3-dev.9's", r.stdout)
        self.assertIn("was published as untagged-2a746c4a: its tag set back to v1.2.3-dev.9", r.stderr)
        calls = self.calls()
        self.assertFalse([c for c in calls if c.startswith("release create")], "mended, not made again")
        self.assertTrue([c for c in calls if "--method PATCH repos/x/y/releases/55" in c and "tag_name=v1.2.3-dev.9" in c], calls)
        self.assertTrue([c for c in calls if "--method DELETE repos/x/y/git/refs/tags/untagged-2a746c4a" in c], calls)
        self.assertTrue([c for c in calls if "/releases/55/assets?name=aerieos-os-1.2.3-dev.9.iso" in c])

    def test_a_stable_tag_is_a_draft_and_no_pre_release(self):
        with open(self.releases, "w", encoding="utf-8") as f:
            json.dump([], f)
        self.env["GH_TAG"] = "v1.2.3"
        r = subprocess.run(["bash", TOOL, "v1.2.3", self.f], env=self.env, capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        made = [c for c in self.calls() if c.startswith("release create")][0]
        self.assertIn("--draft", made)
        self.assertNotIn("--prerelease", made)


if __name__ == "__main__":
    unittest.main()
