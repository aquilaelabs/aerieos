"""A terminal's open keeps the newest copy of an account's sealed sign-in
(B1043). Every open used to write the opened copy from the seal and put the
link in the home's file's place, so a refresh the pass had not sealed yet
(a plain file renamed over the link, or the opened copy written in place)
was thrown away for the seal's older copy; a refresh spends the token
before it, so the account was signed out at its next start.

Now, for each sign-in: a plain file in the home is newer than its seal and
is sealed, opened and linked by the one path the pass takes (left where it
is with no public key yet); a copy open already is never written from the
seal, only linked, and sealed again when it changed or when its seal is
still under the key from before a rotation; and the seal is opened only
where neither is there. The switch off puts back the newest too. The first
pass of a process does not wait for the controller where node.json already
says sign-ins are sealed.

The agent's own code runs here as an ordinary user: the folders are
temporary ones, the account's user is this process's (a chown to oneself
succeeds), root's ownership of a seal is recorded as asked, and the keys a
terminal brings are made by the controller's own tokenkeys from the
census the agent reports. Every sign-in here is made up."""
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import accountkeys  # noqa: E402
import agentpkg  # noqa: E402
import signing  # noqa: E402
import tokenkeys  # noqa: E402

AGENT_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "agent"))
agent = agentpkg.load("token_open")
tok = agent.module("tokens")
tok.log = lambda *a, **k: None
# The shipped agents' sign-ins alone: no pack's table is read off this machine.
tok.pack_signins = lambda *a, **k: {}

ME, MY_GROUP = os.getuid(), os.getgid()
NODE, ACCT = "n_1", "u_00000001"
INSTALL_KEY = b"an install key made up for this test, long enough"
REL = os.path.join(".claude", ".credentials.json")
FIRST = b'{"made up": "the first sign-in"}'
NEWER = b'{"made up": "the sign-in after a refresh, which spent the first"}'
NEWEST = b'{"made up": "the sign-in after a second refresh, longer than either before it"}'

# What the module wrote and for whom: a seal is asked for root, which an
# ordinary user cannot give a file to, so it is recorded and given to this
# process's user instead; everything else is written exactly as asked.
asked = []
_write = tok.write_atomic


def write_recorded(path, data, *, mode=None, uid=None, gid=None, **kw):
    asked.append((path, mode, uid, gid))
    _write(path, data, mode=mode, uid=ME if uid == 0 else uid, gid=MY_GROUP if gid == 0 else gid, **kw)


tok.write_atomic = write_recorded


class Node(tok.TokensMixin):
    """The agent's token half, with what needs root or a real machine stood
    in for: the tmpfs is a folder, accounts are ready, and whether the
    account has a session running is what the test says."""

    def __init__(self, pubs, seal=True):
        self.state = {"token_seal": seal, "token_pubs2": dict(pubs)}
        self.live = True
        self.said = []

    def account_users_ready(self):
        return True

    def session_account(self):
        return "sessions"

    def _open_mounted(self):
        os.makedirs(tok.OPEN_DIR, mode=0o711, exist_ok=True)
        return True

    def _live(self, acct):
        return self.live

    def hello_again(self, why):
        self.said.append(why)


def mode(path):
    return stat.S_IMODE(os.lstat(path).st_mode)


