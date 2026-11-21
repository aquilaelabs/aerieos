"""One pack cannot steer another toolchain's install or its check (the
final audit's 3).

A pack's layout may set variables for every job, and an installer reads
some of them at its start: rustup a download server, Playwright a download
host, npm a registry, git and node whether a certificate is checked. So a
row's installer, its steps, its warm-up and its verify start with none of
the caller's environment but what a check keeps (the home, the temporary
folder, the language, the proxy), the PATH they are handed and BB_LIB,
and then that row's own variables: its layout's and its own env, which win
where both name one. A layout's `=VALUE` reaches a job, and a shell, only
where its row is installed. Git, the whole of a pinned commit's check,
reads no configuration but the repository's own: an earlier step may write
the account's ~/.gitconfig, and a hooks folder named there rewrote what a
checkout left while its commit still matched."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
LIB = os.path.join(REPO, "scripts", "lib")
sys.path.insert(0, HERE)
import agentpkg  # noqa: E402

STEERS = {"RUSTUP_DIST_SERVER": "https://evil.example", "PLAYWRIGHT_DOWNLOAD_HOST": "https://evil.example",
          "NPM_CONFIG_REGISTRY": "https://evil.example", "GIT_SSL_NO_VERIFY": "1", "NODE_TLS_REJECT_UNAUTHORIZED": "0",
          "GOPROXY": "https://evil.example", "PIP_INDEX_URL": "https://evil.example", "UV_INDEX_URL": "https://evil.example"}


class Case(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.store = os.path.join(self.d, "store")
        os.makedirs(self.store)
        self.catalog = os.path.join(self.d, "toolchains.json")
        with open(self.catalog, "w") as f:
            json.dump({"toolchains": [
                {"name": "steer", "layout": {"env": {k: "=" + v for k, v in STEERS.items()}}},
                {"name": "rusty", "source": {"kind": "script", "env": {"RUSTUP_HOME": "{dir}/own", "MINE": "x"}},
                 "layout": {"env": {"RUSTUP_HOME": "rustup", "CARGO_HOME": "cargo", "QUIET": "=1", "WIDE": "root:shared",
                                    "bad name": "=1"}}},
            ]}, f)

    def sh(self, script, extra=None):
        env = {"PATH": "/usr/bin:/bin", "HOME": self.d, "TMPDIR": self.d, "LANG": "C.UTF-8", "BB_LIB": LIB,
               "BB_SCRIPTS": os.path.join(REPO, "scripts"),
               "https_proxy": "http://proxy.lan:3128", **STEERS, **(extra or {})}
        p = subprocess.run(["bash", "-c", f'set -euo pipefail\n. "{LIB}/common.sh"\n. "{LIB}/sdk.sh"\n'
                            f'SDK_CATALOG="{self.catalog}"\nsdk_root() {{ printf %s "{self.store}"; }}\n' + script],
                           capture_output=True, text=True, check=False, timeout=60, env=env)
        return p.returncode, p.stdout, p.stderr


class AStep(Case):
    def test_a_step_starts_with_none_of_what_another_pack_set(self):
        rc, out, err = self.sh('sdk_step OWN=mine env')
        self.assertEqual(rc, 0, err)
        got = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
        for k in STEERS:
            self.assertNotIn(k, got)
        self.assertEqual((got["OWN"], got["HOME"], got["TMPDIR"], got["LANG"], got["BB_LIB"], got["https_proxy"]),
                         ("mine", self.d, self.d, "C.UTF-8", LIB, "http://proxy.lan:3128"))
        self.assertEqual(got["PATH"], "/usr/bin:/bin", "the PATH it is handed, the store's toolchains on it")
        # ...and a warm-up, started under a clock of its own, the same.
        rc, out, err = self.sh('sdk_step_env; sdk_bounded 30 "${STEP_ENV[@]}" CI=true env')
        self.assertEqual(rc, 0, err)
        self.assertNotIn("RUSTUP_DIST_SERVER", out)
        self.assertIn("CI=true", out)

    def test_a_row_starts_with_its_own_layout_and_env(self):
        d = os.path.join(self.store, "rusty")
        rc, out, err = self.sh(f'sdk_row_env rusty "{d}" source.env; printf "%s\\n" "${{ROW_ENV[@]}}"')
        self.assertEqual(rc, 0, err)
        rows = out.splitlines()
        self.assertEqual(rows, [f"RUSTUP_HOME={d}/rustup", f"CARGO_HOME={d}/cargo", "QUIET=1", f"WIDE={self.store}/shared",
                                f"RUSTUP_HOME={d}/own", "MINE=x"], "a name no shell takes is left out; its own env comes last")
        rc, out, err = self.sh(f'sdk_row_env rusty "{d}" source.env; sdk_step "${{ROW_ENV[@]}}" env')
        got = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
        self.assertEqual((got["RUSTUP_HOME"], got["CARGO_HOME"], got["QUIET"]), (f"{d}/own", f"{d}/cargo", "1"))
        self.assertNotIn("RUSTUP_DIST_SERVER", got)


class TheEnvFile(Case):
    def snippet(self):
        rc, out, err = self.sh(f'sdk_meta_file() {{ printf %s "{self.catalog}"; }}\nsdk_env_snippet')
        self.assertEqual(rc, 0, err)
        return out

    def test_a_layouts_value_reaches_a_shell_only_where_its_row_is_installed(self):
        out = self.snippet()
        for k in STEERS:
            self.assertNotIn(k, out)
        self.assertNotIn("QUIET", out)
        os.makedirs(os.path.join(self.store, "steer"))
        os.makedirs(os.path.join(self.store, "rusty", "cargo"))
        out = self.snippet()
        self.assertIn("export RUSTUP_DIST_SERVER=https://evil.example", out, "installed: its own, as before")
        self.assertIn("export QUIET=1", out)
        self.assertIn(f"export CARGO_HOME={self.store}/rusty/cargo", out)
        self.assertNotIn("RUSTUP_HOME", out, "a path that is not there is not said")

    def test_a_value_is_quoted_for_the_shell_that_reads_it(self):
        with open(self.catalog, "w") as f:
            json.dump({"toolchains": [{"name": "odd", "layout": {"env": {"ODD": '=a"; touch pwned; "'}}}]}, f)
        os.makedirs(os.path.join(self.store, "odd"))
        out = self.snippet()
        p = subprocess.run(["bash", "-c", out + '\nprintf %s "$ODD"'], capture_output=True, text=True, cwd=self.d, timeout=30, check=False)
        self.assertEqual(p.stdout, 'a"; touch pwned; "')
        self.assertFalse(os.path.exists(os.path.join(self.d, "pwned")))


class OnANode(unittest.TestCase):
    def test_a_layouts_value_is_set_on_a_job_only_where_its_row_is_installed(self):
        agent = agentpkg.load("aerieos_agent_step_env")
        tc = agent.module("toolchains")
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        layout = [{"name": "steer", "dir": "steer", "bin": [], "env": {"RUSTUP_DIST_SERVER": "=https://evil.example"}},
                  {"name": "jdk", "dir": "jdk", "bin": ["bin"], "env": {"JAVA_HOME": ""}}]
        state = {"stores": {"toolchains": d, "data": d}, "layout": layout}
        orig = tc.tc_root
        tc.tc_root = lambda state: d
        self.addCleanup(setattr, tc, "tc_root", orig)
        self.assertNotIn("RUSTUP_DIST_SERVER", tc.sdk_env(state))
        os.makedirs(os.path.join(d, "steer"))
        os.makedirs(os.path.join(d, "jdk", "bin"))
        env = tc.sdk_env(state)
        self.assertEqual((env["RUSTUP_DIST_SERVER"], env["JAVA_HOME"]), ("https://evil.example", os.path.join(d, "jdk")))
        # An installer's environment has the store's toolchains and none of
        # the layouts' variables (a coding agent's install).
        bare = tc.sdk_env(state, layout_env=False)
        self.assertNotIn("RUSTUP_DIST_SERVER", bare)
        self.assertNotIn("JAVA_HOME", bare)
        self.assertTrue(bare["PATH"].startswith(os.path.join(d, "jdk", "bin")))


@unittest.skipUnless(shutil.which("git"), "no git here")
class Git(Case):
    def test_a_checkout_runs_no_hook_the_accounts_gitconfig_names(self):
        # The audit's (c): an earlier step wrote ~/.gitconfig with a hooks
        # folder; a post-checkout hook there rewrote the checked-out files
        # while rev-parse HEAD still matched.
        src, hooks = os.path.join(self.d, "src"), os.path.join(self.d, "hooks")
        os.makedirs(hooks)
        with open(os.path.join(hooks, "post-checkout"), "w") as f:
            f.write("#!/bin/sh\necho rewritten > tool.sh\n")
        os.chmod(os.path.join(hooks, "post-checkout"), 0o755)
        g = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", src]
        subprocess.run(["git", "init", "-q", src], check=True)
        with open(os.path.join(src, "tool.sh"), "w") as f:
            f.write("the approved file\n")
        subprocess.run(g + ["add", "."], check=True)
        subprocess.run(g + ["commit", "-qm", "x"], check=True)
        with open(os.path.join(self.d, ".gitconfig"), "w") as f:
            f.write(f"[core]\n\thooksPath = {hooks}\n")
        for how, want in (("git", "rewritten\n"), ("sdk_sys git", "the approved file\n")):
            dst = os.path.join(self.d, "dst-" + how.split()[0])
            rc, out, err = self.sh(f'{how} init -q "{dst}"\n{how} -C "{dst}" fetch -q "{src}" HEAD\n'
                                   f'{how} -C "{dst}" checkout -q --detach FETCH_HEAD')
            self.assertEqual(rc, 0, err)
            with open(os.path.join(dst, "tool.sh")) as f:
                self.assertEqual(f.read(), want, how)


if __name__ == "__main__":
    unittest.main()
