"""tools/upgrade-image.sh: the built image started on each release snapshot
of /config through its own entrypoint (R242; the audit of 13 Nov: the
upgrade suite starts server.py alone with stand-ins, and nothing started the
image's own boot on an old volume). Its judgment, with stand-ins for docker
and curl that answer as the image would: what passes, and each thing that
fails it, said by name with the container's log."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TOOL = os.path.join(ROOT, "tools", "upgrade-image.sh")
SNAPS = os.path.join(ROOT, "scripts", "dashboard", "test", "upgrade")

DOCKER = r'''#!/bin/bash
echo "docker $*" >> "$FAKE_LOG"
case "$1" in
  run)
    case " $* " in
      *" stateversion.py policy "*|*"stateversion.py policy"*) echo "{\"current\": $FAKE_NOW, \"supported_from\": $FAKE_FROM}" ;;
      *" -d "*) [ "${FAKE_START:-ok}" = ok ] && echo c0ffee || exit 125 ;;
    esac ;;
  port) echo "127.0.0.1:45678" ;;
  inspect) echo "${FAKE_RUNNING:-true}" ;;
  exec)
    case "$*" in
      *state.json*) echo "${FAKE_STAMP:-$FAKE_NOW}" ;;
      *backups/before-*) [ "${FAKE_COPY:-yes}" = yes ] ;;
    esac ;;
  logs) echo "what the container said" ;;
esac
'''
CURL = r'''#!/bin/bash
echo "curl $*" >> "$FAKE_LOG"
case "$*" in
  *--data-urlencode*) printf 'HTTP/1.1 303 See Other\r\n'; [ "${FAKE_SIGNIN:-yes}" = yes ] && printf 'Set-Cookie: bb_session=abc; Path=/\r\n'; printf '\r\n' ;;
  *) printf '%s' "${FAKE_CODE:-200}" ;;
esac
'''


class Judgment(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        for name, text in (("docker", DOCKER), ("curl", CURL), ("sleep", "#!/bin/sh\n")):
            with open(os.path.join(self.d, name), "w") as f:
                f.write(text)
            os.chmod(os.path.join(self.d, name), 0o755)
        self.states = {}
        for name in sorted(os.listdir(SNAPS)):
            with open(os.path.join(SNAPS, name, "manifest.json")) as f:
                self.states[name] = json.load(f)["state"]
        self.now = max(self.states.values())

    def run_it(self, *snaps, **fake):
        env = {"PATH": self.d + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"), "TMPDIR": self.d,
               "FAKE_LOG": os.path.join(self.d, "calls.log"), "FAKE_NOW": str(self.now), "FAKE_FROM": str(min(self.states.values())),
               **{k: str(v) for k, v in fake.items()}}
        p = subprocess.run(["bash", TOOL, "the-image", *(os.path.join(SNAPS, s) for s in snaps)],
                           capture_output=True, text=True, check=False, env=env)
        with open(env["FAKE_LOG"]) as f:
            calls = f.read()
        os.unlink(env["FAKE_LOG"])
        return p.returncode, p.stdout + p.stderr, calls

    def test_every_snapshot_is_started_as_an_install_starts_the_image(self):
        rc, said, calls = self.run_it()
        self.assertEqual(rc, 0, said)
        for name, state in self.states.items():
            self.assertIn(f"PASS  {name} (state {state})", said)
        # Its own entrypoint on the snapshot's /config, never a command of this script's.
        started = [ln for ln in calls.splitlines() if ln.startswith("docker run -d")]
        self.assertEqual(len(started), len(self.states))
        for ln in started:
            self.assertRegex(ln, r"-v \S+/config:/config -v \S+/workspace:/workspace")
            self.assertTrue(ln.endswith(" the-image"), ln)
        # A copy is asked for only where the state had to move.
        moved = sum(1 for s in self.states.values() if s < self.now)
        self.assertEqual(calls.count("backups/before-"), moved)
        # ...and each container is taken away with what it wrote.
        self.assertEqual(calls.count("docker rm -f"), len(self.states))
        self.assertEqual([n for n in os.listdir(self.d) if n.startswith("tmp")], [])

    def test_each_thing_that_fails_it_is_said_with_the_containers_log(self):
        old = min(self.states, key=self.states.get)
        for fake, why in (({"FAKE_RUNNING": "false", "FAKE_CODE": "000"}, "the container stopped"),
                          ({"FAKE_CODE": "502"}, "did not answer in three minutes (last: 502)"),
                          ({"FAKE_STAMP": str(self.now - 1)}, f"/config's stamp is {self.now - 1}, not the image's {self.now}"),
                          ({"FAKE_COPY": "no"}, "no copy was taken first"),
                          ({"FAKE_SIGNIN": "no"}, "the owner did not sign in"),
                          ({"FAKE_START": "no"}, "the image did not start")):
            rc, said, calls = self.run_it(old, **fake)
            self.assertEqual(rc, 1, (fake, said))
            self.assertIn(f"FAIL  {old}", said)
            self.assertIn(why, said)
            if "FAKE_START" not in fake:
                self.assertIn("      what the container said", said)
                self.assertIn("docker rm -f", calls)

    def test_a_snapshot_older_than_the_image_migrates_from_is_not_started(self):
        old = min(self.states, key=self.states.get)
        rc, said, calls = self.run_it(old, FAKE_FROM=self.states[old] + 1)
        self.assertEqual(rc, 0, said)
        self.assertIn("is older than this image migrates from: not started", said)
        self.assertNotIn("docker run -d", calls)

    def test_it_asks_for_an_image(self):
        p = subprocess.run(["bash", TOOL], capture_output=True, text=True, check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("usage:", p.stderr)


if __name__ == "__main__":
    unittest.main()
