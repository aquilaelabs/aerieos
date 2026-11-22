"""aerie design edit runs on the machine the session is on, and a node's
bundle carries scripts/lib and a few of scripts/dashboard's modules, not
design.py (B934: it ended in No module named 'design'). Every module the
design verbs import from beside the dashboard is one the bundle carries, and
the names a rule is found by read the same from records.py as design.py
gives them."""
import ast
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import design  # noqa: E402
import records  # noqa: E402
import workspace  # noqa: E402

LIB = os.path.join(HERE, "..", "..", "lib")
DASH = os.path.join(HERE, "..")


class DesignEditOnANode(unittest.TestCase):
    def test_every_dashboard_module_it_imports_rides_in_the_bundle(self):
        tree = ast.parse(open(os.path.join(LIB, "design-verbs.py"), encoding="utf-8").read())
        names = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                names |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module:
                names.add(n.module.split(".")[0])
        theirs = {m for m in names if os.path.isfile(os.path.join(DASH, m + ".py"))}
        carried = {os.path.basename(p)[:-3] for p in workspace.BUNDLE_PARTS if p.startswith("scripts/dashboard/") and p.endswith(".py")}
        self.assertTrue(theirs, "it reads records from beside the dashboard")
        self.assertEqual(theirs - carried, set(), "imported from scripts/dashboard and missing from a node's bundle")

    def test_a_rule_is_named_as_the_design_names_it(self):
        rec = {"language": {"themes": [{"name": "Default", "rules": [{"name": "color"}]},
                                       {"name": "Nostromo", "rules": [{"name": "hull"}]}]},
               "pages": [{"id": 3, "name": "A dialog", "rules": [{"name": "layout"}]},
                         {"id": 4, "name": "x", "key": "the-dashboard/library", "rules": [{"name": "row"}]}]}
        self.assertEqual([n for n, _r, _h in records.design_rules(rec)],
                         ["color", "nostromo/hull", "a-dialog/layout", "the-dashboard/library/row"])
        self.assertIs(design.scoped_rules, records.design_rules)
        self.assertIs(design.page_key, records.design_page_key)


if __name__ == "__main__":
    unittest.main()
