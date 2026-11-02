"""bb-ftpd's question to its agent (bbftp.Asker): a login is asked over the
pipes the agent started it with, and a pipe that closes means the agent is
gone. An agent updating itself execs in place, keeping its pid, so the
server's parent watch never saw it and the server held the port refusing
every login (B573): it ends instead, leaving the port to the new agent's.
pyftpdlib is stood in for, so this runs without it."""
import io
import json
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
for name in ("pyftpdlib", "pyftpdlib.authorizers", "pyftpdlib.handlers", "pyftpdlib.servers"):
    sys.modules.setdefault(name, types.ModuleType(name))
_auth = sys.modules["pyftpdlib.authorizers"]
if not hasattr(_auth, "DummyAuthorizer"):
    vars(_auth).update(AuthenticationFailed=type("AuthenticationFailed", (Exception,), {}),
                       DummyAuthorizer=type("DummyAuthorizer", (), {}))
    vars(sys.modules["pyftpdlib.handlers"]).update(TLS_FTPHandler=type("TLS_FTPHandler", (), {}))
    vars(sys.modules["pyftpdlib.servers"]).update(ThreadedFTPServer=type("ThreadedFTPServer", (), {}))
import bbftp  # noqa: E402


class Ended(Exception):
    pass


class Asker(unittest.TestCase):
    def test_an_answer_comes_back(self):
        out = io.StringIO()
        got = bbftp.Asker(out=out, inp=io.StringIO(json.dumps({"id": 1, "access": "rw"}) + "\n")).ask("ann", "pw", "10.0.0.5")
        self.assertEqual(got.get("access"), "rw")
        self.assertEqual(json.loads(out.getvalue())["user"], "ann")

    def test_a_closed_pipe_ends_the_server(self):
        def end(code):
            raise Ended(code)
        real, bbftp.os._exit = bbftp.os._exit, end
        try:
            with self.assertRaises(Ended):
                bbftp.Asker(out=io.StringIO(), inp=io.StringIO("")).ask("ann", "pw", "10.0.0.5")
        finally:
            bbftp.os._exit = real


if __name__ == "__main__":
    unittest.main()
