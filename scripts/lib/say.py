"""How a helper behind `aerie` ends on an error: the one line every verb
prints, and the check of an answer for one.

The line is `[builderbot] ERROR: ` and the sentence, on stderr, and the
exit code is 1. The dashboard reads that prefix out of a relayed verb's
output and the suites assert it, so the bytes are written in one place.

Standard library only, and no network module among it: a helper that never
reaches the controller says what went wrong without loading http or ssl.
"""
import sys
from typing import NoReturn


def die(msg) -> NoReturn:
    """The error line for msg on stderr, then exit code 1. It never returns."""
    sys.stderr.write(f"[builderbot] ERROR: {msg}\n")
    sys.exit(1)


def need(answer):
    """An answer from the controller's API or a dashboard module, handed
    back when it is good. A dict with a truthy "error" ends the helper on
    that error."""
    if isinstance(answer, dict) and answer.get("error"):
        die(answer["error"])
    return answer