class Case(unittest.TestCase):
    def setUp(self):
        self.world()
        # The controller's half, as test_tokenkeys.py sets it up.
        ctl = os.path.join(self.d, "controller")
        os.makedirs(ctl)
        os.environ["BB_INSTALL_KEY_PREVIOUS_FILE"] = os.path.join(ctl, "previous")
        self.addCleanup(os.environ.pop, "BB_INSTALL_KEY_PREVIOUS_FILE", None)
        tokenkeys.configure(agent_dir=AGENT_DIR)
        tokenkeys._pub_cache.clear()
        self.addCleanup(setattr, signing, "MASTER", signing.MASTER)
        signing.MASTER = INSTALL_KEY
        accountkeys.configure(state=Path(ctl))
        self.ts = tokenkeys.ts()
        self.node = Node(self.pubs())

    def world(self):
        """A node's folders, empty: the seals, the tmpfs, and the session
        account's home with the account's own home in it."""
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        del asked[:]
        tok.SEAL_DIR, tok.OPEN_DIR = os.path.join(self.d, "seals"), os.path.join(self.d, "open")
        base = os.path.join(self.d, "home")
        self.home = os.path.join(base, "users", ACCT)
        os.makedirs(os.path.join(self.home, ".claude"))
        self.hf = os.path.join(self.home, REL)
        self.of = os.path.join(tok.OPEN_DIR, ACCT, "claude.json")
        self.seal = os.path.join(tok.SEAL_DIR, ACCT, "claude.seal")
        tok.pwd = SimpleNamespace(getpwnam=lambda name: SimpleNamespace(
            pw_uid=ME, pw_gid=MY_GROUP, pw_dir=base if name == "sessions" else self.home))

    def pubs(self):
        return tokenkeys.pubs(NODE, [ACCT])

    # ---- what the account's agent does in its home -------------------------

    def wrote_plain(self, data):
        """A login, or a refresh: a new file renamed over the name, which
        takes the place of whatever was there, the link included."""
        with open(self.hf + ".tmp", "wb") as f:
            f.write(data)
        os.chmod(self.hf + ".tmp", 0o600)
        os.replace(self.hf + ".tmp", self.hf)

    def wrote_through_the_link(self, data):
        with open(self.hf, "wb") as f:
            f.write(data)

    # ---- the agent's two ways in -------------------------------------------

    def passes(self, node=None):
        node = node or self.node
        node.tokens_at = 0.0
        with mock.patch.object(tok.os, "geteuid", return_value=0):
            node.token_pass()

    def tk(self, node=None):
        """What the controller puts in a terminal's signed open for this
        account, from the census this agent reports."""
        return tokenkeys.wrapped_for(NODE, ACCT, (node or self.node).token_census())

    def opens(self, node=None, tk=None):
        node = node or self.node
        tk = tk or self.tk(node)
        self.assertIsNotNone(tk, "the controller has keys to send")
        node.token_open(tk)

    def signed_in(self, data=FIRST, open_=True):
        """The account signed in and its sign-in sealed, with a copy open
        (a session running) or with none."""
        self.node.live = open_
        self.wrote_plain(data)
        self.passes()
        self.node.live = True
        self.assertEqual(self.sealed()[0], data)
        self.assertEqual(os.path.isfile(self.of), open_)

    # ---- what is where -----------------------------------------------------

    def sealed(self, node=None):
        """(what the seal on the disk holds, whether only the key from
        before opens it), opened the way a terminal's keys would."""
        node = node or self.node
        tk = self.tk(node)
        keys = self.ts.unwrap(node._tok_e, tk["C"], tok.base64.urlsafe_b64decode(tk["w"] + "=" * (-len(tk["w"]) % 4)))
        with open(self.seal, "rb") as f:
            blob = f.read()
        r = self.ts.rid(self.ts.header(blob)["R"])
        for name in (r, r + "|prev"):
            if name in keys:
                try:
                    return self.ts.open_with(keys[name], blob), name.endswith("|prev")
                except self.ts.Refused:
                    continue
        return None, None

    def opened(self):
        with open(self.of, "rb") as f:
            return f.read()

    def linked(self):
        return os.path.islink(self.hf) and os.readlink(self.hf) == self.of

    def picture(self):
        """Every file under the node's folders: what kind, its mode, where a
        link leads, and what was asked of the writes."""
        out = {}
        for top in (tok.SEAL_DIR, tok.OPEN_DIR, self.home):
            for folder, dirs, names in os.walk(top):
                for name in dirs + names:
                    p = os.path.join(folder, name)
                    rel = os.path.relpath(p, self.d)
                    out[rel] = ("link", os.path.relpath(os.readlink(p), self.d)) if os.path.islink(p) \
                        else ("folder" if os.path.isdir(p) else "file", oct(mode(p)))
        return out, sorted((os.path.relpath(p, self.d), m, u, g) for p, m, u, g in asked)


