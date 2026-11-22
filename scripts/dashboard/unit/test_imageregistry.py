"""A registry asked what it serves (imageregistry.py): one client for the
protocol, whatever the host. A stand-in answers in the registry's place:
the anonymous token its challenge names is asked for once and sent back,
a tag answers the digest of its manifest list, a manifest's body is held
to its digest, and a tag that does not exist is said by name."""
import hashlib
import io
import json
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import imageregistry  # noqa: E402

LIST = json.dumps({"schemaVersion": 2, "mediaType": imageregistry.INDEXES[0], "manifests": [
    {"digest": "sha256:" + "1" * 64, "platform": {"os": "linux", "architecture": "amd64"}},
    {"digest": "sha256:" + "2" * 64, "platform": {"os": "linux", "architecture": "arm64"}},
    {"digest": "sha256:" + "3" * 64, "platform": {"os": "unknown", "architecture": "unknown"}}]}).encode()
LIST_DIGEST = "sha256:" + hashlib.sha256(LIST).hexdigest()


class Answer(io.BytesIO):
    def __init__(self, body=b"", headers=None):
        super().__init__(body)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class Registry:
    """A host that speaks the protocol: a manifest per (repository,
    reference), behind a token where `realm` is set."""

    def __init__(self, manifests, realm="", say_digest=True):
        self.manifests, self.realm, self.say_digest, self.asked = manifests, realm, say_digest, []

    def __call__(self, req, timeout=None):
        if isinstance(req, str):
            self.asked.append(("GET", req, ""))
            return Answer(json.dumps({"token": "t0ken"}).encode())
        url, method, auth = req.full_url, req.get_method(), req.get_header("Authorization") or ""
        self.asked.append((method, url, auth))
        if self.realm and auth != "Bearer t0ken":
            raise urllib.error.HTTPError(url, 401, "Unauthorized", {"WWW-Authenticate": f'Bearer realm="{self.realm}",service="reg.example",scope="repository:app/web:pull"'}, io.BytesIO())
        host, _, rest = url.removeprefix("https://").partition("/v2/")
        repo, _, reference = rest.partition("/manifests/")
        body = self.manifests.get((host, repo, reference))
        if body is None:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO())
        headers = {"Docker-Content-Digest": "sha256:" + hashlib.sha256(body).hexdigest()} if self.say_digest else {}
        return Answer(body if method == "GET" else b"", headers)


class Case(unittest.TestCase):
    def stand_in(self, registry):
        self.addCleanup(setattr, imageregistry, "_open", imageregistry._open)
        imageregistry._open = registry
        return registry


class Parse(unittest.TestCase):
    def test_a_reference_is_its_host_repository_tag_and_digest(self):
        d = "sha256:" + "c" * 64
        p = imageregistry.parse
        self.assertEqual(p("mariadb:11"), (imageregistry.DEFAULT_HOST, "library/mariadb", "11", ""))
        self.assertEqual(p("linuxserver/radarr"), (imageregistry.DEFAULT_HOST, "linuxserver/radarr", "latest", ""))
        self.assertEqual(p("reg.example/app/web:1.2"), ("reg.example", "app/web", "1.2", ""))
        self.assertEqual(p("localhost:5000/app:1"), ("localhost:5000", "app", "1", ""))
        # docker.io/NAME is the default registry said by name, not a host to ask.
        self.assertEqual(p("docker.io/valkey/valkey:8"), (imageregistry.DEFAULT_HOST, "valkey/valkey", "8", ""))
        self.assertEqual(p("docker.io/nginx:1"), (imageregistry.DEFAULT_HOST, "library/nginx", "1", ""))
        self.assertEqual(p("index.docker.io/library/nginx:1"), (imageregistry.DEFAULT_HOST, "library/nginx", "1", ""))
        self.assertEqual(p(f"reg.example/app/web:1.2@{d}"), ("reg.example", "app/web", "1.2", d))
        self.assertEqual(p(f"nginx@{d}"), (imageregistry.DEFAULT_HOST, "library/nginx", "", d), "a digest with no tag: nothing to ask a registry about")
        for bad in ("", "a b:1", "nginx:1@sha256:abc", "nginx:1@md5:" + "c" * 64, "reg.example/../x:1", "reg.example/App:1", "nginx:-1"):
            self.assertIsNone(p(bad), bad)


