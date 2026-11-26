"""One wording for each refusal every module says (R287 step 2): a missing
space is 'not a space' and a missing account 'not an account', each written
once in refusals.py, and no module spells either another way or writes the
sentence out again."""
import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import refusals  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
# The other ways each was said, as a string a module returns or raises.
OTHER = re.compile(r"""["'](unknown space|no such space|no such project|unknown project|no such account|unknown account|no such user)(["']|: )""")
SAID = re.compile(r"""["'](not a space|not an account)(: )?["']""")


class SaidOnce(unittest.TestCase):
    def modules(self):
        return [p for p in sorted(HERE.glob("*.py")) if p.name != "refusals.py"]

    def test_no_module_says_a_missing_space_or_account_another_way(self):
        bad = [f"{p.name}:{n}: {m.group(0)}" for p in self.modules()
               for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) for m in [OTHER.search(line)] if m]
        self.assertEqual(bad, [], "say refusals.NO_SPACE or refusals.NO_ACCOUNT")

    def test_the_sentence_is_written_once(self):
        bad = [f"{p.name}:{n}" for p in self.modules()
               for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
               if SAID.search(line) and not line.lstrip().startswith("#")]
        self.assertEqual(bad, [], "use refusals.NO_SPACE, NO_ACCOUNT, no_space() or no_account()")

    def test_a_name_is_said_after_it(self):
        self.assertEqual((refusals.no_space(), refusals.no_space("web")), ("not a space", "not a space: web"))
        self.assertEqual(refusals.no_account("pat"), "not an account: pat")


if __name__ == "__main__":
    unittest.main()
