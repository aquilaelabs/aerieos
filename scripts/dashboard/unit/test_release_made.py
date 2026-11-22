"""A pushed release's tag is handed on whichever channel it is on, so what
CI builds for it (the APK the controller signs) is looked for at once: a dev
release's was left to the hourly look (B469)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import version  # noqa: E402


class Made(unittest.TestCase):
    def run_release(self, dev, pushed=True, unsealed="", code=200):
        made, forged = [], []
        parts = {"PANEL": lambda _n: {}, "GIT_ENV": lambda _w, _n: {}, "CREDS_ENV": dict,
                 "MAY_PUSH": lambda _n: True, "AUDIT": lambda *_a: None,
                 "FORGE": lambda *a, **k: forged.append((a, k)) or {}, "MADE": lambda p, t: made.append((p, t)),
                 "UNSEALED": lambda _n: unsealed}
        got = {"tag": "v1.2.3-dev.7" if dev else "v1.2.3", "target": "1.2.3", "sha": "abc1234", "pushed": pushed}
        with mock.patch.multiple(version, **parts), mock.patch.object(version, "release", return_value=got) as cut:
            self.said, got_code = version.verb("app", "release", {"dev": dev}, {"name": "t"}, "p")
        self.assertEqual(got_code, code)
        self.cut = cut.called
        return made, forged

    def test_a_dev_release_is_handed_on_beside_its_forge_page_marked_a_pre_release(self):
        # R218: a pre-release's page is made too (publish leaves it to CI
        # where the space's CI makes its releases).
        made, forged = self.run_release(True)
        self.assertEqual(made, [("app", "v1.2.3-dev.7")])
        self.assertEqual(len(forged), 1)
        self.assertEqual(forged[0][1], {"pre": True})

    def test_a_stable_release_is_handed_on_beside_its_forge_page(self):
        made, forged = self.run_release(False)
        self.assertEqual(made, [("app", "v1.2.3")])
        self.assertEqual(len(forged), 1)

    def test_a_tag_not_pushed_is_not(self):
        made, _ = self.run_release(True, pushed=False)
        self.assertEqual(made, [])

    def test_a_release_the_host_would_not_finish_is_refused_before_its_tag(self):
        # v0.9.0-dev.6049: tagged, built and its APK attached, and then a
        # draft for good, the workflow that signs its list of files being
        # one GitHub would not start.
        why = "GitHub starts a workflow only from the default branch, and main has no seal.yml it can start"
        made, forged = self.run_release(True, unsealed=why, code=409)
        self.assertFalse(self.cut, "no tag is made")
        self.assertEqual((made, forged), ([], []))
        self.assertEqual(self.said["error"], f"The release would stay a draft: {why}, so put it there first")


if __name__ == "__main__":
    unittest.main()
