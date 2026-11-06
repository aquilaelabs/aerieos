"""What a node says of a VM's network and its host's networks reaches the
page (R219 step 4): the controller's cleaning kept net to lan or project,
so a VM on a bridge read as its space's and its Hardware dialog would have
moved it back on Save."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import nodes  # noqa: E402


class Kept(unittest.TestCase):
    def test_a_vms_network_model_and_mac(self):
        got = nodes._vm_hw({"net": "br:virbr0", "model": "e1000", "mac": "52:54:00:AA:BB:CC", "cpuset": []})
        self.assertEqual((got["net"], got["model"], got["mac"]), ("br:virbr0", "e1000", "52:54:00:aa:bb:cc"))
        self.assertEqual(nodes._vm_hw({"net": "net:default"})["net"], "net:default")
        self.assertEqual(nodes._vm_hw({"net": "net:bbvm-x"})["net"], "project")
        self.assertEqual(nodes._vm_hw({"net": "br:a b"})["net"], "project")
        self.assertNotIn("model", nodes._vm_hw({"model": "ne2000"}))
        self.assertNotIn("mac", nodes._vm_hw({"mac": "nope"}))
        self.assertIs(nodes._vm_hw({"tpm": True})["tpm"], True)
        self.assertNotIn("tpm", nodes._vm_hw({"tpm": "yes"}))


if __name__ == "__main__":
    unittest.main()
