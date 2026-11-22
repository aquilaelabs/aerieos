#!/usr/bin/env bash
# The library a release's build uses its key with, installed from
# tools/release-requirements.txt into a folder of its own, every file held
# to the sha256 that list gives it: a wheel PyPI serves under another hash,
# or a library the list does not name, stops the install.
#
#   tools/release-lib.sh DIR
#
# Run in a step that holds no secret; the step that holds the key then
# reads the library by PYTHONPATH=DIR and installs nothing. Into a folder
# rather than the runner's own Python, which a hosted runner's system
# refuses a pip install into, and which would leave the runner's copy of
# the library, of whatever version, ahead of this one.
set -euo pipefail

dir="${1:?the folder the library goes in}"
here="$(cd "$(dirname "$0")" && pwd)"
python3 -m pip install --quiet --disable-pip-version-check --no-cache-dir \
    --require-hashes --only-binary :all: --target "$dir" -r "$here/release-requirements.txt"
# Said, and held to this folder: the copy the key's step will import.
PYTHONPATH="$dir" python3 - "$dir" <<'PY'
import os
import sys

import cryptography

at = os.path.realpath(os.path.dirname(cryptography.__file__))
if not at.startswith(os.path.realpath(sys.argv[1]) + os.sep):
    sys.exit(f"release-lib: cryptography loads from {at}, not from {sys.argv[1]}")
print(f"cryptography {cryptography.__version__} in {sys.argv[1]}, each file held to its hash")
PY
