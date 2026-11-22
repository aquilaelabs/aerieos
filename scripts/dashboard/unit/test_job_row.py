"""A job in a list carries a spec that names it and no more (nodes.job_row):
a system job's whole configuration and an exec's script stay with the job,
read whole by its id."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import nodes  # noqa: E402


class JobRow(unittest.TestCase):
    def test_a_small_spec_is_the_same(self):
        j = {"id": "j_1", "type": "compose", "spec": {"action": "rebuild", "instance": "main", "names": ["a", "b"],
                                                      "plan": {"steps": 2}, "timeout": 600, "title": None}}
        self.assertEqual(nodes.job_row(j), j)

    def test_the_bulk_is_left_with_the_job(self):
        script = "x" * 60000
        j = {"id": "j_2", "type": "system", "log": "kept",
             "spec": {"apply": "root", "argv": ["bash", "-c", script], "config": {"files": {"a": script}},
                      "text": script, "names": [str(i) for i in range(500)],
                      "steps": [{"big": script}, {"small": 1}]}}
        row = nodes.job_row(j)
        self.assertLess(len(json.dumps(row)), 6000)
        s = row["spec"]
        self.assertEqual(s["apply"], "root")
        self.assertEqual(s["argv"][:2], ["bash", "-c"])
        self.assertTrue(s["argv"][2].startswith("x" * 80) and s["argv"][2].endswith("…"))
        self.assertNotIn("config", s)
        self.assertEqual(len(s["names"]), nodes.ROW_ITEMS)
        self.assertEqual(s["steps"], [{"small": 1}])
        self.assertEqual(row["log"], "kept")
        # The job itself is as it was: the row is a copy.
        self.assertEqual(len(j["spec"]["argv"][2]), 60000)
        self.assertIn("config", j["spec"])

    def test_what_is_the_nodes_alone_is_not_read_with_the_job(self):
        # B796: a sign-in job's spec carried the session token minted for
        # its flow to every reader of the list.
        j = {"id": "j_4", "type": "claude-login", "spec": {"uid": "u_1", "timeout": 900, "token": "bbs_secret", "agent": "claude"}}
        self.assertEqual(nodes.job_read(j)["spec"], {"uid": "u_1", "timeout": 900, "agent": "claude"})
        self.assertEqual(j["spec"]["token"], "bbs_secret", "the job itself, which the node is handed, is as it was")
        plain = {"id": "j_5", "type": "exec", "spec": {"argv": ["true"]}}
        self.assertIs(nodes.job_read(plain), plain)
        self.assertEqual(nodes.job_read({"id": "j_6", "spec": None}), {"id": "j_6", "spec": None})

    def test_a_job_with_no_spec(self):
        self.assertEqual(nodes.job_row({"id": "j_3", "spec": None}), {"id": "j_3", "spec": None})
        self.assertEqual(nodes.job_row({"id": "j_4"}), {"id": "j_4"})


if __name__ == "__main__":
    unittest.main()
