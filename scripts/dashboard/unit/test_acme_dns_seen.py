"""A DNS-01 record is looked for where a resolver reads it before Let's
Encrypt is asked (R226): seen, the order goes on; not seen within the wait,
it says so, rather than sleeping fifteen seconds and hoping."""
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import nginxproxy  # noqa: E402


class Seen(unittest.TestCase):
    def setUp(self):
        saved = (nginxproxy.urlopen, nginxproxy.time.sleep)
        self.addCleanup(lambda: (setattr(nginxproxy, "urlopen", saved[0]), setattr(nginxproxy.time, "sleep", saved[1])))
        nginxproxy.time.sleep = lambda s: None
        self.asked = []

    def answers(self, *bodies):
        it = iter(bodies)

        def urlopen(req, timeout=5):
            self.asked.append(req.full_url)
            return io.BytesIO(json.dumps(next(it, {"Answer": []})).encode())
        nginxproxy.urlopen = urlopen

    def test_seen_once_the_resolver_has_it(self):
        self.answers({}, {"Answer": [{"data": '"other"'}]}, {"Answer": [{"data": '"tok-1"'}]})
        self.assertTrue(nginxproxy._txt_seen("_acme-challenge.a.example", "tok-1", wait=5))
        self.assertEqual(len(self.asked), 3)
        self.assertIn("name=_acme-challenge.a.example", self.asked[0])
        self.assertIn("type=TXT", self.asked[0])

    def test_not_seen_within_the_wait_is_false(self):
        self.answers()
        self.assertFalse(nginxproxy._txt_seen("_acme-challenge.a.example", "tok-1", wait=0.2))


if __name__ == "__main__":
    unittest.main()
