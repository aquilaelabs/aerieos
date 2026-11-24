"""Who may cancel a job (server.py's _job_cancel_why, R277): an
administrator any; a session its own space's; a person one on a node they
hold Jobs Write on, or one of a space they hold Spaces Write on; and a job
this account does not read is answered as one it does not have. Held here
without a server: the method is lifted out of server.py's source and run
against stand-ins for the accounts."""
import ast
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = open(os.path.join(HERE, "..", "server.py"), encoding="utf-8").read()


class _Users:
    @staticmethod
    def is_admin(u):
        return u.get("admin", False)

    @staticmethod
    def may_work(u, name):
        return name == u.get("session")

    @staticmethod
    def may_node(u, action, nid):
        assert action == "jobs", action
        return "" if nid in u.get("jobs_on", ()) else "no Jobs Write there"

    @staticmethod
    def may(u, action, project=None):
        assert action == "work", action
        return "" if project in u.get("writes", ()) else "no Spaces Write there"


def handler():
    lines = SERVER.splitlines()
    cls = next(n for n in ast.parse(SERVER).body if isinstance(n, ast.ClassDef) and n.name == "Handler")
    f = next(f for f in cls.body if isinstance(f, ast.FunctionDef) and f.name == "_job_cancel_why")
    ns = {"users": _Users}
    exec("class Lifted:\n" + "\n".join(lines[f.lineno - 1:f.end_lineno]), ns)  # noqa: S102 (the repository's own source)

    class Stand(ns["Lifted"]):
        def __init__(self, reads):
            self.reads = reads

        def _jobs_scope(self):
            return self.reads, None

    return Stand


Stand = handler()
JOB = {"id": "j1", "project": "alpha", "node": "n1", "state": "running"}


class Cancel(unittest.TestCase):
    def why(self, me, reads=frozenset({"alpha"}), job=JOB):
        return Stand(set(reads))._job_cancel_why(me, job)

    def test_an_administrator_cancels_any(self):
        self.assertEqual(self.why({"admin": True}, reads=set()), "")

    def test_a_session_its_own_space_s_alone(self):
        self.assertEqual(self.why({"session": "alpha"}), "")
        self.assertEqual(self.why({"session": "beta"}), "unseen")

    def test_a_reader_of_the_space_does_not(self):
        # Spaces Read on alpha, which lists the job, is not Write.
        why = self.why({"name": "reader"})
        self.assertTrue(why and why != "unseen", why)

    def test_spaces_write_on_its_space_does(self):
        self.assertEqual(self.why({"name": "dev", "writes": ["alpha"]}), "")

    def test_jobs_write_on_its_node_does_where_the_space_is_not_read(self):
        self.assertEqual(self.why({"name": "ops", "jobs_on": ["n1"]}, reads=set()), "")
        self.assertEqual(self.why({"name": "ops", "jobs_on": ["n2"]}, reads=set()), "unseen")

    def test_a_job_not_read_is_one_not_had(self):
        self.assertEqual(self.why({"name": "dev", "writes": ["alpha"]}, reads={"beta"}), "unseen")

    def test_every_job_read_still_asks_the_grant(self):
        # None: this reader lists every job (Jobs Read on every node).
        why = Stand(None)._job_cancel_why({"name": "watcher"}, JOB)
        self.assertTrue(why and why != "unseen", why)


if __name__ == "__main__":
    unittest.main()
