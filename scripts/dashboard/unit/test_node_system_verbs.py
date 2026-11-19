"""The verbs that queue a system job on a node share two pieces: the
refusal for a node that cannot be acted on (locked to its own console
first, then an agent that is not dialing in) and the queueing itself, a
job_add followed by the verb's own audit row once the job is queued. Held
here on a few verbs: the sentences, the spec the agent is sent, and the
audit row, with no store behind them."""
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import nodes  # noqa: E402

AWAY = "box's agent is not dialing in, so nothing from here reaches the machine"
LOCKED = "system changes on box are locked to its own console"


def row(**over):
    n = {"id": "n1", "name": "box", "kind": "agent", "state": "online", "live": True, "config": {},
         "reported": {"sandbox": True, "administers": True, "door": {"kind": "cloudflared"}}}
    n.update(over)
    return n


class Verbs(unittest.TestCase):
    def call(self, n, verb, *args, add=None, **patches):
        """One verb on the row `n`: its answer, what job_add was handed and
        what audit was handed."""
        self.added, self.audited = [], []

        def job_add(*a):
            self.added.append(a)
            return dict(add or {"ok": True, "job": "j1"})
        with mock.patch.multiple(nodes, node=lambda node_id: n, job_add=job_add,
                                 audit=lambda *a: self.audited.append(a), **patches):
            return getattr(nodes, verb)("user:t", "n1", *args)

    def test_a_locked_node_refuses_before_a_node_that_is_away(self):
        for n in (row(config={"lock": True}), row(config={"lock": True}, live=False)):
            for verb, args in (("node_door", (True,)), ("node_gpu_display_off", ()), ("node_power", ("reboot",))):
                r = self.call(n, verb, *args, jobs_for=lambda **k: [])
                self.assertIn(LOCKED, r["error"], verb)
                self.assertEqual((self.added, self.audited), ([], []), verb)

    def test_a_node_that_is_away_is_told_in_one_sentence(self):
        n = row(live=False)
        for verb, args in (("node_door", (True,)), ("node_gpu_display_off", ()), ("node_storage_measure", ()),
                           ("node_feature", ("vmhost", "remove"))):
            self.assertEqual(self.call(n, verb, *args), {"error": AWAY}, verb)
            self.assertEqual((self.added, self.audited), ([], []), verb)
        # A power verb ends it with where the machine is restarted instead.
        self.assertEqual(self.call(n, "node_power", "reboot", jobs_for=lambda **k: []),
                         {"error": AWAY + ": reboot it from its console or its hypervisor"})
        self.assertEqual(self.call(n, "node_power", "poweroff", jobs_for=lambda **k: []),
                         {"error": AWAY + ": shut down it from its console or its hypervisor"})

    def test_a_verb_the_lock_does_not_cover_asks_only_for_the_agent(self):
        n = row(config={"lock": True})
        self.assertTrue(self.call(n, "node_storage_measure").get("ok"))
        self.assertEqual(self.added, [("user:t", {"node": "n1"}, "storage", {"timeout": 900})])
        self.assertEqual(self.call(row(config={"lock": True}, live=False), "node_storage_measure"), {"error": AWAY})

    def test_a_healthy_node_is_queued_the_spec_and_audited_once(self):
        r = self.call(row(), "node_door", False)
        self.assertEqual(r, {"ok": True, "job": "j1"})
        self.assertEqual(self.added, [("user:t", {"node": "n1"}, "system", {"apply": "door", "config": {"on": False}, "timeout": 300})])
        self.assertEqual(self.audited, [("user:t", "node-door", "n1", {"job": "j1", "on": False})])
        # The spec's keys in the order the agent has always been sent them.
        self.assertEqual(list(self.added[0][3]), ["apply", "config", "timeout"])

        self.call(row(), "node_gpu_display_off")
        self.assertEqual(self.added[0][3], {"apply": "gpu-off", "config": {}, "timeout": 300})
        self.assertEqual(self.audited, [("user:t", "node-gpu-display-off", "n1", {"job": "j1"})])

        self.call(row(), "node_feature", "vmhost", "remove")
        self.assertEqual(self.added[0][3], {"apply": "feature", "config": {"id": "vmhost", "op": "remove"}, "timeout": 1800})
        self.assertEqual(self.audited, [("user:t", "node-feature", "n1", {"job": "j1", "id": "vmhost", "op": "remove"})])

    def test_a_refusal_from_the_queue_is_handed_back_and_not_audited(self):
        no = {"error": "node is draining; it takes no new work"}
        for verb, args in (("node_door", (True,)), ("node_power", ("reboot",)), ("node_apply", ("network",))):
            n = row(config={"desired": {"network": {"dhcp": True}}})
            self.assertEqual(self.call(n, verb, *args, add=no, jobs_for=lambda **k: [{"type": "toolchain"}]), no, verb)
            self.assertEqual(len(self.added), 1, verb)
            self.assertEqual(self.audited, [], verb)

    def test_power_says_what_it_waits_for_beside_the_job(self):
        r = self.call(row(), "node_power", "poweroff", jobs_for=lambda **k: [{"type": "toolchain"}])
        self.assertEqual(r["job"], "j1")
        self.assertIn("a toolchain install or removal is running on box", r["waits"])
        self.assertEqual(self.added[0][3], {"apply": "poweroff", "config": {}, "timeout": 60})
        self.assertEqual(self.audited, [("user:t", "node-poweroff", "n1", {"job": "j1"})])
        self.assertNotIn("waits", self.call(row(), "node_power", "reboot", jobs_for=lambda **k: []))

    def test_an_apply_that_moves_a_store_is_marked_quiet_in_the_spec(self):
        n = row(config={"desired": {"stores": {"toolchains": "/new"}}})
        n["reported"]["stores"] = {"toolchains": {"path": "/old"}}
        self.call(n, "node_apply", "storage")
        spec = self.added[0][3]
        self.assertEqual(list(spec), ["apply", "config", "timeout", "quiet"])
        self.assertEqual((spec["apply"], spec["timeout"], spec["quiet"]), ("storage", 6 * 3600 + 900, True))
        self.assertEqual(self.audited, [("user:t", "node-apply", "n1", {"job": "j1", "what": "storage"})])
        self.call(row(config={"desired": {"network": {"dhcp": True}}}), "node_apply", "network")
        self.assertEqual(self.added[0][3], {"apply": "network", "config": {"network": {"dhcp": True}}, "timeout": 900})


if __name__ == "__main__":
    unittest.main()