class NoLibrary(Case):
    """A node with no cryptography library seals nothing new: a sign-in
    stays the plain file it is, said once in the agent's log and on the
    node's row. A seal of the format before that it holds still opens in a
    terminal, its boot key the old group's."""

    def setUp(self):
        super().setUp()
        nts, base = agent.module("tokenseal"), agent.module("base")
        for p in (mock.patch.object(nts, "HAVE", False), mock.patch.dict(base._said, {}, clear=True)):
            p.start()
            self.addCleanup(p.stop)
        self.logged = []
        p = mock.patch.object(base, "log", self.logged.append)
        p.start()
        self.addCleanup(p.stop)
        self.node = Node(self.pubs())

    def test_a_plain_sign_in_stays_as_it_is_and_it_says_so_once(self):
        self.wrote_plain(FIRST)
        ino = os.lstat(self.hf).st_ino
        for _ in range(3):
            self.passes()
        self.assertFalse(os.path.lexists(self.seal), "no seal made")
        self.assertFalse(os.path.islink(self.hf))
        self.assertEqual(os.lstat(self.hf).st_ino, ino, "the very file, untouched")
        self.assertEqual(self.logged, ["tokens: this node has no cryptography library, so no sign-in is sealed here"])
        census = self.node.token_census()
        self.assertIs(census.get("nolib"), True)
        self.assertGreater(len(census["E"]), 64, "its boot key is the old group's")

    def test_a_seal_from_before_it_holds_still_opens(self):
        pub1 = self.ts.public(self.ts.secret1(INSTALL_KEY, NODE, ACCT))
        about = {"agent": "claude", "K": self.ts.rid(pub1)}
        os.makedirs(os.path.dirname(self.seal))
        with open(self.seal, "wb") as f:
            f.write(agentpkg.seal_the_way_before(self.ts, pub1, FIRST, about))
        self.opens()
        self.assertEqual((self.linked(), self.opened()), (True, FIRST))


class PlainFile(Case):
    def test_a_plain_file_newer_than_the_seal_survives_a_terminal_open(self):
        self.signed_in()
        tk = self.tk()                          # made before the refresh, as a page reconnecting holds it
        self.wrote_plain(NEWER)                 # the running session's refresh, not yet sealed
        self.opens(tk=tk)
        self.assertTrue(self.linked(), "the plain file gave way to the link")
        self.assertEqual(self.opened(), NEWER, "the opened copy holds the refresh")
        self.assertEqual(self.sealed(), (NEWER, False), "and so does the seal")
        left = [p for p, _ in self.picture()[0].items() if p.endswith((".new", ".tmp"))]
        self.assertEqual(left, [], "nothing in the clear is left beside them")

    def test_with_no_copy_open_it_is_opened_for_the_terminal_about_to_start(self):
        self.signed_in(open_=False)
        self.wrote_plain(NEWER)
        self.node.live = False                  # the terminal's program has not started yet
        self.opens()
        self.assertEqual((self.linked(), self.opened(), self.sealed()), (True, NEWER, (NEWER, False)))
        self.assertIn(ACCT, self.node._tok_state()[1], "the account counts as working here from now")

    def test_an_account_with_no_public_key_yet_keeps_its_plain_file(self):
        self.signed_in(open_=False)
        with open(self.seal, "rb") as f:
            was = f.read()
        self.wrote_plain(NEWER)
        ino = os.lstat(self.hf).st_ino
        self.node.state["token_pubs2"] = {}
        self.opens()
        self.passes()
        self.assertFalse(os.path.islink(self.hf))
        self.assertEqual((os.lstat(self.hf).st_ino, mode(self.hf)), (ino, 0o600), "the very file, untouched")
        with open(self.hf, "rb") as f:
            self.assertEqual(f.read(), NEWER)
        with open(self.seal, "rb") as f:
            self.assertEqual(f.read(), was, "the seal is as it was")
        self.assertFalse(os.path.lexists(self.of), "and the older sign-in in it is opened nowhere")
        # The key arrives with a later hello: the next look seals it.
        self.node.state["token_pubs2"] = self.pubs()
        self.opens()
        self.assertEqual((self.linked(), self.opened(), self.sealed()), (True, NEWER, (NEWER, False)))

    def test_one_written_again_while_it_is_sealed_is_left_for_the_next_look(self):
        self.signed_in()
        self.wrote_plain(NEWER)
        seal = self.node._seal

        def seal_then_refresh(*a):
            done = seal(*a)
            self.wrote_plain(NEWEST)            # a second refresh lands while the first is being sealed
            return done
        with mock.patch.object(self.node, "_seal", seal_then_refresh):
            self.opens()
        self.assertFalse(os.path.islink(self.hf))
        with open(self.hf, "rb") as f:
            self.assertEqual(f.read(), NEWEST, "not shredded, not linked over")
        self.passes()
        self.assertEqual((self.linked(), self.opened(), self.sealed()), (True, NEWEST, (NEWEST, False)))

    def test_the_link_never_takes_a_plain_files_place(self):
        self.signed_in()
        self.wrote_plain(NEWER)
        self.node._link(self.home, REL, self.of, tok.pwd.getpwnam("x"))
        self.assertFalse(os.path.islink(self.hf))
        with open(self.hf, "rb") as f:
            self.assertEqual(f.read(), NEWER)


