"""The systems a node can be: what Enroll node's pulldown offers, and which
provisioner family file the built script carries for each (R204).

An entry is a distribution as a person knows their machine (what
os-release's PRETTY_NAME says); its family is the provisioner file under
nodes/families/, shared by the distributions that take the same packages,
package verbs and docker repository. Vetting is per entry, like the git
hosts' and hypervisors' (forges.py, vmtemplate.py): a walk on Rocky vets
Rocky and not AlmaLinux until Alma is walked. An entry without a vetted
line is offered only behind Offer dev features, tagged dev.
"""
import re
from pathlib import Path

import forges
import labrecord

FAMILIES_DIR = Path(__file__).resolve().parent.parent.parent / "nodes" / "families"

# What lab-systems walks on each system it makes a node of (test/lab-systems.mjs).
WALK = ("a VM made a node from its cloud image, enrolled; VM host installed and removed; a toolchain installed and "
        "removed; nginx run as a container from a compose file; a space synced and a terminal opened through the "
        "controller; Uninstall, the machine's own account kept")
WALK_NO_VM_HOST = WALK.replace("VM host installed and removed; ", "")

# An entry's "vetted" is typed where nothing dates it (a system in daily
# use). One with "walked" is vetted by the lab's own record (labrecord.py,
# R3 step 8): its line is what was walked, dated by the newest walk on
# record whose machine said it was this system, and with no walk on record
# it is not vetted. The dates were typed here by hand before, and stayed
# as the provisioner changed under them.
SYSTEMS = [
    {"id": "ubuntu", "name": "Ubuntu 24.04 or later", "family": "deb", "ids": ["ubuntu"],
     "vetted": "bb-sandbox and the dev pair's bb-dev-sandbox (Ubuntu 24.04 and 26.04), in daily use"},
    {"id": "rocky", "name": "Rocky Linux 9", "family": "rhel", "ids": ["rocky"],
     "walked": "a machine of its own on the dev pair: enroll, toolchains, storage, a synced space, a container, "
               "nginx, a Gitea runner, a shell and an agent's session"},
    {"id": "debian", "name": "Debian 12 or later", "family": "deb", "ids": ["debian", "raspbian"], "walked": WALK},
    {"id": "almalinux", "name": "AlmaLinux 9", "family": "rhel", "ids": ["almalinux"], "walked": WALK},
    {"id": "rhel", "name": "Red Hat Enterprise Linux 9", "family": "rhel", "ids": ["rhel"], "vetted": "",
     "why": "not walked: its image needs a Red Hat subscription. Rocky Linux and AlmaLinux are its rebuilds, and both are"},
    {"id": "centos", "name": "CentOS Stream 9", "family": "rhel", "ids": ["centos"], "walked": WALK},
    {"id": "fedora", "name": "Fedora", "family": "rhel", "ids": ["fedora"], "walked": WALK},
    {"id": "arch", "name": "Arch Linux", "family": "arch", "ids": ["arch", "archlinux", "manjaro"], "walked": WALK},
    {"id": "opensuse", "name": "openSUSE Leap or Tumbleweed", "family": "suse",
     "ids": ["opensuse", "opensuse-leap", "opensuse-tumbleweed", "suse", "sles"],
     "walked": WALK_NO_VM_HOST + "; VM host wants its full kernel, kernel-default, as its cloud image boots kernel-default-base"},
    {"id": "alpine", "name": "Alpine Linux", "family": "alpine", "ids": ["alpine"],
     "walked": WALK_NO_VM_HOST + "; a toolchain runs there only where it publishes a musl build, as Node does"},
    {"id": "void", "name": "Void Linux", "family": "void", "ids": ["void"], "vetted": "",
     "why": "not walked: Void publishes no cloud image for a VM to be made from, so it is walked only on a machine of its own"},
    {"id": "gentoo", "name": "Gentoo", "family": "gentoo", "ids": ["gentoo"], "vetted": "",
     "why": "not vetted: a rolling, source-built system whose image changes under it, so a walk would not hold from one release to the next"},
]
DEFAULT = "ubuntu"


def get(sid):
    """The entry with this id, or None."""
    return next((s for s in SYSTEMS if s["id"] == sid), None)


def allowed(sid):
    """Whether this system may be picked here: vetted, or dev features on."""
    s = get(sid)
    return bool(s) and (bool(s["vetted"]) or bool(forges.unvetted_ok and forges.unvetted_ok()))


def offered():
    """The pulldown's entries: every vetted one, and the rest when Offer dev
    features is on, each saying whether it is vetted."""
    return [{"id": s["id"], "name": s["name"], "family": s["family"], "vetted": bool(s["vetted"]),
             **({"why": s["why"]} if s.get("why") and not s["vetted"] else {})}
            for s in SYSTEMS if allowed(s["id"])]


def of_os(text):
    """The system whose ids name what the census says of the machine's OS
    ("linux x86_64 Ubuntu 24.04.2 LTS", "linux x86_64 Rocky Linux 9.4"),
    or "" when none does: a row enrolled before the system was recorded
    on it (R210) gets its script built for the system it reports."""
    words = re.findall(r"[a-z]+", str(text or "").lower())
    if "red" in words and "hat" in words:
        return "rhel"
    return next((s["id"] for s in SYSTEMS if any(i.replace("-", "") in words or i in words for i in s["ids"])), "")


def vet(record=None):
    """Each walked entry's vetted line read from the lab's record (`record`
    a path, the shipped one by default): what was walked, dated by the
    newest walk whose machine said it was this system, with the build it
    ran against where the record has one; "" and a why with none on record."""
    # Only a walk of a system as a node: the suite that makes one of each,
    # or the same done by hand on a machine of its own. A suite that asks a
    # node a question (lab-node) walks far less than the line says.
    walks = [r for r in labrecord.rows(record or labrecord.FILE) if r["suite"] in ("lab-systems", "by-hand")]
    for s in SYSTEMS:
        if "walked" not in s:
            continue
        row = next((r for r in walks if of_os(r["said"]) == s["id"] or r["subject"] == s["id"]), None)
        if row:
            how = row["suite"].replace("by-hand", "by hand") + (f" at build {row['build']}" if row["build"] else "")
            s["vetted"] = f"{row['at']}, {how}: {s['walked']} ({row['said']})"
            s.pop("why", None)
        else:
            s["vetted"] = ""
            s["why"] = "not vetted: the lab's record holds no walk of it (aerie tests lab writes one)"


vet()


def family_file(sid):
    """The provisioner family file the built script carries for this system."""
    s = get(sid)
    return FAMILIES_DIR / f"{s['family']}.sh" if s else None
