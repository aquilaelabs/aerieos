"""The provisioner run again on an enrolled node, and the agent's verbs it asks.

A second run fetches the controller's agent with the node's own token: it
does so under what the node holds its controller to, as its record says
it, so a node that moved to https under a key's pin is fetched for and its
token goes to nobody else. What the script writes into the record on such a
run (the session account, the tunnel) is written by the agent's own verb,
under its lock and in one step, and by the script the same way where the
agent is from before the verb. What the node trusts is asked of the agent,
the keys added at its console among it. The agent's check-update refuses on
a record it cannot read as one, and enroll refuses a pin beside plain http.
A Mac's enrollment keeps the token off curl's command line."""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import agentpkg  # noqa: E402

LINUX = os.path.join(ROOT, "nodes", "provision-linux.sh")
MAC = os.path.join(ROOT, "nodes", "provision-macos.sh")
ENTRY = os.path.join(ROOT, "scripts", "agent", "builderbot-agent.py")
KEY = "sha256//" + "A" * 43 + "="
RECORD = {"node_id": "n_1", "token": "bbn_the-nodes-own", "controller": "https://controller.example:7680", "stores": {}}


def text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def function(script, name):
    """A function of the provisioner's, as it defines it."""
    m = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", script, re.M | re.S)
    assert m, name
    return m.group(0)