class OpenCopy(Case):
    def test_a_copy_changed_in_place_survives_a_terminal_open_and_is_sealed_again(self):
        self.signed_in()
        self.wrote_through_the_link(NEWER)      # a refresh written into the opened copy
        ino = os.stat(self.of).st_ino
        self.opens()
        self.assertEqual((self.linked(), self.opened()), (True, NEWER))
        self.assertEqual(os.stat(self.of).st_ino, ino, "the copy itself, not one written again")
        self.assertEqual(self.sealed(), (NEWER, False))

    def test_it_survives_the_first_open_after_the_agent_started_again(self):
        # What was seen: the agent re-executed for its update, the session's
        # refresh had not been sealed, and the page reconnected its terminal.
        self.signed_in()
        self.wrote_through_the_link(NEWER)
        again = Node(self.pubs())
        self.opens(again)
        self.assertEqual((self.linked(), self.opened(), self.sealed(again)), (True, NEWER, (NEWER, False)))

    def test_an_unchanged_copy_is_not_written_again_and_the_link_is_right(self):
        self.signed_in()
        with open(self.seal, "rb") as f:
            seal = f.read()
        was = os.stat(self.of)
        del asked[:]
        self.opens()
        now = os.stat(self.of)
        self.assertEqual((now.st_ino, now.st_mtime_ns), (was.st_ino, was.st_mtime_ns))
        self.assertEqual(asked, [], "neither the copy nor the seal was written")
        with open(self.seal, "rb") as f:
            self.assertEqual(f.read(), seal)
        self.assertTrue(self.linked())
        # A link that went (the agent's own sign-out removes its file) or
        # leads elsewhere is put right, the copy still not written.
        for put in (lambda: os.unlink(self.hf), lambda: (os.unlink(self.hf), os.symlink(self.of + ".other", self.hf))):
            put()
            self.opens()
            self.assertTrue(self.linked())
            self.assertEqual(os.stat(self.of).st_ino, was.st_ino)
        self.assertEqual(self.opened(), FIRST)


