"""What each system apply and each job type reaches on the agent, and with
which arguments: every name the controller can send, an unknown one, and the
applies a machine that is not a sandbox refuses. Nothing here runs an apply
or a job: the methods they reach are recorders."""
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agentpkg  # noqa: E402

agent = agentpkg.load("aerieos_agent_applies")
configplane = agent.module("configplane")
http80 = agent.module("http80")

# Every apply, the method it reaches and what that method is handed after
# the job: the config, the apply's own name, or nothing.
APPLIES = {
    "root": ("_apply_root", "cfg"),
    "storage": ("_apply_storage", "cfg"),
    "network": ("_apply_network", "cfg"),
    "runner": ("_apply_runner", "cfg"),
    "funnel": ("_apply_funnel", "cfg"),
    "uninstall": ("_apply_uninstall", "cfg"),
    "reboot": ("_apply_power", "what"),
    "poweroff": ("_apply_power", "what"),
    "gpu": ("_apply_gpu", ""),
    "door": ("_apply_door", "cfg"),
    "lockdown": ("_apply_lockdown", ""),
    "feature": ("_apply_feature", "cfg"),
    "controller-update": ("_apply_controller_update", "cfg"),
    "storage-share": ("_apply_storage_share", "cfg"),
    "storage-pool": ("_apply_storage_pool", "cfg"),
    "storage-snapshot": ("_apply_storage_snapshot", "cfg"),
    "storage-array": ("_apply_storage_array", "cfg"),
    "console": ("_apply_console", "cfg"),
    "storage-adopt": ("_apply_storage_adopt", "cfg"),
    "host-update": ("_apply_host_update", "cfg"),
    "storage-backup": ("_apply_storage_backup", "cfg"),
    "machine": ("_apply_machine", "cfg"),
    "system-pool": ("_apply_system_pool", "cfg"),
    "os-kept": ("_apply_os_kept", "cfg"),
    "projects-folder": ("_apply_projects_folder", "cfg"),
    "os-update": ("_apply_os_update", "cfg"),
}
# The applies only a machine provisioned as a sandbox takes. gpu-off is one
# of them, and is the one apply that is a command rather than a method above.
NEED_SANDBOX = {"storage", "network", "root", "gpu", "gpu-off", "feature"}

# Every job type whose run is one call into the agent, handed the job and
# its spec.
RUNNERS = {
    "self-update": "self_update",
    "system": "system",
    "scan": "scan",
    "vm": "vm",
    "image": "image",
    "sign": "sign",
    "sign-key": "sign_key",
    "cache-clear": "cache_clear",
    "storage": "storage_measure",
    "avd-remove": "avd_remove",
    "phones-idle": "phones_idle",
    "claude-update": "claude_update",
    "tell": "tell",
    "codex-update": "agent_update",
    "copilot-update": "agent_update",
    "grok-update": "agent_update",
    "opencode-update": "agent_update",
}


class SaidJob:
    """What system() uses of a job: its log."""

    def __init__(self):
        self.said = []

    def say(self, text):
        self.said.append(text)


def plane(sh_rc=0):
    """An agent whose applies are recorders: every method in APPLIES, the
    sandbox tool's refresh, the root command runner and the hello. The
    agent is never constructed: system() reads none of its state."""
    calls = []

    def recorder(name, answer):
        def record(self, *args, **kw):
            calls.append((name, args, kw))
            return answer
        return record

    names = {method for method, _ in APPLIES.values()}
    body = {name: recorder(name, ("succeeded", 0)) for name in names}
    body["refresh_sandbox_tool"] = recorder("refresh_sandbox_tool", None)
    body["_sh"] = recorder("_sh", sh_rc)
    body["hello_again"] = recorder("hello_again", None)
    body["__init__"] = lambda self: None
    return type("Plane", (agent.Agent,), body)(), calls


