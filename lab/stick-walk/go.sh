#!/bin/bash
# A whole first run, from a blank machine: see README.md. go.sh IMAGE.stick.raw.xz
set -u
HERE="$(dirname "$(readlink -f "$0")")"; cd "$HERE" || exit 1
IMAGE="${1:?go.sh IMAGE.stick.raw.xz}"
mkdir -p run
(cd run && python3 -m http.server 8099 --bind 127.0.0.1 >/dev/null 2>&1 & echo $! > run/http.pid)
timeout 8 python3 walk.py stop
rm -f run/stick.raw run/browser.json run/serial.log run/blank-*.raw run/vars.fd
python3 walk.py prep "$IMAGE" | tail -1
python3 walk.py boot | tail -1
# Rescue once, for a root shell on the second serial port; then its true first boot.
cat > run/rescue.cmds <<'C'
export TERM=dumb; bind 'set enable-bracketed-paste off'; id -u
printf '[Unit]\nDescription=walk shell\nAfter=basic.target\n[Service]\nExecStart=/bin/bash -i\nStandardInput=tty\nStandardOutput=tty\nStandardError=tty\nTTYPath=/dev/ttyS1\nTTYReset=yes\nRestart=always\nTimeoutStopSec=1\nKillSignal=SIGKILL\nEnvironment=TERM=dumb\n[Install]\nWantedBy=multi-user.target\n' > /etc/systemd/system/walkshell.service; mkdir -p /etc/systemd/system/multi-user.target.wants; ln -sf ../walkshell.service /etc/systemd/system/multi-user.target.wants/walkshell.service; sync; systemctl reboot
C
timeout 140 python3 rescue.py run/rescue.cmds >/dev/null 2>&1
for _ in $(seq 1 30); do [ "$(curl -s -o /dev/null -m 4 -w '%{http_code}' http://127.0.0.1:7690/)" != 000 ] && break; python3 -c "import time;time.sleep(5)"; done
for _ in $(seq 1 40); do timeout 20 python3 walk.py sh 'test -f /etc/aerieos-controller/own-node && echo marked' 2>/dev/null | grep -q marked && break; python3 -c "import time;time.sleep(5)"; done
for step in landing2 makeit; do node person.mjs "$step"; done
python3 -c "import time;time.sleep(45)"
for step in shares nameclaude "create first-project" finish openproject storageshares pageshots; do
    # shellcheck disable=SC2086
    node person.mjs $step
done
# It has to come back whole.
timeout 25 python3 walk.py sh 'sync; systemctl reboot' >/dev/null 2>&1
python3 -c "import time;time.sleep(60)"
timeout 60 python3 walk.py sh 'ls /usr/local/sbin | tr "\n" " "; systemctl is-active builderbot-agent docker containerd libvirtd smbd | tr "\n" " "; systemctl show builderbot-agent -p NRestarts; zpool list -H -o name,health; findmnt -rn -o TARGET,SOURCE /home /workspace /srv/aerieos/projects'
