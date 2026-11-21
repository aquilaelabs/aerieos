"""A tool pack across distributions (R171): its system block names packages
per package manager as the shipped recipes do, each list held to its
manager's names; a node whose manager the pack names none for is told so
on the pack's row and refused at Install, and a pack with no system
packages, or one naming the node's manager, fits every family.

And the two shapes every entry is held to for what reaches a node as more
than a file: a system package's name is a package's name, never an option
or apt's remove and install suffixes, and a variable an entry sets is none
a loader, a shell, an interpreter, git, ssh or AerieOS reads at its start;
one rule each (packformat.system_name_ok, env_name_ok), the same for a
pack, a shipped row, a catalog's newer row and a coding agent's recipe."""
import copy
import json
import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import agents  # noqa: E402
import catalogrows  # noqa: E402
import packformat  # noqa: E402
import toolchains  # noqa: E402
import toolpacks  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
SHIPPED = json.loads((ROOT / "config" / "toolchains.json").read_text())["toolchains"]
# What no entry sets, by the kind of thing that reads it at its start.
KEPT = ("PATH", "HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "IFS", "ENV", "BASH_ENV", "PROMPT_COMMAND",
        "LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT", "DYLD_INSERT_LIBRARIES",
        "PYTHONSTARTUP", "PYTHONPATH", "PERL5OPT", "RUBYOPT", "NODE_OPTIONS",
        "GIT_SSH", "GIT_SSH_COMMAND", "GIT_EXEC_PATH", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_COUNT", "SSH_AUTH_SOCK", "SSH_ASKPASS",
        "BB_TOKEN", "BUILDERBOT_URL", "AERIEOS_HOME",
        # Each loads code into, or redirects, a tool another entry's install
        # is checked with: python, OpenSSL, the C library, tar, git, curl, java.
        "PYTHONHOME", "PYTHONUSERBASE", "OPENSSL_CONF", "GCONV_PATH", "TAR_OPTIONS", "GIT_TEMPLATE_DIR", "GIT_ASKPASS",
        "GIT_DIR", "CURL_HOME", "SSL_CERT_FILE", "HTTPS_PROXY", "JAVA_TOOL_OPTIONS", "XDG_CONFIG_HOME", "SHELLOPTS", "PS4")

BASE = {"name": "hexkit", "label": "Hex kit", "about": "Looks inside binaries.", "platforms": ["linux/amd64"],
        "install": {"steps": [["sh", "{dir}/install.sh"]]}, "layout": {"bin": ["bin"], "tool": "bin/hexkit"},
        "verbs": {"dump": {"about": "A file as hex.", "usage": "FILE", "run": ["{dir}/bin/hexkit", "dump", "{args}"]}}}


class Families(unittest.TestCase):
    def test_each_manager_keeps_its_own_names(self):
        m, errors = toolpacks.validate(dict(BASE, system={"apt": ["libssl-dev"], "dnf": ["openssl-devel"], "pacman": ["openssl"],
                                                           "zypper": ["libopenssl-devel"], "apk": ["openssl-dev"]}))
        self.assertEqual(errors, [])
        self.assertEqual(sorted(m["system"]), ["apk", "apt", "dnf", "pacman", "zypper"])
        _, errors = toolpacks.validate(dict(BASE, system={"apt": ["Bad Name"], "brew": ["x"]}))
        self.assertTrue(any("system.apt lists Debian and Ubuntu package names" in e for e in errors), errors)
        self.assertTrue(any("system.brew is not a package manager" in e for e in errors), errors)

    def test_a_system_package_s_name_is_a_name_and_nothing_a_package_manager_reads_as_more(self):
        # A name that ends in its own + (g++ on apt and apk, gcc-c++ on dnf
        # and zypper) is a name: to apt a trailing + asks to install, which
        # is what the list asks.
        for good in ("libssl-dev", "libstdc++6", "g++-12", "libicu73_2", "python3.12", "libc6:i386", "7zip", "Xvfb", "libasound2t64|libasound2",
                     "g++", "gcc-c++", "clang|g++"):
            self.assertTrue(packformat.system_name_ok(good), good)
        # An option, apt's suffix for remove, a version or a pattern, a
        # path, a second word, an empty alternative.
        for bad in ("-y", "--allow-downgrades", "-oAPT::Get::Assume-Yes=true", "openssh-server-", "g++-", "curl=8.5.0", "lib*", "./x.deb", "/tmp/x.deb",
                    "a b", "a;b", "$(id)", "a|", "|a", "a|-b", "a|b-", "", "x" * 81, 7, None, ["a"], "caf\u00e9"):
            self.assertFalse(packformat.system_name_ok(bad), repr(bad))
            for mgr in toolpacks.SYSTEM_NAMES:
                self.assertTrue(toolpacks.validate(dict(BASE, system={mgr: ["good", bad]}))[1], (mgr, bad))
        # A portage name is CATEGORY/NAME, each part a name; no other manager's is.
        self.assertTrue(packformat.system_name_ok("dev-libs/icu", "emerge"))
        for bad, mgr in (("dev-libs/icu", "apt"), ("dev-libs/icu", ""), ("a/b/c", "emerge"), ("-a/b", "emerge"), ("a/b-", "emerge"), ("a/", "emerge")):
            self.assertFalse(packformat.system_name_ok(bad, mgr), (bad, mgr))

    def test_no_shipped_step_turns_its_installer_s_own_checks_off(self):
        # The .NET row's workload step ran with --skip-sign-check: on a
        # node that cannot cut its network it fetched with the packs'
        # signatures unchecked while the card read pinned (the audit of 21
        # Nov). A row that says its installer downloads the rest leaves
        # that installer's own checks on.
        off = re.compile(r"^--?(skip-sign|no-verify|insecure|allow-unauthenticated|nogpgcheck|no-check-certificate|disable-signature)", re.I)
        for r in SHIPPED:
            for step in (r.get("source") or {}).get("then") or []:
                for word in step.get("run") or []:
                    self.assertIsNone(off.match(str(word)), (r["name"], word))
        dotnet = next(r for r in SHIPPED if r["name"] == "dotnet")
        self.assertEqual(dotnet["source"]["then"][0]["run"], ["{dir}/dotnet", "workload", "install", "maui-android"])

    def test_every_shipped_row_s_system_packages_are_names_and_a_catalog_s_row_is_held_to_them(self):
        for r in SHIPPED:
            self.assertEqual(packformat.system_refused(r.get("system")), "", r["name"])
        row = next(r for r in SHIPPED if r.get("system", {}).get("apt"))
        for bad in (["-oDPkg::Pre-Invoke::=id"], ["openssh-server-"], "libssl-dev", [["libssl-dev"]]):
            newer = dict(copy.deepcopy(row), rev=catalogrows.rev_of(row) + 1)
            newer["system"] = dict(newer["system"], apt=bad)
            got, why = catalogrows.checked(newer, row)
            self.assertEqual((got, why.startswith("its system packages are not package names: each")), (None, True), bad)
        newer = dict(copy.deepcopy(row), rev=catalogrows.rev_of(row) + 1, system={"APT;id": ["x"]})
        self.assertIsNone(catalogrows.checked(newer, row)[0])


