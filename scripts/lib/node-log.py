"""Behind `aerie logs --node NAME [--agent|--runner|--terminal]` (cmd_logs in bb): a
MACHINE's own log, read through the controller, which decides whether the
asking session may see it.

BB_LOG_NODE is the node, BB_LOG_STREAM which of its logs, and BB_LOG_LINES
how many lines. The auth header is bbapi's own (BB_AUTH_HEADER, from api_py
in aerie).
"""
import os
import sys

import bbapi
from say import need


d = bbapi.call("/api/nodelog",
               {"node": os.environ["BB_LOG_NODE"],
                "stream": os.environ["BB_LOG_STREAM"],
                "lines": int(os.environ["BB_LOG_LINES"])},
               timeout=180)
need(d)
sys.stdout.write(d.get("out") or "")
if d.get("state") and d["state"] != "succeeded":
    sys.exit(f"[builderbot] ERROR: the read {d['state']} on the node")
