"""Where a node keeps what is AerieOS's, under its own name (R204).

A node kept its record in /etc/builderbot and its state in
/var/lib/builderbot, and ran builderbot-agent, the name the product had
before it was AerieOS. They are /etc/aerieos, /var/lib/aerieos and
aerieos-agent now, and a node comes to them in two steps, neither of which
moves anything under a running agent (an agent that cannot find its
node.json crash-loops with no way to reach it remotely):

  * every agent, as it starts as root, makes the new names answer where
    they do not yet (`ensure`): /etc/aerieos and /var/lib/aerieos as links
    to the folders that are there, and aerieos-agent as a command that runs
    the one installed. Nothing is moved; both names name the same thing.
  * the Enroll script, run on the machine by a person, makes the new names
    the real ones (the folders moved, the old names left as links to them,
    the service installed as aerieos-agent, builderbot-agent a command that
    runs it), so a path a record still holds under the old name goes on
    resolving.

So this file answers with whichever is really there: the new name where it
exists, the old where only that does, the new on a machine with neither.
No import but the standard library: the provisioner's tools read it too.
"""
import os

OLD_ETC, NEW_ETC = "/etc/builderbot", "/etc/aerieos"
OLD_VAR, NEW_VAR = "/var/lib/builderbot", "/var/lib/aerieos"
OLD_UNIT, NEW_UNIT = "builderbot-agent", "aerieos-agent"
OLD_CMD, NEW_CMD = "/usr/local/sbin/builderbot-agent", "/usr/local/sbin/aerieos-agent"
OLD_SANDBOX, NEW_SANDBOX = "/usr/local/sbin/bb-sandbox", "/usr/local/sbin/aerie-sandbox"


def _home(new, old):
    return new if (os.path.isdir(new) or not os.path.isdir(old)) else old


ETC = _home(NEW_ETC, OLD_ETC)
VAR = _home(NEW_VAR, OLD_VAR)


def unit():
    """The agent's service as this machine has it."""
    have = lambda u: any(os.path.exists(p) for p in (  # noqa: E731
        f"/etc/systemd/system/{u}.service", f"/etc/init.d/{u}", f"/etc/conf.d/{u}"))
    return NEW_UNIT if have(NEW_UNIT) or not have(OLD_UNIT) else OLD_UNIT


def command():
    """What a person types for the agent here: the new name where it answers."""
    return os.path.basename(NEW_CMD if os.path.exists(NEW_CMD) or not os.path.exists(OLD_CMD) else OLD_CMD)


def sandbox_bin():
    return NEW_SANDBOX if os.path.exists(NEW_SANDBOX) or not os.path.exists(OLD_SANDBOX) else OLD_SANDBOX


def ensure(own_path="", say=lambda msg: None):
    """The new names made to answer on a machine that has only the old ones,
    by root, adding and never moving: a link for each folder, a command for
    the agent. What could not be made is said and left; the old names work."""
    if os.geteuid() != 0:
        return
    for new, old in ((NEW_ETC, OLD_ETC), (NEW_VAR, OLD_VAR)):
        try:
            if os.path.isdir(old) and not os.path.islink(old) and not os.path.lexists(new):
                os.symlink(old, new)
                say(f"{new} now answers as {old} does (a link; the Enroll script makes it the folder itself)")
        except OSError as e:
            say(f"{new} could not be made to answer ({e}); {old} is used as before")
    try:
        if own_path == OLD_CMD and not os.path.lexists(NEW_CMD):
            with open(NEW_CMD, "w") as f:
                f.write(f"#!/bin/sh\n# AerieOS's agent under its own name (names.py): the one installed here.\nexec {OLD_CMD} \"$@\"\n")
            os.chmod(NEW_CMD, 0o755)
            say(f"{os.path.basename(NEW_CMD)} now runs the agent here, as {os.path.basename(OLD_CMD)} does")
    except OSError as e:
        say(f"{NEW_CMD} could not be written ({e}); {os.path.basename(OLD_CMD)} is the command as before")
    try:
        if os.path.exists(OLD_SANDBOX) and not os.path.lexists(NEW_SANDBOX):
            with open(NEW_SANDBOX, "w") as f:
                f.write(f"#!/bin/sh\n# AerieOS's tool for this machine, under its own name: bb-sandbox, as installed.\nexec {OLD_SANDBOX} \"$@\"\n")
            os.chmod(NEW_SANDBOX, 0o750)
    except OSError:
        pass
