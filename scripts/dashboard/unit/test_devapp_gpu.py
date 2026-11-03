"""A container given the machine's GPU (R207 step 4): a setting of the
instance, nvidia or amd, laid over its compose as a file AerieOS writes
naming every service, last of the -f files; never kept as text a person
edits."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import devapp  # noqa: E402


def write_json(path, d):
    with open(path, "w") as f:
        json.dump(d, f)


class Gpu(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gpu-"))
        self.was = {k: getattr(devapp, k, None) for k in ("WORKSPACE", "STATE", "FILE", "OWNERS", "ENVDIR", "write_json", "label_of")}
        ws, st = self.tmp / "ws", self.tmp / "state"
        st.mkdir()
        devapp.configure(workspace=ws, state=st, write_json=write_json)
        (ws / "alpha").mkdir(parents=True)
        (ws / "alpha" / "compose.yml").write_text("services:\n  web:\n    build: .\n  db:\n    image: postgres\n")
        self.assertTrue(devapp.create_instance("alpha", "web-a").get("ok"))

    def tearDown(self):
        for k, v in self.was.items():
            setattr(devapp, k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_setting_is_nvidia_or_amd_or_none(self):
        self.assertIn("nvidia or amd", devapp.set_gpu("alpha", "web-a", "intel").get("error", ""))
        self.assertEqual(devapp.set_gpu("alpha", "web-a", "nvidia"), {"ok": True, "gpu": "nvidia"})
        self.assertEqual(devapp.gpu_of("alpha", "web-a"), "nvidia")
        self.assertEqual(devapp.set_gpu("alpha", "web-a", ""), {"ok": True, "gpu": ""})
        self.assertEqual(devapp.gpu_of("alpha", "web-a"), "")

    def test_the_file_names_every_service_and_comes_last(self):
        devapp.set_gpu("alpha", "web-a", "nvidia")
        with mock.patch.object(devapp, "_service_names", return_value=["web", "db"]):
            argv = devapp._compose("alpha", "web-a", "config")
        fs = [argv[i + 1] for i, a in enumerate(argv) if a == "-f"]
        self.assertEqual(len(fs), 2, argv)
        self.assertTrue(fs[-1].endswith(".gpu.yml"), fs)
        text = Path(fs[-1]).read_text()
        self.assertIn("  web:\n    deploy:", text)
        self.assertIn("  db:\n    deploy:", text)
        self.assertIn("driver: nvidia", text)
        # ...and the resolved compose asks for the card, as the gate reads it.
        self.assertEqual(devapp.gpu_asks({"services": {"web": {"deploy": {"resources": {"reservations": {"devices": [{"driver": "nvidia", "capabilities": ["gpu"]}]}}}}}}), ["web"])
        devapp.set_gpu("alpha", "web-a", "amd")
        with mock.patch.object(devapp, "_service_names", return_value=["web"]):
            argv = devapp._compose("alpha", "web-a", "config")
        text = Path([argv[i + 1] for i, a in enumerate(argv) if a == "-f"][-1]).read_text()
        self.assertIn("/dev/dri:/dev/dri", text)
        self.assertNotIn("nvidia", text)

    def test_no_service_or_no_setting_lays_nothing_over(self):
        with mock.patch.object(devapp, "_service_names", return_value=["web"]):
            self.assertEqual(devapp._compose("alpha", "web-a", "config").count("-f"), 1)
        devapp.set_gpu("alpha", "web-a", "amd")
        with mock.patch.object(devapp, "_service_names", return_value=[]):
            self.assertEqual(devapp._compose("alpha", "web-a", "config").count("-f"), 1)
        # The names are asked of compose without the GPU file, or it would ask itself.
        seen = []
        with mock.patch.object(devapp, "_run", side_effect=lambda argv, **k: seen.append(argv) or {"code": 0, "out": "web\n"}):
            devapp._service_names("alpha", "web-a")
        self.assertEqual(seen[0].count("-f"), 1)
        self.assertIn("--services", seen[0])


if __name__ == "__main__":
    unittest.main()
