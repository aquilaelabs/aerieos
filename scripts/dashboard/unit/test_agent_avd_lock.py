"""A phone's lock is in an account's home (R247 step 5): the room keeper's
walk opens it only as a regular file reached by no link, and never waits on
one, so a FIFO or a link left there does not hold the walk or reach a device."""
import fcntl
import os
import shutil
import tempfile
import threading
import unittest

import agentpkg

storage = agentpkg.load("avd_lock").module("storage")


class Lock(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)

    def ran(self, fn):
        out = []
        t = threading.Thread(target=lambda: out.append(fn()), daemon=True)
        t.start()
        t.join(5)
        self.assertFalse(t.is_alive(), "the lock's open waited")
        return out[0]

    def test_a_fifo_or_a_link_at_the_lock_reads_as_not_running_at_once(self):
        os.mkfifo(os.path.join(self.d, "multiinstance.lock"))
        self.assertFalse(self.ran(lambda: storage.avd_running(self.d)))
        os.remove(os.path.join(self.d, "multiinstance.lock"))
        os.symlink("/dev/zero", os.path.join(self.d, "multiinstance.lock"))
        self.assertFalse(self.ran(lambda: storage.avd_running(self.d)))

    def test_a_held_lock_is_running_and_a_free_one_is_not(self):
        lock = os.path.join(self.d, "multiinstance.lock")
        with open(lock, "w") as f:
            self.assertFalse(storage.avd_running(self.d))
            fcntl.flock(f, fcntl.LOCK_EX)
            self.assertTrue(self.ran(lambda: storage.avd_running(self.d)))

    def test_the_owner_of_a_home_is_read_off_the_folder_itself(self):
        # A link at the home names whoever left it, never what it leads to
        # (/ is root's): the work done as them reaches only what they could.
        os.symlink("/", os.path.join(self.d, "home"))
        mine = None if os.geteuid() == 0 else (os.getuid(), os.getgid())
        self.assertEqual(storage.home_owner(os.path.join(self.d, "home")), mine)
        self.assertEqual(storage.home_owner(self.d), mine)
        self.assertIsNone(storage.home_owner(os.path.join(self.d, "gone")))


if __name__ == "__main__":
    unittest.main()
