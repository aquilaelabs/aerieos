"""A node's system-packages job on the Installed page: whether it worked is
what the census still finds unmet, not whether the recipe is in the store
(it is, before and after), and the reason on the row is the package
manager's, read from the agent's own section of the log."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import toolchains  # noqa: E402

HERE = {"playwright", "node"}


class Finished(unittest.TestCase):
    def test_a_job_that_worked_is_done(self):
        rep = {"sysdeps": {"family": "dnf", "unmet": {}}}
        self.assertEqual(toolchains.finished("sysdeps", ["playwright"], HERE, rep, "succeeded"),
                         (["playwright"], []))

    def test_what_is_still_unmet_failed(self):
        rep = {"sysdeps": {"family": "dnf", "unmet": {"playwright": ["libXtst"]}}}
        self.assertEqual(toolchains.finished("sysdeps", ["playwright"], HERE, rep, "failed"),
                         ([], ["playwright"]))

    def test_no_names_is_every_held_recipe(self):
        rep = {"sysdeps": {"unmet": {"dotnet": ["libicu"]}}}
        self.assertEqual(toolchains.finished("sysdeps", [], HERE, rep, "failed"), ([], ["dotnet"]))

    def test_a_failed_job_with_nothing_unmet_still_says_so(self):
        self.assertEqual(toolchains.finished("sysdeps", ["playwright"], HERE, {}, "failed"),
                         ([], ["playwright"]))

    def test_install_and_remove_are_read_from_the_store(self):
        self.assertEqual(toolchains.finished("install", ["node", "go"], HERE, {}, "failed"), (["node"], ["go"]))
        self.assertEqual(toolchains.finished("remove", ["node", "go"], HERE, {}, "failed"), (["go"], ["node"]))


class Reason(unittest.TestCase):
    def why(self, log, name="playwright"):
        class Nodes:
            @staticmethod
            def job_tail(job_id, n=0):
                return log
        was, toolchains.nodes = toolchains.nodes, Nodes
        toolchains._node_errors_seen.clear()
        try:
            return toolchains._node_errors("j_1", [name], "sysdeps")[name]
        finally:
            toolchains.nodes = was

    def test_the_package_managers_own_words(self):
        got = self.why("== system packages for playwright: libXtst google-noto-color-emoji-fonts\n"
                       "Error: Unable to find a match: google-noto-color-emoji-fonts\n"
                       "playwright: its system packages did not install (exit 1)\n1 of 1 did not install\n")
        self.assertIn("Unable to find a match: google-noto-color-emoji-fonts", got)
        self.assertTrue(got.endswith("sysdeps failed on the node"))

    def test_a_refusal_is_the_reason(self):
        got = self.why("refused: this agent does not administer the machine, so its owner installs these: playwright: libXtst\n")
        self.assertIn("does not administer the machine", got)

    def test_a_signature_refusal_is_its_error_alone(self):
        # As a vendor's changed key reads in the log: curl's bar, gpgv's own
        # lines, bb's ERROR, the partial copy removed. The row is the ERROR.
        tail = toolchains._job_tail("######################################################################## 100.0%\n"
                                    "gpgv: using EDDSA key 0016B9E1A994\n"
                                    "gpgv: Can't check signature: No public key\n"
                                    "[builderbot] ERROR: kit: dl/data.bin does not carry its publisher's signature under kit.asc: nothing is installed\n"
                                    "[builderbot] WARN: install failed (exit 1); removing the partial /srv/tc/kit\n")
        got = toolchains._reason(tail, "install failed (exit 1)")
        self.assertEqual(got, "ERROR: kit: dl/data.bin does not carry its publisher's signature under kit.asc: nothing is installed · install failed (exit 1)")

    def test_a_refusal_after_its_detail_is_the_reason_alone(self):
        # The agent says what holds a toolchain, pid and all, on lines of
        # their own, then the refusal in one sentence: the row takes that.
        got = toolchains._reason(["  in use by node (pid 4242, ann's session)", "  in use by java (pid 4250, ann's session)",
                                  "refused: jdk is in use, so it was left as it is: try again once that has finished"],
                                 "install failed on the node")
        self.assertEqual(got, "refused: jdk is in use, so it was left as it is: try again once that has finished · install failed on the node")
        self.assertNotIn("pid", got)

    def test_a_long_reason_starts_at_a_line_not_mid_word(self):
        # B83: a tool pack's install, as bb-dev-sandbox logged it; the row
        # was cut by characters from the end and began '3pack · * branch'.
        out = "Permission denied: " + "x" * 300
        got = self.why("== aerie toolchains install wordy\n"
                       "[builderbot] fetching wordy at 047e27a1b2c3 into /mnt/bbdata/toolchains/n_6d799c7c/wordy\n"
                       "From http://192.168.1.16:3000/labadmin/r3pack\n"
                       " * branch            047e27a1b2c3d4e5f60718293a4b5c6d7e8f9012 -> FETCH_HEAD\n"
                       f"[builderbot] ERROR: wordy installed but /mnt/bbdata/toolchains/n_6d799c7c/wordy/bin/wordy does not run: {out}\n"
                       "[builderbot] WARN: install failed (exit 1); removing the partial /mnt/bbdata/toolchains/n_6d799c7c/wordy\n",
                       name="wordy")
        self.assertTrue(got.startswith("ERROR: wordy installed but"), got[:80])
        self.assertNotIn("FETCH_HEAD", got)
        self.assertTrue(got.endswith("failed on the node"), got[-60:])
        self.assertLessEqual(len(got), 400)
        # ...and one line too long for the row keeps its start, cut at a word.
        got = toolchains._reason(["ERROR: the tool said " + "word " * 120], "install failed on the node")
        self.assertTrue(got.startswith("ERROR: the tool said word") and got.endswith("… · install failed on the node"), got)
        self.assertLessEqual(len(got), 400)

    def test_the_digests_a_download_is_held_to_stay_in_the_log(self):
        # sdk.sh says each digest on a line of its own before its refusal,
        # for whoever compares them in the job's log; the row says why alone.
        got = toolchains._reason(["[builderbot] sha256 of what https://example.invalid/k.zip answered: " + "ab" * 32,
                                  "[builderbot] sha256 expected: " + "cd" * 32,
                                  "[builderbot] gpgv: using key " + "EF" * 20,
                                  "[builderbot] ERROR: kotlin-lsp: k.zip is not the file its entry pins: nothing is installed"],
                                 "install failed (exit 1)")
        self.assertEqual(got, "ERROR: kotlin-lsp: k.zip is not the file its entry pins: nothing is installed · install failed (exit 1)")


if __name__ == "__main__":
    unittest.main()