class Sealed(Case):
    def test_with_nothing_open_the_seal_is_opened_as_before(self):
        self.signed_in(open_=False)
        self.assertTrue(self.linked(), "sealed and not open: the link leads to nothing yet")
        self.opens()
        self.assertEqual((self.linked(), self.opened()), (True, FIRST))
        self.assertEqual(self.sealed(), (FIRST, False))
        self.assertIn(ACCT, self.node._tok_state()[1])
        # ...and the pass that follows finds nothing to seal again.
        del asked[:]
        self.passes()
        self.assertEqual(asked, [])

    def rotate(self):
        """The account's key changed on the controller, the one before kept
        while this node's seal is still under it; the node hears the new
        public key with its next hello."""
        accountkeys.configure(state=accountkeys.STATE, nodes_under=lambda uid, k: 1)
        self.assertEqual(accountkeys.change(ACCT)[1], 200)
        self.node.state["token_pubs2"] = self.pubs()
        self.assertEqual(self.sealed()[1], True, "only the key from before opens the seal now")
        self.assertEqual(tokenkeys.under_previous(NODE, self.node.token_census()), 1)

    def test_a_seal_under_the_key_before_is_opened_and_sealed_again(self):
        self.signed_in(open_=False)
        self.rotate()
        self.opens()
        self.assertEqual((self.linked(), self.opened()), (True, FIRST))
        self.assertEqual(self.sealed(), (FIRST, False), "under the account's key of today")
        self.assertEqual(tokenkeys.under_previous(NODE, self.node.token_census()), 0)

    def test_with_a_copy_open_it_is_sealed_again_from_the_copy(self):
        self.signed_in()
        self.rotate()
        ino = os.stat(self.of).st_ino
        self.opens()
        self.assertEqual(os.stat(self.of).st_ino, ino, "the copy is not written from the seal")
        self.assertEqual(self.sealed(), (FIRST, False))
        self.assertEqual(tokenkeys.under_previous(NODE, self.node.token_census()), 0)

    def test_with_a_refreshed_copy_open_the_refresh_is_what_moves_to_the_new_key(self):
        self.signed_in()
        self.rotate()
        self.wrote_through_the_link(NEWER)
        self.opens()
        self.assertEqual((self.opened(), self.sealed()), (NEWER, (NEWER, False)))


class Kept(Case):
    def test_the_keys_are_wiped_and_nothing_is_left_readable_by_others(self):
        self.signed_in(open_=False)
        got = []
        unwrap = tok.tokenseal.unwrap

        def unwrapped(*a):
            got.append(unwrap(*a))
            return got[-1]
        with mock.patch.object(tok.tokenseal, "unwrap", unwrapped):
            self.opens()
        self.assertTrue(got[0], "the terminal brought keys")
        for k in got[0].values():
            self.assertEqual(bytes(k), bytes(len(k)), "each key zeroed as the open returns")
        self.assertEqual(self.opened(), FIRST)
        self.assertEqual({p: mode(p) for p in (tok.SEAL_DIR, os.path.dirname(self.seal), self.seal,
                                               os.path.dirname(self.of), self.of)},
                         {tok.SEAL_DIR: 0o700, os.path.dirname(self.seal): 0o700, self.seal: 0o600,
                          os.path.dirname(self.of): 0o700, self.of: 0o600})
        self.assertEqual({(m, u, g) for p, m, u, g in asked if p == self.seal}, {(0o600, 0, 0)}, "a seal is root's alone")
        self.assertEqual({(m, u, g) for p, m, u, g in asked if p == self.of}, {(0o600, ME, MY_GROUP)},
                         "an opened copy is the account's user's alone")
        files, _ = self.picture()
        self.assertEqual(sorted(p for p, (kind, _) in files.items() if kind == "file"),
                         sorted(os.path.relpath(p, self.d) for p in (self.seal, self.of)),
                         "the seal and the opened copy, and no other file")

    def test_the_keys_are_wiped_when_the_open_fails(self):
        self.signed_in(open_=False)
        got = []
        unwrap = tok.tokenseal.unwrap

        def unwrapped(*a):
            got.append(unwrap(*a))
            return got[-1]

        def nobody(name):
            raise KeyError(name)
        tk = self.tk()
        with mock.patch.object(tok.tokenseal, "unwrap", unwrapped), mock.patch.object(tok.pwd, "getpwnam", nobody):
            with self.assertRaises(KeyError):
                self.node.token_open(tk)
        for k in got[0].values():
            self.assertEqual(bytes(k), bytes(len(k)))


