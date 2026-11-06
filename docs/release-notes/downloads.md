### Which download is for what

| File | What it is for |
|---|---|
| `aerieos-os-@VER@.stick.raw.xz` | AerieOS for a USB stick: the USB edition, written with AerieOS USB Maker below, or any tool that writes a raw image. |
| `aerieos-os-@VER@.iso` | AerieOS installed on a machine's own disk, from a USB stick or a VM's virtual drive. |
| `aerieos-usb-maker-@VER@.exe` | AerieOS USB Maker for Windows: picks the release and the stick, and writes it. |
| `aerieos-controller-@VER@.tar.gz` | The controller for a bare-metal install on Linux, which the install script fetches by itself; nothing to download by hand. The container edition is the image `ghcr.io/@REPO@`. |
| `aerieos-app-@VER@.apk` | The Android app: your AerieOS on your phone, its spaces, approvals and notifications. |
| `aerieos-companion-@VER@.exe` | The desktop companion for Windows: a space's files kept in a folder on your computer, and the computer lent to a space's sessions. |
| `aerieos-companion-@VER@.pyz` | The same companion run with Python, on Linux, a Mac or Windows. |
| `aerieos-vscode-@VER@.vsix` | The VS Code extension: a space's files and sessions in your editor. |
| `*.sha256`, `*.attestation.jsonl` | The checksum and the build attestation of the file of the same name, to check a download; nothing to install. |

A file that is not in the list above was not built for this release.

