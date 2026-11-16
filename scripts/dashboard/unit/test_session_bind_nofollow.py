"""bb-session binds what it staged from a descriptor opened a part at a time
through no link (R247 step 5): the account owns much of a view's sources,
and a link it left along one (u/<account> pointed at another account's
folder) led the bind to that account's token and session."""
import importlib.machinery
import importlib.util
import os
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


session = load("bb_session_bind_nofollow", os.path.join(ROOT, "nodes", "bb-session"))


class SourceFd(unittest.TestCase):
    def setUp(self):
        self.d = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        os.makedirs(os.path.join(self.d, "cache", "u", "u_a", "project", "p"))
        os.makedirs(os.path.join(self.d, "base", "u", "u_b", "project", "p"))

    def test_a_path_of_real_folders_opens(self):
        fd = session._src_fd(os.path.join(self.d, "cache", "u", "u_a", "project", "p"))
        try:
            self.assertTrue(os.path.samestat(os.fstat(fd), os.stat(os.path.join(self.d, "cache", "u", "u_a", "project", "p"))))
        finally:
            os.close(fd)

    def test_a_link_anywhere_along_it_is_refused(self):
        shutil.rmtree(os.path.join(self.d, "cache", "u", "u_a"))
        os.symlink(os.path.join(self.d, "base", "u", "u_b"), os.path.join(self.d, "cache", "u", "u_a"))
        with self.assertRaises(OSError):
            session._src_fd(os.path.join(self.d, "cache", "u", "u_a", "project", "p"))
        os.symlink(os.path.join(self.d, "base"), os.path.join(self.d, "last"))
        with self.assertRaises(OSError):
            session._src_fd(os.path.join(self.d, "last"))

    def test_a_climb_is_refused(self):
        with self.assertRaises(OSError):
            session._src_fd(os.path.join(self.d, "cache", "..", "base"))


if __name__ == "__main__":
    unittest.main()