class Variables(unittest.TestCase):
    def test_the_one_rule(self):
        for good in ("JAVA_HOME", "CARGO_HOME", "NODE_PATH", "PLAYWRIGHT_BROWSERS_PATH", "X", "GIT_AUTHOR_NAME", "LDFLAGS", "SSHD"):
            self.assertTrue(packformat.env_name_ok(good), good)
        for bad in (*KEPT, "path", "1X", "A-B", "A B", "", "X" * 42, None, 7):
            self.assertFalse(packformat.env_name_ok(bad), repr(bad))

    def test_a_pack_s_layout_sets_none_of_them(self):
        got, errors = toolpacks.validate(dict(BASE, layout=dict(BASE["layout"], env={"HEXKIT_HOME": "", "HEXKIT_MODE": "=fast"})))
        self.assertEqual((errors, got["layout"]["env"]), ([], {"HEXKIT_HOME": "", "HEXKIT_MODE": "=fast"}))
        for name in KEPT:
            _, errors = toolpacks.validate(dict(BASE, layout=dict(BASE["layout"], env={"HEXKIT_HOME": "", name: "=/tmp/x"})))
            self.assertEqual(len([e for e in errors if e.startswith("layout.env sets variables of the tool's own")]), 1, name)

    def test_every_shipped_row_s_and_every_bundled_pack_s_variables_pass(self):
        for r in SHIPPED:
            for k in (r.get("layout") or {}).get("env") or {}:
                self.assertTrue(packformat.env_name_ok(k), (r["name"], k))
            self.assertEqual(packformat.source_refused(r["source"]), "", r["name"])
            self.assertEqual(toolpacks.validate(catalogrows.manifest_of(r), official=True)[1], [], r["name"])
        for p in sorted((ROOT / "packs").rglob("bbtool.json")):
            m = json.loads(p.read_text())
            self.assertEqual(toolpacks.validate(m, official=m.get("tier") == "official")[1], [], str(p))

    def test_a_catalog_s_row_and_an_installer_s_environment_are_held_to_it_too(self):
        row = next(r for r in SHIPPED if (r.get("layout") or {}).get("env") and (r.get("source") or {}).get("env"))
        for name in ("LD_PRELOAD", "BASH_ENV", "BB_TOKEN", "PYTHONPATH"):
            newer = dict(copy.deepcopy(row), rev=catalogrows.rev_of(row) + 1)
            newer["layout"] = dict(newer["layout"], env=dict(newer["layout"]["env"], **{name: "=/tmp/x"}))
            got, why = catalogrows.checked(newer, row)
            self.assertEqual((got, why.startswith("its layout.env sets variables of the tool's own")), (None, True), name)
            newer = dict(copy.deepcopy(row), rev=catalogrows.rev_of(row) + 1)
            newer["source"] = dict(newer["source"], env=dict(newer["source"]["env"], **{name: "/tmp/x"}))
            got, why = catalogrows.checked(newer, row)
            self.assertEqual((got, why.startswith("source.env maps the installer's own variables")), (None, True), name)

    def test_an_agent_s_recipe_its_sessions_and_its_sign_in_are_held_to_it_too(self):
        good = agents.get("codex").install
        self.assertEqual(agents.install_checked(good), (good, ""))
        for name in KEPT:
            self.assertTrue(agents.install_checked(good | {"env": {name: "{home}/x"}})[1], name)
            self.assertTrue(agents.install_checked(good | {"pin": [name, "{v}"]})[1], name)

    def test_a_node_of_another_manager_is_told_and_one_it_names_is_not(self):
        apt_only = {"system": {"apt": ["libssl-dev"]}}
        self.assertIn("for apt only, and this node installs with dnf", toolchains.family_miss(apt_only, "dnf"))
        self.assertEqual(toolchains.family_miss(apt_only, "apt"), "")
        self.assertEqual(toolchains.family_miss(apt_only, ""), "", "a node that has not said is not judged")
        self.assertEqual(toolchains.family_miss({}, "dnf"), "", "a pack with no system packages fits every family")


if __name__ == "__main__":
    unittest.main()
