"""Who the node agent's file and PUT verbs answer (channel.py's node_only,
FILES and PUTS): a node's own token and nobody else's, refused in the words
a released agent reads, before anything behind the verb is asked; the one
file an enrollment token or the operator's login may have (download); and
the answer a file verb gives the server to send."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import channel  # noqa: E402

NODE = {"kind": "node", "node": "n_1", "principal": "node:n_1", "token": "t_1"}
# Each caller that is not an enrolled node's token, as nodes.authenticate
# says it, with the refusal's words.
OTHERS = {
    "no token": ({"error": "no token"}, "no token"),
    "a token nobody issued": ({"error": "unknown token"}, "unknown token"),
    "a retired node's": ({"error": "credential revoked"}, "credential revoked"),
    "an enrollment token": ({"kind": "enroll", "node": "n_9", "principal": "node:n_9", "token": "t_9"}, "a node's token"),
}
Q = {"job": ["j_1"], "digest": ["abc"], "project": ["app"], "path": ["a"], "upload": ["0123456789abcdef"], "what": ["bundle"]}
# The verbs a released agent asks for by name: the last part of its path.
FILE_VERBS = ["claude-file", "devdata", "devimage", "file", "iso", "source", "sync-file", "sync-tar"]
PUT_VERBS = ["artifact", "claude-put", "devdata-put", "devimage-put", "oldapps-put", "scan-put", "signing-put", "sync-put"]


class Door(unittest.TestCase):
    def setUp(self):
        self.was = (channel.nodes.job, channel.nodes.agent_file, channel.workspace.bundle, channel.workspace.path_for)
        self.asked = []

        def never(*a, **kw):
            self.asked.append(a)
            raise AssertionError("asked before the caller was known")
        channel.nodes.job = channel.workspace.path_for = never
        channel.nodes.agent_file = lambda: {"body": b"the agent", "digest": "d_1"}
        channel.workspace.bundle = lambda: {"body": b"the bundle", "digest": "d_2"}

    def tearDown(self):
        channel.nodes.job, channel.nodes.agent_file, channel.workspace.bundle, channel.workspace.path_for = self.was

    def test_the_tables_are_the_verbs_an_agent_names(self):
        self.assertEqual(sorted(channel.FILES), FILE_VERBS)
        self.assertEqual(sorted(channel.PUTS), PUT_VERBS)
        self.assertNotIn("download", channel.FILES)

    def test_the_server_s_door_reads_the_tables(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "server.py"), encoding="utf-8") as f:
            src = f.read()
        door = src[src.index("    def _agent(self):"):src.index("    def _device(self):")]
        for name in ("channel.FILES", "channel.PUTS", "channel.fetch(", 'verb == "download"'):
            self.assertIn(name, door)

    def test_a_file_verb_answers_only_a_node_s_token(self):
        for verb in FILE_VERBS:
            for who, (auth, words) in OTHERS.items():
                self.assertEqual(channel.FILES[verb](auth, Q), ({"error": words}, 401), f"{verb} as {who}")
                self.assertEqual(channel.fetch(verb, auth, Q, authed=lambda: True), ({"error": words}, 401), f"{verb} as {who}")
        self.assertEqual(self.asked, [])

    def test_a_put_verb_answers_only_a_node_s_token(self):
        for verb in PUT_VERBS:
            for who, (auth, words) in OTHERS.items():
                self.assertEqual(channel.PUTS[verb](auth, Q, None, 0), ({"error": words}, 401), f"{verb} as {who}")
        self.assertEqual(self.asked, [])

    def test_the_bundle_is_a_node_s_and_carries_its_digest(self):
        for who, (auth, words) in OTHERS.items():
            self.assertEqual(channel.fetch("download", auth, Q, authed=lambda: True), ({"error": words}, 401), who)
        got, status = channel.fetch("download", NODE, Q, authed=lambda: False)
        self.assertEqual(status, 200)
        self.assertEqual(got, {"body": b"the bundle", "ctype": "application/x-tar", "headers": {"X-Bundle-Digest": "d_2"}})

    def test_the_agent_itself_needs_no_enrolled_node(self):
        want = {"body": b"the agent", "ctype": "text/x-python; charset=utf-8", "headers": {"X-Agent-Digest": "d_1"}}
        q = {"what": [""]}
        # An enrollment token, before there is a node; a node updating itself.
        self.assertEqual(channel.fetch("download", OTHERS["an enrollment token"][0], q, authed=lambda: False), (want, 200))
        self.assertEqual(channel.fetch("download", NODE, q, authed=lambda: False), (want, 200))
        # No token of the door's, with the operator's own login.
        self.assertEqual(channel.fetch("download", {"error": "no token"}, q, authed=lambda: True), (want, 200))
        # Neither: refused in the token's own words.
        for who in ("no token", "a token nobody issued", "a retired node's"):
            auth, words = OTHERS[who]
            self.assertEqual(channel.fetch("download", auth, q, authed=lambda: False), ({"error": words}, 401), who)

    def test_a_verb_behind_the_check_keeps_its_name_and_its_words(self):
        self.assertEqual(channel.sync_put.__name__, "sync_put")
        self.assertIn("raw in the body", channel.sync_put.__doc__)

    def test_a_node_s_own_ask_reaches_the_verb(self):
        channel.workspace.path_for = lambda digest: None
        self.assertEqual(channel.fetch("source", NODE, Q, authed=lambda: False),
                         ({"error": "no such snapshot: the tree has moved on; queue the job again"}, 404))
        channel.workspace.path_for = lambda digest: "/snapshots/" + digest
        self.assertEqual(channel.fetch("source", NODE, Q, authed=lambda: False),
                         ({"path": "/snapshots/abc", "ctype": "application/x-tar", "headers": {}}, 200))


class IsoAnswer(unittest.TestCase):
    """An ISO uploaded on the VMs page, fetched by its node's running job: the
    answer is the Path, which the server asks for its size (B1035: a string
    was handed over and the fetch was a server error)."""

    def setUp(self):
        import pathlib
        import tempfile
        self.dir = tempfile.mkdtemp()
        self.iso = pathlib.Path(self.dir) / "0123456789abcdef.iso"
        self.iso.write_bytes(b"iso")
        self.was = (channel.nodes.job, channel.vms.upload_path)
        channel.nodes.job = lambda jid, with_log=False: {"node": "n_1", "state": "running",
                                                         "spec": {"iso": {"upload": "0123456789abcdef"}}}
        channel.vms.upload_path = lambda up: self.iso if up == "0123456789abcdef" else None

    def tearDown(self):
        channel.nodes.job, channel.vms.upload_path = self.was

    def test_the_answer_is_a_path_the_server_can_size(self):
        got, status = channel.fetch("iso", NODE, Q, authed=lambda: False)
        self.assertEqual(status, 200)
        self.assertEqual(got["path"].stat().st_size, 3)
        self.assertEqual(got["path"], self.iso)


class FileAnswer(unittest.TestCase):
    def test_a_path_and_its_type_with_no_header_of_its_own(self):
        self.assertEqual(channel._file("/a/b"), ({"path": "/a/b", "ctype": "application/octet-stream", "headers": {}}, 200))
        self.assertEqual(channel._file("/a/b.tar", "application/x-tar"),
                         ({"path": "/a/b.tar", "ctype": "application/x-tar", "headers": {}}, 200))
        self.assertEqual(list(channel._file("/a/b")[0]), ["path", "ctype", "headers"])

    def test_each_answer_s_headers_are_its_own(self):
        one, two = channel._file("/a")[0], channel._file("/b")[0]
        one["headers"]["X-One"] = "1"
        self.assertEqual(two["headers"], {})


if __name__ == "__main__":
    unittest.main()