class Applies(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.tool = os.path.join(d.name, "bb-sandbox")
        with open(self.tool, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\n")
        os.chmod(self.tool, 0o755)
        self.absent = os.path.join(d.name, "nothing-here")

    def system(self, what, config=None, sandbox=True, sh_rc=0):
        me, calls = plane(sh_rc)
        job = SaidJob()
        spec = {"apply": what}
        if config is not None:
            spec["config"] = config
        with mock.patch.object(configplane, "SANDBOX_BIN", self.tool if sandbox else self.absent):
            answer = me.system(job, spec)
        return answer, calls, job

    def test_every_apply_reaches_its_method_with_its_arguments(self):
        for what, (method, takes) in APPLIES.items():
            with self.subTest(apply=what):
                cfg = {"marker": what}
                answer, calls, job = self.system(what, cfg)
                self.assertEqual(answer, ("succeeded", 0))
                self.assertEqual(job.said, [])
                self.assertEqual([c[0] for c in calls], ["refresh_sandbox_tool", method])
                self.assertEqual(calls[0][1:], ((job,), {}))
                name, args, kw = calls[1]
                self.assertEqual(kw, {})
                self.assertIs(args[0], job)
                if takes == "cfg":
                    self.assertEqual(len(args), 2)
                    self.assertIs(args[1], cfg)
                elif takes == "what":
                    self.assertEqual(args[1:], (what,))
                else:
                    self.assertEqual(args[1:], ())

    def test_the_agent_s_table_is_these_applies_and_no_other(self):
        table = agent.ConfigPlaneMixin.APPLIES
        self.assertEqual(set(table), set(APPLIES) | {"gpu-off"})
        self.assertEqual({what for what, row in table.items() if row[1]}, NEED_SANDBOX)
        for what, (method, takes) in APPLIES.items():
            self.assertEqual((table[what][0], table[what][2]), (method, takes), what)
        for method, _, _ in table.values():
            self.assertTrue(callable(getattr(agent.Agent, method, None)), method)

    def test_a_config_that_is_not_a_table_is_handed_over_empty(self):
        for what, (method, takes) in APPLIES.items():
            if takes != "cfg":
                continue
            for config in (None, ["a"], "text", 3):
                with self.subTest(apply=what, config=config):
                    _, calls, _ = self.system(what, config)
                    self.assertEqual(calls[1], (method, (mock.ANY, {}), {}))

    def test_what_a_method_answers_is_the_job_s_answer(self):
        me, calls = plane()
        type(me)._apply_door = lambda self, job, cfg: ("failed", 9)
        with mock.patch.object(configplane, "SANDBOX_BIN", self.tool):
            self.assertEqual(me.system(SaidJob(), {"apply": "door"}), ("failed", 9))

    def test_gpu_off_stops_the_display_and_says_hello(self):
        answer, calls, job = self.system("gpu-off", {"marker": 1})
        self.assertEqual(answer, ("succeeded", 0))
        self.assertEqual(calls, [
            ("refresh_sandbox_tool", (job,), {}),
            ("_sh", (job, [self.tool, "gpu-off"]), {"timeout": 120}),
            ("hello_again", ("the GPU was switched off",), {}),
        ])
        self.assertEqual(job.said, [])

    def test_gpu_off_fails_with_the_command_s_exit_and_still_says_hello(self):
        answer, calls, _ = self.system("gpu-off", sh_rc=3)
        self.assertEqual(answer, ("failed", 3))
        self.assertEqual([c[0] for c in calls], ["refresh_sandbox_tool", "_sh", "hello_again"])

    def test_a_machine_that_is_no_sandbox_refuses_only_what_edits_it(self):
        for what in list(APPLIES) + ["gpu-off"]:
            with self.subTest(apply=what):
                answer, calls, job = self.system(what, {}, sandbox=False)
                if what in NEED_SANDBOX:
                    self.assertEqual(answer, ("failed", 77))
                    self.assertEqual([c[0] for c in calls], ["refresh_sandbox_tool"])
                    self.assertEqual(job.said, [
                        f"refused: {what} edits this machine's own configuration, and this node "
                        f"was not provisioned as an AerieOS sandbox ({self.absent} is not here)\n"])
                else:
                    self.assertEqual(answer, ("succeeded", 0))
                    self.assertEqual([c[0] for c in calls], ["refresh_sandbox_tool", APPLIES[what][0]])
                    self.assertEqual(job.said, [])

    def test_a_tool_that_is_there_and_cannot_be_run_is_no_sandbox(self):
        os.chmod(self.tool, 0o644)
        if os.access(self.tool, os.X_OK):
            self.skipTest("this account may run any file")
        answer, calls, _ = self.system("storage", {})
        self.assertEqual(answer, ("failed", 77))
        self.assertEqual([c[0] for c in calls], ["refresh_sandbox_tool"])

    def test_an_unknown_apply_is_refused_with_its_sentence(self):
        for what in ("nope", "", None, "Storage", "storage ", "_apply_storage", "APPLIES",
                     ["storage"], {"apply": "storage"}, 7, ("reboot",)):
            for sandbox in (True, False):
                with self.subTest(apply=what, sandbox=sandbox):
                    answer, calls, job = self.system(what, {}, sandbox=sandbox)
                    self.assertEqual(answer, ("failed", 64))
                    self.assertEqual([c[0] for c in calls], ["refresh_sandbox_tool"])
                    self.assertEqual(job.said, [f"refused: unknown system job {what!r}\n"])

    def test_a_spec_with_no_apply_is_refused_the_same(self):
        me, calls = plane()
        job = SaidJob()
        self.assertEqual(me.system(job, {}), ("failed", 64))
        self.assertEqual(job.said, ["refused: unknown system job None\n"])


class Recorded:
    """The agent a job runs against: every method a recorder that answers
    the same, and the two things a job's end touches."""

    def __init__(self, calls, answer=("succeeded", 0)):
        self._calls, self._answer = calls, answer
        self._logins_at = 99
        self.sessnet = mock.Mock(containers_at=5.0)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)

        def record(*args, **kw):
            held = {"paused": http80._paused} if name == "compose" else {}
            self._calls.append(("agent." + name, args, dict(kw, **held)))
            return None if name in ("finished", "reexec_when_idle", "session_renew", "hello") else self._answer
        return record


def run(kind, spec=None, answer=("succeeded", 0), no_type=False):
    """One job of this type run to its end, with what it called, in order,
    what it said and what it reported."""
    calls = []
    me = Recorded(calls, answer)

    class RunJob(agent.Job):
        def say(self, text):
            self.said.append(text)

        def flush(self, keepalive=False):
            return True

        def report(self, state, code, error):
            self.ended = (state, code, error)

        def claude_login(self, *args, **kw):
            calls.append(("job.claude_login", args, kw))
            return answer

        def claude_logout(self, *args, **kw):
            calls.append(("job.claude_logout", args, kw))
            return answer

        def exec(self, *args, **kw):
            calls.append(("job.exec", args, kw))
            return answer

    record = {"id": "j1"} if no_type else {"id": "j1", "type": kind}
    if spec is not None:
        record["spec"] = spec
    job = RunJob(me, record)
    job.said, job.ended = [], None
    with mock.patch.object(agent.module("jobs"), "log", lambda *_a: None):
        job.run()
    return job, me, calls


def work(calls):
    """A job's calls without its end's bookkeeping."""
    return [c for c in calls if c[0] not in ("agent.finished", "agent.reexec_when_idle")]


class JobTypes(unittest.TestCase):
    def test_every_plain_type_reaches_its_runner_with_the_job_and_the_spec(self):
        for kind, method in RUNNERS.items():
            with self.subTest(type=kind):
                spec = {"marker": kind}
                job, me, calls = run(kind, spec)
                self.assertEqual([c[0] for c in work(calls)], ["agent." + method])
                _, args, kw = work(calls)[0]
                self.assertEqual(len(args), 2)
                self.assertIs(args[0], job)
                self.assertIs(args[1], spec)
                self.assertEqual(kw, {})
                self.assertEqual(job.ended, ("succeeded", 0, ""))
                self.assertEqual(job.said, [kind + "\n"])
                self.assertEqual(me._logins_at, 99)
                self.assertEqual(me.sessnet.containers_at, 5.0)

    def test_the_job_s_table_is_these_types_and_names_methods_the_agent_has(self):
        table = agent.Job.RUNNERS
        self.assertEqual(table, {k: m for k, m in RUNNERS.items() if m != "agent_update"})
        for method in table.values():
            self.assertTrue(callable(getattr(agent.Agent, method, None)), method)

    def test_the_test_names_every_install_the_agent_knows(self):
        self.assertEqual({k for k, m in RUNNERS.items() if m == "agent_update"}, set(agent.AGENT_INSTALLS))

    def test_a_runner_s_failure_is_the_job_s_with_its_exit(self):
        for kind in RUNNERS:
            with self.subTest(type=kind):
                job, _, _ = run(kind, {"x": 1}, answer=("failed", 9))
                self.assertEqual(job.ended, ("failed", 9, "exit 9"))

    def test_a_system_job_s_first_line_names_its_apply(self):
        job, _, _ = run("system", {"apply": "storage"})
        self.assertEqual(job.said, ["system: storage\n"])

    def test_compose_runs_with_port_80_let_go_and_the_containers_read_again(self):
        spec = {"marker": 1}
        before = http80._paused
        job, me, calls = run("compose", spec)
        self.assertEqual(work(calls), [("agent.compose", (job, spec), {"paused": before + 1})])
        self.assertEqual(http80._paused, before)
        self.assertEqual(me.sessnet.containers_at, 0.0)
        self.assertEqual(job.ended, ("succeeded", 0, ""))

    def test_a_toolchain_job_renews_the_session_half_and_says_hello(self):
        for action in ("install", "remove", "", None):
            with self.subTest(action=action):
                spec = {"action": action}
                job, _, calls = run("toolchain", spec)
                self.assertEqual(work(calls), [("agent.toolchain", (job, spec), {}),
                                               ("agent.session_renew", (), {}),
                                               ("agent.hello", (), {})])

    def test_a_toolchain_check_moves_nothing(self):
        spec = {"action": "check"}
        job, _, calls = run("toolchain", spec)
        self.assertEqual(work(calls), [("agent.toolchain", (job, spec), {})])

    def test_a_sign_in_names_its_agent_and_asks_for_the_logins_again(self):
        for kind, which in (("claude-login", ""), ("codex-login", "codex"),
                            ("copilot-login", "copilot"), ("grok-login", "grok")):
            with self.subTest(type=kind):
                spec = {"marker": kind}
                job, me, calls = run(kind, spec)
                self.assertEqual(work(calls), [("job.claude_login", (spec, which), {})])
                self.assertEqual(me._logins_at, 0)

    def test_a_sign_out_names_its_agent_and_asks_for_the_logins_again(self):
        for kind, which in (("claude-logout", ""), ("codex-logout", "codex"),
                            ("copilot-logout", "copilot"), ("grok-logout", "grok")):
            with self.subTest(type=kind):
                spec = {"marker": kind}
                job, me, calls = run(kind, spec)
                self.assertEqual(work(calls), [("job.claude_logout", (spec, which), {})])
                self.assertEqual(me._logins_at, 0)

    def test_the_test_names_every_sign_in_the_agent_knows(self):
        self.assertEqual(agent.AGENT_LOGINS, {"codex-login": "codex", "copilot-login": "copilot", "grok-login": "grok"})
        self.assertEqual(agent.AGENT_LOGOUTS,
                         {"codex-logout": "codex", "copilot-logout": "copilot", "grok-logout": "grok"})

    def test_a_pack_s_agent_signs_in_and_out_by_the_name_in_the_spec(self):
        for kind, method in (("agent-login", "job.claude_login"), ("agent-logout", "job.claude_logout")):
            with self.subTest(type=kind):
                spec = {"agent": "aider"}
                job, me, calls = run(kind, spec)
                self.assertEqual(work(calls), [(method, (spec, "aider"), {"pack": True})])
                self.assertEqual(me._logins_at, 0)

    def test_a_pack_s_sign_in_for_a_built_in_agent_or_no_agent_is_refused(self):
        for kind in ("agent-login", "agent-logout"):
            for which in ("claude", "codex", "copilot", "grok", "", None, "Aider", "a", "x" * 17, "ai der"):
                with self.subTest(type=kind, agent=which):
                    job, me, calls = run(kind, {"agent": which})
                    self.assertEqual(work(calls), [])
                    self.assertEqual(job.said[1:], ["refused: a pack's agent's sign-in names the agent it is for\n"])
                    self.assertEqual(job.ended, ("failed", 64, "exit 64"))
                    self.assertEqual(me._logins_at, 0)

    def test_any_other_type_is_a_command(self):
        for kind in ("exec", "build", "nope", "", "System", "self_update", "RUNNERS", "run", 7):
            with self.subTest(type=kind):
                spec = {"argv": ["true"]}
                job, me, calls = run(kind, spec)
                self.assertEqual(work(calls), [("job.exec", (spec,), {})])
                self.assertEqual(job.ended, ("succeeded", 0, ""))
                self.assertEqual(me._logins_at, 99)

    def test_a_job_with_no_type_is_a_command(self):
        for record_type in (None, "absent"):
            with self.subTest(type=record_type):
                job, _, calls = run(None, {"argv": ["true"]}, no_type=record_type == "absent")
                self.assertEqual([c[0] for c in work(calls)], ["job.exec"])
                self.assertEqual(job.said, ["exec\n"])

    def test_a_job_with_no_spec_hands_its_runner_an_empty_one(self):
        job, _, calls = run("scan")
        self.assertEqual(work(calls), [("agent.scan", (job, {}), {})])

    def test_a_type_that_is_not_a_word_fails_as_the_agent_s_error(self):
        # A list is no key of the installs' table: the job ends failed with
        # the agent's own exit, and nothing was run.
        job, _, calls = run(["scan"], {})
        self.assertEqual(work(calls), [])
        self.assertEqual(job.ended, ("failed", 70, "agent error: TypeError"))
        self.assertTrue(job.said[1].startswith("agent error: TypeError: "))

    def test_a_docker_command_has_the_containers_read_again(self):
        job, me, _ = run("exec", {"argv": ["/usr/bin/docker", "ps"]})
        self.assertEqual(me.sessnet.containers_at, 0.0)

    def test_a_self_update_that_installed_nothing_leaves_the_agent_running(self):
        _, _, calls = run("self-update", {})
        self.assertEqual([c[0] for c in calls], ["agent.self_update", "agent.finished"])


if __name__ == "__main__":
    unittest.main()