class Bash(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.record = os.path.join(self.d, "node.json")
        self.src = text(LINUX)

    def write(self, state):
        with open(self.record, "w") as f:
            json.dump(state, f)
        os.chmod(self.record, 0o600)

    def read(self):
        with open(self.record) as f:
            return json.load(f)

    def bash(self, script, **env):
        r = subprocess.run(["bash", "-c", "set -euo pipefail\n" + script], capture_output=True, text=True, timeout=120, check=False,
                           env=dict(os.environ, **env), cwd=self.d)
        return r.returncode, r.stdout, r.stderr

    def an_agent(self):
        """This tree's agent as the file a node runs, on this test's record."""
        path = os.path.join(self.d, "aerieos-agent")
        with open(path, "w") as f:
            f.write(f'#!/bin/sh\nBUILDERBOT_NODE_JSON="{self.record}" exec "{sys.executable}" "{ENTRY}" "$@"\n')
        os.chmod(path, 0o755)
        return path


class TheFetch(Bash):
    def fetch(self, state):
        """The rerun's fetch as the script runs it, curl standing in: what curl was handed."""
        self.write(state)
        i = self.src.index('    ctl=""; tok=""; pin=""; held=""')
        j = self.src.index('        warn "/etc/aerieos/node.json carries no controller or token', i)
        piece = self.src[i:self.src.index("\n    fi\n", j) + len("\n    fi\n")]
        script = (f'NODE_RECORD="{self.record}"; AGENT="{self.d}/agent"\n'
                  'warn() { printf "!! %s\\n" "$*"; }\n'
                  'agent_sent() { :; }\nagent_swap() { echo swapped; }\n'
                  'curl() { printf "%s\\n" "$@" > "$OUT"; for a in "$@"; do case "$a" in @*) cat "${a#@}" >> "$OUT.header" ;; esac; done; }\n'
                  + piece)
        out = os.path.join(self.d, "curl-words")
        for f in (out, out + ".header"):
            if os.path.exists(f):
                os.unlink(f)
        rc, said, err = self.bash(script, OUT=out)
        self.assertEqual(rc, 0, said + err)
        words = text(out).splitlines() if os.path.exists(out) else None
        header = text(out + ".header") if os.path.exists(out + ".header") else ""
        return words, header, said

    def test_a_node_under_a_key_s_pin_is_fetched_for_under_it(self):
        words, header, said = self.fetch(dict(RECORD, pin=KEY))
        self.assertIn("swapped", said)
        at = words.index("--pinnedpubkey")
        self.assertEqual(words[at - 1:at + 2], ["-k", "--pinnedpubkey", KEY])
        self.assertIn("https://controller.example:7680/api/v1/agent/download", words)
        self.assertEqual(header, "Authorization: Bearer bbn_the-nodes-own\n")
        self.assertNotIn("bbn_the-nodes-own", " ".join(words), "the token is on a descriptor, never among curl's words")

    def test_a_public_hostname_and_plain_http_are_fetched_as_they_were(self):
        for state in (dict(RECORD, pin="ca"), dict(RECORD, controller="http://10.0.0.5:7680"), dict(RECORD, pin="")):
            words, _header, _said = self.fetch(state)
            self.assertNotIn("--pinnedpubkey", words, state)
            self.assertNotIn("-k", words, state)

    def test_a_pin_that_is_not_a_key_s_is_never_handed_to_curl(self):
        for pin in ("sha256//short=", "sha256//" + "A" * 43 + "=; id", "-o /etc/passwd"):
            words, _header, _said = self.fetch(dict(RECORD, pin=pin))
            self.assertNotIn(pin, words or [])
            self.assertNotIn("--pinnedpubkey", words or [])

    def test_a_node_that_pinned_a_certificate_sends_its_token_to_nobody(self):
        words, _header, said = self.fetch(dict(RECORD, pin="sha256:" + "ab" * 32))
        self.assertIsNone(words, "curl was not run")
        self.assertIn("holds its controller to a certificate", said)


class TheRecord(Bash):
    def set(self, agent, what, value):
        script = (f'NODE_RECORD="{self.record}"; AGENT="{agent}"\n' + function(self.src, "node_record_set")
                  + f'node_record_set {what} "{value}"\n')
        return self.bash(script)

    def test_the_agent_s_own_verb_writes_it_and_a_running_agent_keeps_it(self):
        self.write(RECORD)
        agent = self.an_agent()
        rc, said, err = self.set(agent, "session-user", "builder")
        self.assertEqual((rc, said.strip()), (0, "changed"), err)
        self.assertEqual(self.read(), dict(RECORD, session_user="builder"))
        self.assertEqual(stat.S_IMODE(os.stat(self.record).st_mode), 0o600)
        self.assertEqual(self.set(agent, "session-user", "builder")[1].strip(), "", "nothing changed, nothing said")
        rc, said, _ = self.set(agent, "tunnel", "10.44.0.7")
        self.assertEqual(self.read()["tunnel"], {"kind": "wireguard", "iface": "bb", "addr": "10.44.0.7"})
        # The running agent's own save, from the copy it read before the
        # provisioner wrote: the record's two keys are the file's.
        a = agentpkg.load("aerieos_agent_rerun")
        a.NODE_JSON = self.record
        a.module("stores").save_state(dict(RECORD, token="bbn_next", session_user="nobody-yet"))
        got = self.read()
        self.assertEqual((got["token"], got["session_user"], got["tunnel"]["addr"]), ("bbn_next", "builder", "10.44.0.7"))
        # No account any more: taken out.
        self.set(agent, "session-user", "")
        self.assertNotIn("session_user", self.read())

    def test_what_is_not_a_name_or_an_address_is_refused_by_the_verb(self):
        self.write(RECORD)
        agent = self.an_agent()
        for what, value in (("session-user", "a b"), ("session-user", "$(id)"), ("tunnel", "not-an-address"), ("token", "x")):
            r = subprocess.run([agent, "record", what, value], capture_output=True, text=True, timeout=60, check=False)
            self.assertNotEqual(r.returncode, 0, (what, value))
        self.assertEqual(self.read(), RECORD)

    def test_an_agent_from_before_the_verb_is_not_asked_and_the_script_writes_the_same_way(self):
        self.write(RECORD)
        old = os.path.join(self.d, "old-agent")
        with open(old, "w") as f:
            f.write('#!/bin/sh\necho "unknown command $1" >&2\nexit 64\n')
        os.chmod(old, 0o755)
        for agent in (old, os.path.join(self.d, "no-agent")):
            self.write(RECORD)
            rc, said, err = self.set(agent, "session-user", "builder")
            self.assertEqual((rc, said.strip()), (0, "changed"), err)
            self.assertEqual(self.read(), dict(RECORD, session_user="builder"))
            self.assertEqual(stat.S_IMODE(os.stat(self.record).st_mode), 0o600)
            self.assertEqual([n for n in os.listdir(self.d) if n.startswith(".node.json.") and n != ".node.json.lock"], [],
                             "written beside itself and renamed: nothing is left")
            self.assertEqual(self.set(agent, "session-user", "builder")[1].strip(), "")
        self.assertNotIn('json.dump(d, open(p, "w")', self.src, "the record is never truncated in place")


class WhatItTrusts(Bash):
    def pinned(self, agent):
        script = f'NODE_RECORD="{self.record}"; AGENT="{agent}"\n' + function(self.src, "agent_pinned") + "agent_pinned\n"
        rc, said, err = self.bash(script)
        self.assertEqual(rc, 0, err)
        return said.strip()

    def test_a_key_added_at_the_console_is_a_key_the_node_pinned(self):
        a, b, c = "a1" * 32, "b2" * 32, "c3" * 32
        for state, want in ((dict(RECORD, release_also=[c]), c),
                            (dict(RECORD, release_key=a, release_spare=b, release_also=[c]), f"{a},{b},{c}"),
                            (dict(RECORD, release_key=a), a),
                            (dict(RECORD), "none"),
                            (dict(RECORD, release_unpinned=True), "none")):
            self.write(state)
            # Asked of the agent, and read from the record where none is left.
            self.assertEqual(self.pinned(self.an_agent()), want, state)
            self.assertEqual(self.pinned(os.path.join(self.d, "no-agent")), want, state)

    def test_a_record_that_cannot_be_read_says_nothing_and_not_none(self):
        with open(self.record, "w") as f:
            f.write("not json")
        self.assertEqual(self.pinned(os.path.join(self.d, "no-agent")), "")


class TheAgent(unittest.TestCase):
    def test_a_pin_beside_plain_http_enrolls_nothing(self):
        a = agentpkg.load("aerieos_agent_rerun_enroll")
        cli = a.module("cli")
        sent = []

        class Ctl:
            CA = "ca"

            def __init__(self, url, token, pin=""):
                self.url, self.scheme, self.host = url, url.split(":", 1)[0], "h"

            def call(self, *args, **kw):
                sent.append(args)
                return 200, {}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(cli, "Controller", Ctl), \
                mock.patch.object(cli, "make_store", lambda p: {}), mock.patch.object(cli, "store_path_ok", lambda p, **kw: ""), \
                mock.patch.object(cli, "NODE_JSON", os.path.join(d, "node.json")):
            for pin in (KEY, "sha256:" + "ab" * 32):
                with self.assertRaises(SystemExit) as no:
                    cli.cmd_enroll(["--controller", "http://10.0.0.5:7680", "--token", "bbe_once", "--pin", pin])
                self.assertIn("--pin is what an https controller is held to", str(no.exception))
        self.assertEqual(sent, [], "the token went nowhere")


class TheWords(unittest.TestCase):
    def test_a_mac_s_token_is_not_among_curl_s_words(self):
        mac = text(MAC)
        self.assertNotIn('-H "Authorization: Bearer ${TOKEN}"', mac)
        self.assertIn("-H @<(printf 'Authorization: Bearer %s\\n' \"${TOKEN}\")", mac)
        self.assertNotIn('-H "Authorization: Bearer', text(LINUX))

    def test_the_header_says_how_the_script_reaches_a_machine(self):
        head = text(LINUX).split("set -euo pipefail", 1)[0]
        self.assertNotIn("raw.githubusercontent.com", head)
        self.assertNotIn("/main/", head)
        self.assertIn("Enroll node", head)

    def test_the_agent_says_what_its_capability_check_is(self):
        said = text(os.path.join(agentpkg.PKG, "__init__.py"))
        self.assertNotIn("refused HERE", said)
        self.assertIn("a field the controller writes", said)


if __name__ == "__main__":
    unittest.main()
