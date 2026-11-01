"""BuilderBot USB Maker (R198, tools/builderbot-usb-maker.py): the window is
tkinter's and not tested here, where there is none; what it decides without
a screen is. The settings page's fields become the stick's builderbot.env
lines or are refused with why, and the releases offered are the published
ones by tag, a dev build marked."""
import importlib.util
import json
import os
import sys
import types
import unittest
from unittest import mock

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tools")


def load():
    # tkinter stood in for: the module builds no window at import.
    tk = types.ModuleType("tkinter")
    vars(tk).update(Tk=object, StringVar=object, BooleanVar=object, Listbox=object, Text=object)
    for name, mod in (("tkinter", tk), ("tkinter.filedialog", types.ModuleType("fd")),
                      ("tkinter.messagebox", types.ModuleType("mb")), ("tkinter.ttk", types.ModuleType("ttk"))):
        sys.modules.setdefault(name, mod)
    vars(tk).update(filedialog=sys.modules["tkinter.filedialog"], messagebox=sys.modules["tkinter.messagebox"], ttk=sys.modules["tkinter.ttk"])
    spec = importlib.util.spec_from_file_location("usb_maker", os.path.join(TOOLS, "builderbot-usb-maker.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


um = load()


class Settings(unittest.TestCase):
    def test_the_fields_become_the_sticks_lines(self):
        self.assertEqual(um.settings_lines({}), [])
        self.assertEqual(um.settings_lines({"dev": True, "hostname": "tower", "tz": "Europe/London", "address": "192.168.1.20",
                                            "mask": "24", "gateway": "192.168.1.1", "dns": "1.1.1.1"}),
                         ["BB_RELEASE_CHANNEL=dev", "BB_HOSTNAME=tower", "TZ=Europe/London", "BB_NET_ADDRESS=192.168.1.20",
                          "BB_NET_MASK=24", "BB_NET_GATEWAY=192.168.1.1", "BB_NET_DNS=1.1.1.1"])

    def test_a_field_that_is_not_one_is_refused_with_why(self):
        for bad in ({"hostname": "a b"}, {"tz": "London; rm"}, {"address": "192.168.1.20"}, {"address": "x", "mask": "24", "gateway": "1.1.1.1"}):
            with self.assertRaises(ValueError, msg=bad):
                um.settings_lines(bad)


class Releases(unittest.TestCase):
    def test_the_published_ones_by_tag_a_dev_build_marked(self):
        rows = [{"tag_name": "v0.9.0-dev.4724", "prerelease": True}, {"tag_name": "v0.8.2", "prerelease": False},
                {"tag_name": "v0.9.0-dev.1", "draft": True}, {"tag_name": "nightly"}]

        class R:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps(rows).encode()
        with mock.patch("urllib.request.urlopen", return_value=R()):
            self.assertEqual(um.releases(), [("v0.9.0-dev.4724", True), ("v0.8.2", False)])


if __name__ == "__main__":
    unittest.main()