class Asked(Case):
    def test_a_tag_answers_the_digest_of_its_manifest_list_with_the_token_its_host_names(self):
        reg = self.stand_in(Registry({("reg.example", "app/web", "1.2"): LIST}, realm="https://auth.example/token"))
        self.assertEqual(imageregistry.digest_of("reg.example/app/web:1.2"), (LIST_DIGEST, ""))
        self.assertEqual([(m, u) for m, u, _ in reg.asked],
                         [("HEAD", "https://reg.example/v2/app/web/manifests/1.2"),
                          ("GET", "https://auth.example/token?service=reg.example&scope=repository%3Aapp%2Fweb%3Apull"),
                          ("HEAD", "https://reg.example/v2/app/web/manifests/1.2")],
                         "the challenge's realm is asked once, and the tag again with the token")
        self.assertEqual(reg.asked[-1][2], "Bearer t0ken")

    def test_a_host_that_asks_for_no_token_is_asked_once(self):
        reg = self.stand_in(Registry({(imageregistry.DEFAULT_HOST, "library/web", "1"): LIST}))
        self.assertEqual(imageregistry.digest_of("web:1"), (LIST_DIGEST, ""))
        self.assertEqual(len(reg.asked), 1)

    def test_a_host_that_names_no_digest_has_its_manifest_hashed_here(self):
        self.stand_in(Registry({("reg.example", "app/web", "1.2"): LIST}, say_digest=False))
        self.assertEqual(imageregistry.digest_of("reg.example/app/web:1.2"), (LIST_DIGEST, ""))

    def test_a_tag_that_does_not_exist_is_said_by_name(self):
        self.stand_in(Registry({}, realm="https://auth.example/token"))
        self.assertEqual(imageregistry.digest_of("reg.example/app/web:9"), ("", "reg.example has no app/web:9"))

    def test_a_challenge_that_names_no_https_realm_is_a_sign_in_it_does_not_have(self):
        self.stand_in(Registry({}, realm="http://auth.example/token"))
        self.assertIn("asks for a sign-in", imageregistry.digest_of("reg.example/app/web:1")[1])

    def test_a_host_that_cannot_be_reached_says_so(self):
        def gone(req, timeout=None):
            raise urllib.error.URLError("no route")
        self.stand_in(gone)
        self.assertIn("could not reach reg.example", imageregistry.digest_of("reg.example/app/web:1")[1])

    def test_a_reference_with_no_tag_is_not_asked(self):
        reg = self.stand_in(Registry({}))
        self.assertIn("names no tag", imageregistry.digest_of("nginx@sha256:" + "c" * 64)[1])
        self.assertEqual(reg.asked, [])


class Manifest(Case):
    def test_a_manifest_is_read_by_its_digest_and_names_its_platforms(self):
        reg = self.stand_in(Registry({("reg.example", "app/web", LIST_DIGEST): LIST}))
        digest, doc, err = imageregistry.manifest_of(f"reg.example/app/web:1.2@{LIST_DIGEST}", by_digest=True)
        self.assertEqual((digest, err), (LIST_DIGEST, ""))
        self.assertEqual(reg.asked[0][1], f"https://reg.example/v2/app/web/manifests/{LIST_DIGEST}", "asked by the digest, never the tag beside it")
        self.assertEqual(imageregistry.platforms_of(doc), ["linux/amd64", "linux/arm64"], "what a list carries besides images is left out")
        self.assertEqual(imageregistry.platforms_of({"config": {}}), [], "one image's own manifest names none")

    def test_a_body_that_is_not_the_digest_asked_for_is_refused(self):
        other = "sha256:" + "d" * 64
        self.stand_in(Registry({("reg.example", "app/web", other): LIST}))
        digest, doc, err = imageregistry.manifest_of(f"reg.example/app/web:1.2@{other}", by_digest=True)
        self.assertEqual((digest, doc), ("", {}))
        self.assertIn(f"is not {other}", err)

    def test_a_reference_with_no_digest_cannot_be_read_by_one(self):
        self.assertIn("names no digest", imageregistry.manifest_of("reg.example/app/web:1.2", by_digest=True)[2])


if __name__ == "__main__":
    unittest.main()