class OnePath(Case):
    def after(self, how):
        """A plain file newer than an open copy, taken by `how`, as a picture."""
        self.world()
        self.node = Node(self.pubs())
        self.signed_in()
        self.wrote_plain(NEWER)
        del asked[:]
        how()
        self.assertEqual((self.linked(), self.opened(), self.sealed()), (True, NEWER, (NEWER, False)))
        return self.picture()

    def test_the_pass_and_a_terminal_open_leave_a_plain_file_the_same(self):
        by_pass, by_open = self.after(self.passes), self.after(self.opens)
        self.assertEqual(by_pass, by_open, "the same files, modes, links and owners asked")
        self.assertTrue(by_pass[1], "both wrote a seal and a copy")

    def test_both_go_through_the_one_method(self):
        for how in (self.passes, self.opens):
            self.world()
            self.node = Node(self.pubs())
            self.signed_in()
            self.wrote_plain(NEWER)
            with mock.patch.object(self.node, "_seal_plain", wraps=self.node._seal_plain) as taken, \
                    mock.patch.object(self.node, "_seal", wraps=self.node._seal) as sealed:
                how()
            self.assertEqual(taken.call_count, 1, how.__name__)
            self.assertEqual(sealed.call_count, 1, "sealed once, by it")


class SwitchOff(Case):
    def off(self):
        self.node.state.update(token_seal=False, token_pubs2={})

    def test_an_opened_copy_comes_back_as_the_plain_file(self):
        self.signed_in()
        self.wrote_through_the_link(NEWER)
        self.off()
        self.passes()
        self.assertFalse(os.path.islink(self.hf))
        with open(self.hf, "rb") as f:
            self.assertEqual(f.read(), NEWER)
        self.assertEqual(mode(self.hf), 0o600)
        self.assertFalse(os.path.exists(self.seal) or os.path.exists(self.of))

    def test_a_plain_file_newer_than_the_opened_copy_is_what_stays(self):
        self.signed_in()
        self.wrote_plain(NEWER)                 # renamed over the link, not yet sealed
        ino = os.lstat(self.hf).st_ino
        self.off()
        self.passes()
        self.assertEqual(os.lstat(self.hf).st_ino, ino, "not written over from the older copy")
        with open(self.hf, "rb") as f:
            self.assertEqual(f.read(), NEWER)
        self.assertFalse(os.path.exists(self.seal) or os.path.exists(self.of))

    def test_a_terminal_open_brings_a_seal_back_and_never_over_a_plain_file(self):
        self.signed_in(open_=False)
        tk = self.tk()
        self.off()
        self.opens(tk=tk)
        self.assertEqual(self.opened(), FIRST, "opened, for the pass to put back")
        self.passes()
        with open(self.hf, "rb") as f:
            self.assertEqual(f.read(), FIRST)
        self.assertFalse(os.path.islink(self.hf) or os.path.exists(self.seal))
        # A seal left behind a sign-in made since the switch went off: the
        # plain file is the sign-in, and the seal goes without being opened.
        self.node.state.update(token_seal=True, token_pubs2=self.pubs())
        self.passes()
        self.node._tok_state()[1].clear()
        tk = self.tk()
        self.off()
        os.unlink(self.hf)
        shutil.rmtree(os.path.dirname(self.of))
        self.wrote_plain(NEWER)
        self.opens(tk=tk)
        with open(self.hf, "rb") as f:
            self.assertEqual(f.read(), NEWER)
        self.assertFalse(os.path.islink(self.hf) or os.path.exists(self.seal) or os.path.lexists(self.of))


