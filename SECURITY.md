# Security

## Reporting a vulnerability

Report it privately, through GitHub: on this repository's **Security** tab,
press **Report a vulnerability**. The report reaches the maintainers alone,
and the fix is worked on in private until it ships.

Please do not open a public issue, a pull request, or a post anywhere public
for a vulnerability until a fix is released.

Say what you found, which AerieOS version and edition it is in (the
container, bare metal or the USB edition), and the steps that show it. A
proof of concept helps; one that reaches other people's machines or data
does not, so test only on an install of your own.

## What to expect

- An answer within a week saying whether it is confirmed.
- A fix in the next dev build for a confirmed issue, sooner where it is
  serious, and the release notes naming it once it ships.
- Credit in those notes if you would like it.

## What is covered

AerieOS has no stable release yet: the newest dev build is the one fixed.
Everything this repository ships is in scope: the controller and its
dashboard, the node agent and its provisioner, the installable OS and the
USB edition, the Android app and the Windows companion. The coding agents a
node installs (Claude Code, Codex, Copilot, Grok) belong to their makers:
report what is theirs to them.

How AerieOS keeps secrets, holds sessions to what a space allows and checks
what it installs is in [docs/security.md](docs/security.md).
