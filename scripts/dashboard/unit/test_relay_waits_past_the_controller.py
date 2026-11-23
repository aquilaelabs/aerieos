"""A session's relayed verb waits past the longest the controller takes (B995).

The relay's client gave up at 200 s, and 960 s for a release, while the
controller may wait 120 s for a slot and run a verb 180 s (900 s for a
release or a rehearsal): a write that landed was reported as timed out with
exit 1, and a retry made it twice. relay.py's waits are read here beside
bbrelay's limits, so a limit moved on one side alone fails."""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import bbrelay  # noqa: E402

RELAY = open(os.path.join(HERE, "..", "..", "lib", "relay.py"), encoding="utf-8").read()


def waits(name):
    m = re.search(rf"(?m)^{name} = ([0-9 +]+)$", RELAY)
    assert m, name
    return sum(int(x) for x in m.group(1).split("+"))


class Waits(unittest.TestCase):
    def test_the_client_outwaits_a_slot_and_the_verb(self):
        self.assertGreater(waits("WAIT_S"), bbrelay.SLOT_WAIT_S + bbrelay.relay_limit(["bug", "add", "x"]))
        self.assertGreater(waits("WAIT_LONG_S"), bbrelay.SLOT_WAIT_S + bbrelay.relay_limit(["version", "release"]))
        self.assertGreater(waits("WAIT_LONG_S"), bbrelay.SLOT_WAIT_S + bbrelay.relay_limit(["version", "rehearse"]))
        self.assertIn("timeout=WAIT_LONG_S if", RELAY)


if __name__ == "__main__":
    unittest.main()
