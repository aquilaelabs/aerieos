"""A release withdrawn takes its tag with it, on GitHub, and a tag whose
release is already gone goes alone (R190 step 3): the 0.9.0 dev release
left a tag GitHub would not delete beside its release, and a tag with no
release, each deleted by hand."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import forgerelease  # noqa: E402

API = forgerelease.API + "/repos/o/r"


class Forge:
    def __init__(self, release=True, tag=True, pkgs=None, versions=None, person=False):
        self.release, self.tag, self.calls = release, tag, []
        self.pkgs, self.versions, self.person = pkgs or [], versions or [], person

    def __call__(self, method, url, token, body=None, data=None, ctype=None):
        self.calls.append((method, url))
        gh = forgerelease.API
        if method == "GET" and url.startswith(f"{gh}/orgs/o/packages?"):
            return None if self.person else self.pkgs
        if method == "GET" and url.startswith(f"{gh}/users/o/packages?"):
            return self.pkgs
        if method == "GET" and url.startswith(f"{gh}/{'users' if self.person else 'orgs'}/o/packages/container/r/versions?"):
            return self.versions
        if method == "DELETE" and url in (f"{gh}/orgs/o/packages/container/r/versions/1", f"{gh}/user/packages/container/r/versions/1"):
            return {}
        if url == f"{API}/releases/tags/v1.0.0-dev.5" and method == "GET":
            return {"id": 41, "prerelease": True, "assets": [{"name": "a"}, {"name": "b"}],
                    "html_url": "https://h/r"} if self.release else None
        if url == f"{API}/git/ref/tags/v1.0.0-dev.5" and method == "GET":
            return {"ref": "refs/tags/v1.0.0-dev.5"} if self.tag else None
        if method == "DELETE" and url == f"{API}/releases/41":
            self.release = False
            return {}
        if method == "DELETE" and url == f"{API}/git/refs/tags/v1.0.0-dev.5":
            self.tag = False
            return {}
        raise forgerelease.Refused(f"unexpected {method} {url}")


class Withdraw(unittest.TestCase):
    def go(self, forge, fn, *a):
        with mock.patch.object(forgerelease, "_handle", return_value=("github", "GitHub", ("o/r", "t"))), \
                mock.patch.object(forgerelease, "_req", forge):
            return fn("app", *a)

    def test_the_plan_names_what_goes(self):
        p = self.go(Forge(), forgerelease.withdraw_plan, "v1.0.0-dev.5")
        self.assertEqual((p["release"], p["tagged"], p["prerelease"], p["files"]), (True, True, True, 2))

    def test_the_release_goes_first_then_its_tag(self):
        f = Forge()
        r = self.go(f, forgerelease.withdraw, "v1.0.0-dev.5")
        self.assertEqual((r["release"], r["tagged"]), (True, True))
        dels = [u for m, u in f.calls if m == "DELETE"]
        self.assertEqual(dels, [f"{API}/releases/41", f"{API}/git/refs/tags/v1.0.0-dev.5"])
        self.assertIn("its release and its tag deleted", forgerelease.withdraw_said(r))

    def test_a_tag_left_alone_by_its_release_goes_alone(self):
        f = Forge(release=False)
        self.assertTrue(self.go(f, forgerelease.withdraw_plan, "v1.0.0-dev.5")["tagged"])
        r = self.go(f, forgerelease.withdraw, "v1.0.0-dev.5")
        self.assertEqual((r["release"], r["tagged"]), (False, True))

    def test_nothing_there_is_refused_before_anybody_is_asked(self):
        p = self.go(Forge(release=False, tag=False), forgerelease.withdraw_plan, "v1.0.0-dev.5")
        self.assertIn("neither a release nor a tag", p["error"])

    def test_the_tag_is_read_exactly_never_by_prefix(self):
        f = Forge()
        self.go(f, forgerelease.withdraw_plan, "v1.0.0-dev.5")
        self.assertNotIn(("GET", f"{API}/git/refs/tags/v1.0.0-dev.5"), f.calls)


    # B1159: the release and its tag went, and the image its build pushed
    # stayed pullable by its version.
    PKGS = [{"name": "r", "repository": {"full_name": "o/r"}}, {"name": "x", "repository": {"full_name": "o/x"}}]

    def test_the_image_its_build_pushed_goes_with_it(self):
        f = Forge(pkgs=self.PKGS, versions=[{"id": 1, "metadata": {"container": {"tags": ["1.0.0-dev.5", "sha-abc1234"]}}},
                                            {"id": 2, "metadata": {"container": {"tags": ["1.0.0-dev.4"]}}}])
        r = self.go(f, forgerelease.withdraw, "v1.0.0-dev.5")
        self.assertEqual(r.get("images"), ["ghcr.io/o/r:1.0.0-dev.5"], r)
        dels = [u for m, u in f.calls if m == "DELETE"]
        self.assertIn(f"{forgerelease.API}/orgs/o/packages/container/r/versions/1", dels)
        self.assertFalse([u for u in dels if u.endswith("/versions/2")], "another version's stays")
        self.assertFalse([u for m, u in f.calls if "/container/x/" in u], "another repository's package is not read")
        self.assertIn("its release, its tag and its image deleted", forgerelease.withdraw_said(r))

    def test_an_image_people_follow_is_kept_and_said(self):
        f = Forge(pkgs=self.PKGS, versions=[{"id": 1, "metadata": {"container": {"tags": ["1.0.0-dev.5", "dev"]}}}])
        r = self.go(f, forgerelease.withdraw, "v1.0.0-dev.5")
        self.assertNotIn("images", r)
        self.assertFalse([u for m, u in f.calls if m == "DELETE" and "/packages/" in u])
        self.assertIn("its image kept since r is also tagged dev", forgerelease.withdraw_said(r))

    def test_a_persons_image_goes_through_their_own_path(self):
        f = Forge(person=True, pkgs=self.PKGS, versions=[{"id": 1, "metadata": {"container": {"tags": ["1.0.0-dev.5"]}}}])
        r = self.go(f, forgerelease.withdraw, "v1.0.0-dev.5")
        self.assertEqual(r.get("images"), ["ghcr.io/o/r:1.0.0-dev.5"], r)
        self.assertIn(("DELETE", f"{forgerelease.API}/user/packages/container/r/versions/1"), f.calls)

    def test_a_token_that_may_not_reads_as_kept(self):
        class NoPackages(Forge):
            def __call__(self, method, url, *a, **k):
                if "/packages" in url:
                    raise forgerelease.Refused("GitHub answered 403")
                return super().__call__(method, url, *a, **k)
        r = self.go(NoPackages(), forgerelease.withdraw, "v1.0.0-dev.5")
        self.assertEqual((r["release"], r["tagged"]), (True, True))
        self.assertIn("its image kept since the token may not delete packages", forgerelease.withdraw_said(r))

    def test_only_the_packages_addresses_are_asked_beside_the_repositorys(self):
        for u in (f"{forgerelease.API}/orgs/o/packages?package_type=container", f"{forgerelease.API}/user/packages/container/r/versions/1"):
            self.assertTrue(forgerelease._PACKAGES.fullmatch(u), u)
        self.assertFalse(forgerelease._PACKAGES.fullmatch(f"{forgerelease.API}/orgs/o/members"))


class GitLabPackages(unittest.TestCase):
    def test_a_withdrawn_release_takes_its_builds_from_the_package_registry(self):
        # B561: the release and its tag went, and the package registry went
        # on serving the build.
        calls = []
        class F:
            def ask(self, method, path, body=None, data=None, ctype=None):
                calls.append((method, path))
                if method == "GET" and "/releases/" in path:
                    return {"tag_name": "v1.2.0"}
                if method == "GET" and "/repository/tags/" in path:
                    return {"name": "v1.2.0"}
                if method == "GET" and "/packages?" in path:
                    return [{"id": 5, "name": "app", "version": "1.2.0"}, {"id": 6, "name": "app", "version": "1.1.0"}]
                return {}
        ctx = (F(), {"path": "grp/app"})
        with mock.patch.object(forgerelease, "_handle", return_value=("gitlab", "GitLab", ctx)):
            r = forgerelease.withdraw("app", "v1.2.0")
        self.assertEqual(r.get("packages"), 1, r)
        self.assertIn(("DELETE", "/projects/grp%2Fapp/packages/5"), calls)
        self.assertNotIn(("DELETE", "/projects/grp%2Fapp/packages/6"), calls, "another version's stays")


if __name__ == "__main__":
    unittest.main()