class ThroughNoLink(Case):
    """The pass and a terminal's open are root's, and the account may point
    any folder of its home, or the opened copy's name in its own folder of
    the tmpfs, anywhere: at another account's home among them. Neither
    follows one: the other account's sign-in is never read, sealed, opened,
    shredded or linked over, and the watch neither holds nor marks it."""
    OTHER = b'{"made up": "another account\'s sign-in"}'

    def others(self):
        """Another account's .claude, beside this one's home."""
        b = os.path.join(os.path.dirname(self.home), "u_00000002", ".claude")
        os.makedirs(b)
        bf = os.path.join(b, ".credentials.json")
        with open(bf, "wb") as f:
            f.write(self.OTHER)
        os.chmod(bf, 0o600)
        return b, bf

    def untouched(self, bf):
        self.assertFalse(os.path.islink(bf), "nothing linked in its place")
        with open(bf, "rb") as f:
            self.assertEqual(f.read(), self.OTHER, "neither shredded nor written")

    def test_a_folder_of_the_home_linked_to_another_home(self):
        self.signed_in()
        b, bf = self.others()
        shutil.rmtree(os.path.join(self.home, ".claude"))
        os.symlink(b, os.path.join(self.home, ".claude"))
        self.passes()
        self.opens()
        self.untouched(bf)
        self.assertEqual(self.sealed(), (FIRST, False), "the account's own seal is as it was")
        self.assertEqual(self.opened(), FIRST, "and so is its opened copy")
        self.node.state.update(token_seal=False, token_pubs2={})
        self.passes()
        self.untouched(bf)

    def test_a_link_where_the_opened_copy_was(self):
        self.signed_in()
        _, bf = self.others()
        os.unlink(self.of)
        os.symlink(bf, self.of)
        self.passes()
        self.opens()
        self.untouched(bf)
        self.assertEqual(self.sealed(), (FIRST, False), "the link's file is not sealed as this account's")
        self.node.state.update(token_seal=False, token_pubs2={})
        self.passes()
        self.untouched(bf)
        with open(self.hf, "rb") as f:
            self.assertEqual(f.read(), FIRST, "the account's own sign-in is what comes back, never the link's file")

    def test_the_watch_holds_only_what_it_reaches_through_no_link(self):
        tw = agent.module("tokenwatch")
        b, bf = self.others()
        os.rmdir(os.path.join(self.home, ".claude"))
        os.symlink(b, os.path.join(self.home, ".claude"))
        changed = []
        record = lambda *a, **k: changed.append(a)  # noqa: E731
        someone = SimpleNamespace(pw_uid=ME + 1, pw_gid=MY_GROUP)
        with mock.patch.multiple(tw.os, chown=record, fchown=record, chmod=record, fchmod=record), \
                mock.patch.object(tw, "pack_signins", lambda: {}):
            tw.TokenWatch().watch(self.home, someone)
        self.assertEqual(changed, [], "another account's file is given to nobody")
        # The account's own, through no link, still is.
        os.unlink(os.path.join(self.home, ".claude"))
        os.makedirs(os.path.join(self.home, ".claude"))
        self.wrote_plain(FIRST)
        os.chmod(self.hf, 0o644)
        with mock.patch.multiple(tw.os, fchown=record, fchmod=record), mock.patch.object(tw, "pack_signins", lambda: {}):
            tw.TokenWatch().watch(self.home, someone)
        self.assertEqual(len(changed), 2, "held at 600 and the account's")


class FirstPass(Case):
    def test_it_runs_at_once_where_the_kept_state_says_sealed(self):
        self.signed_in()
        self.wrote_plain(NEWER)
        again = Node(self.pubs())               # a process just started: node.json's word, no hello yet
        with mock.patch.object(tok.os, "geteuid", return_value=0):
            again.token_pass_early()
        self.assertEqual((self.linked(), self.opened()), (True, NEWER))

    def test_with_the_switch_off_in_what_was_kept_it_waits_for_the_controller(self):
        self.signed_in()
        off = Node({}, seal=False)
        with mock.patch.object(tok.os, "geteuid", return_value=0):
            off.token_pass_early()
        self.assertTrue(self.linked() and os.path.exists(self.seal), "nothing put back on a word that may be old")

    def test_a_turn_takes_it_before_its_hello(self):
        class Said(BaseException):
            pass
        order = []
        a = agent.Agent.__new__(agent.Agent)
        a.hello_at = 0
        a.token_pass_early = lambda: order.append("tokens")
        a.console_moved = lambda: False
        a.refresh_session_tool = a.quiet_distro_ttyd = lambda: None

        def hello():
            order.append("hello")
            raise Said
        a.hello_step = hello
        with self.assertRaises(Said):
            a.turns()
        self.assertEqual(order, ["tokens", "hello"])


if __name__ == "__main__":
    unittest.main()
