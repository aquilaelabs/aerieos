"""bb-session's apply: a step of the view that fails says which step it was.
A mount's own error names no path, so a node whose view could not be built
said "No such file or directory" and nothing of where."""
import errno
import importlib.machinery
import importlib.util
import os
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


session = load("bb_session_step", os.path.join(ROOT, "nodes", "bb-session"))


class Step(unittest.TestCase):
    def test_a_failed_mount_names_its_step(self):
        def no(*_a):
            raise OSError(errno.ENOENT, "mount: No such file or directory")
        with mock.patch.object(session, "_mount", no), self.assertRaises(session.Refused) as got:
            session.apply([("hide", "/somewhere/gone")], os.getuid(), os.getgid())
        said = str(got.exception)
        self.assertIn("hide /somewhere/gone", said)
        self.assertIn("No such file or directory", said)

    def test_the_steps_before_it_are_made(self):
        made = []

        def mount(src, target, *_a):
            if target == "/b":
                raise OSError(errno.EPERM, "mount: Operation not permitted")
            made.append(target)
        with mock.patch.object(session, "_mount", mount), self.assertRaises(session.Refused) as got:
            session.apply([("hide", "/a"), ("hide", "/b"), ("hide", "/c")], os.getuid(), os.getgid())
        self.assertEqual(made, ["/a"])
        self.assertIn("hide /b", str(got.exception))

    def test_a_mount_let_go_already_is_not_a_failure(self):
        def gone(*_a):
            raise OSError(errno.EINVAL, "umount2: Invalid argument")
        with mock.patch.object(session, "_call", gone):
            session.apply([("letgo", "/mnt/went")], os.getuid(), os.getgid())


if __name__ == "__main__":
    unittest.main()
