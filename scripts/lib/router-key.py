"""Behind `aerie router-key` (R144): the model router's address, this project's
own key and the models it offers, for an Any model session at its start
(bb-tty's launcher writes OpenCode's config from it). Prints the JSON the
controller answers, {} where no router allows the project.

BB_PROJECT is the project. The auth header is bbapi's own (BB_AUTH_HEADER,
from aerie).
"""
import json
import os
import sys
import urllib.parse

import bbapi

proj = os.environ.get("BB_PROJECT", "")
if not proj:
    sys.exit("[builderbot] ERROR: no space: run it inside one, or set BB_PROJECT")
d = bbapi.call("/api/router-key?project=" + urllib.parse.quote(proj), timeout=20)
print(json.dumps(d))
