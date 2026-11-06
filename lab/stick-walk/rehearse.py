#!/usr/bin/env python3
"""The move off another NAS rehearsed on the walked stick (R163 step 4):
the branch's agent and rehearse-inside.py handed to the stick over QEMU's
user network, run as root there in the background, and its PASS and FAIL
lines read back until it ends. The stick must be booted (walk.py boot) with
its root shell answering; its three blank disks and the NVMe are laid out
afresh, so whatever was on them is gone.

  rehearse.py            run it, print its lines, exit 1 on any FAIL
"""
import http.server
import os
import subprocess
import sys
import tarfile
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PORT = 18732


def sh(cmd, timeout=120):
    r = subprocess.run([sys.executable, os.path.join(HERE, "walk.py"), "sh", cmd], capture_output=True, text=True, timeout=timeout + 30)
    return r.stdout


def main():
    serve = tempfile.mkdtemp(prefix="rehearse-")
    with tarfile.open(os.path.join(serve, "agent.tgz"), "w:gz") as t:
        t.add(os.path.join(ROOT, "scripts", "agent", "aerieos_agent"), "aerieos_agent",
              filter=lambda i: None if "__pycache__" in i.name else i)
    with open(os.path.join(HERE, "rehearse-inside.py"), "rb") as f, open(os.path.join(serve, "inside.py"), "wb") as g:
        g.write(f.read())
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=serve, **k)  # noqa: E731
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        print(sh(f"rm -rf /root/rh && mkdir -p /root/rh && cd /root/rh && curl -sS -O http://10.0.2.2:{PORT}/agent.tgz -O http://10.0.2.2:{PORT}/inside.py "
                 "&& tar -xzf agent.tgz && (nohup python3 inside.py > /root/rh/log 2>&1 &) && echo started").strip().splitlines()[0])
        # Read until it ends, then printed whole: a line read while it is
        # being written would be printed cut and then skipped.
        end = time.time() + 1800
        while time.time() < end:
            time.sleep(5)
            lines = [ln for ln in sh("cat /root/rh/log").splitlines() if not ln.startswith("__END")]
            done = lines and (lines[-1] == "all passed" or lines[-1].endswith(" failed") or any("Traceback" in ln for ln in lines))
            if done:
                time.sleep(2)
                lines = [ln for ln in sh("cat /root/rh/log").splitlines() if not ln.startswith("__END")]
                print("\n".join(lines))
                return 0 if lines[-1] == "all passed" else 1
        print("the rehearsal did not end within half an hour")
        return 1
    finally:
        srv.shutdown()


if __name__ == "__main__":
    sys.exit(main())
