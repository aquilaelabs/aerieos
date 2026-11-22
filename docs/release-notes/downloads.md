### Which download is for what

| File | What it is for |
|---|---|
| `aerieos-os-@VER@.stick.raw.xz` | AerieOS for a USB stick: the USB edition, written with AerieOS USB Maker below, or any tool that writes a raw image. |
| `aerieos-os-@VER@.iso` | What a machine already running AerieOS updates from: its Updates section fetches it by itself, or takes it from a folder where the machine is offline. Not an installer: a new machine is set up from the USB edition above. |
| `aerieos-usb-maker-@VER@.exe` | AerieOS USB Maker for Windows: picks the release and the stick, and writes it. |
| `aerieos-controller-@VER@.tar.gz` | The controller for a bare-metal install on Linux, which the install script fetches by itself; nothing to download by hand. The container edition is the image `ghcr.io/@REPO@`. |
| `aerieos-app-@VER@.apk` | The Android app: your AerieOS on your phone, its spaces, approvals and notifications. |
| `aerieos-companion-@VER@.exe` | The desktop companion for Windows: a space's files kept in a folder on your computer, and the computer lent to a space's sessions. |
| `aerieos-companion-@VER@.pyz` | The same companion run with Python, on Linux, a Mac or Windows. |
| `aerieos-vscode-@VER@.vsix` | The VS Code extension: a space's files and sessions in your editor. |
| `aerieos-image-@VER@.digest` | One line naming this release's container image by its digest, `ghcr.io/@REPO@@sha256:...`: what `docker pull` takes to run exactly this release. |
| `SHA256SUMS`, `SHA256SUMS.sig` | The list of this release's files with the checksum of each, and its signature: what every AerieOS install checks a file it takes against. Nothing to install. |
| `*.sha256` | The checksum of the file of the same name, to check a download; nothing to install. |
| `aerieos-os-@VER@.attestation.jsonl` | The ISO's build attestation as a file, for a machine that updates offline. Each download above but the Android app has a build attestation on GitHub (`gh attestation verify FILE --repo @REPO@`); the Android app is signed with its own certificate instead, which these notes name at their end. |

A file that is not in the list above was not built for this release.

