"""codemap.affected never plans a lab suite: a lab suite needs a real
service and is run by name, so whichever road reaches it, the drawn names
or the covered run, it leaves the plan. A function nearly every suite
reaches is planned by the suites that run it most, and a
covered run's counts of a suite replace the ones before (coverage_ingest)."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))
import codemap  # noqa: E402


def index():
    page = "scripts/dashboard/tab-x.js"
    fn = {"file": page, "name": "send", "line": 1, "end": 3}
    return {
        "files": {page: {"lang": "js", "defs": [fn],
                         "draws": [{"what": "/api/thing", "kind": "path", "line": 2}]}},
        "defs": [fn],
        "calls": [],
        "draws": [{"file": "scripts/dashboard/test/cards.mjs", "what": "/api/thing", "kind": "path", "line": 9},
                  {"file": "scripts/dashboard/test/lab-node.mjs", "what": "/api/thing", "kind": "path", "line": 9}],
    }, fn


class Affected(unittest.TestCase):
    def test_a_drawn_name_plans_its_suites_but_never_a_lab_one(self):
        idx, _ = index()
        suites, _, _, _ = codemap.affected(idx, None, {"scripts/dashboard/tab-x.js": [(2, 2)]})
        self.assertIn("cards", suites)
        self.assertNotIn("lab-node", suites)

    def test_a_covered_run_that_saw_a_lab_suite_does_not_plan_it(self):
        idx, fn = index()
        cov = {"suites": {"lab-node": {codemap.fid(fn): 3}, "cards": {codemap.fid(fn): 1}}}
        suites, _, _, _ = codemap.affected(idx, cov, {"scripts/dashboard/tab-x.js": [(2, 2)]})
        self.assertIn("cards", suites)
        self.assertNotIn("lab-node", suites)

    def test_a_function_nearly_every_suite_reaches_plans_those_that_run_it_most(self):
        idx, fn = index()
        many = {f"s{i:02d}": i + 1 for i in range(20)}
        cov = {"suites": {name: {codemap.fid(fn): n} for name, n in many.items()}}
        suites, notes, _, _ = codemap.affected(idx, cov, {"scripts/dashboard/tab-x.js": [(2, 2)]})
        took = sorted(s for s in suites if s.startswith("s"))
        self.assertEqual(took, [f"s{i:02d}" for i in range(20 - codemap.MOST_TAKE, 20)])
        self.assertTrue(any("reached by 20 of 20 suites" in n for n in notes), notes)

    def test_one_a_few_suites_reach_plans_every_one_of_them(self):
        idx, fn = index()
        cov = {"suites": {f"s{i:02d}": ({codemap.fid(fn): 1} if i < 14 else {}) for i in range(40)}}
        suites, _, _, _ = codemap.affected(idx, cov, {"scripts/dashboard/tab-x.js": [(2, 2)]})
        self.assertEqual(len([s for s in suites if s.startswith("s")]), 14)


class Ingest(unittest.TestCase):
    def test_a_suite_counted_again_keeps_this_run_alone_and_one_not_counted_keeps_its_own(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        idx = {"defs": [], "files": {}}
        def run(n, **suites):
            files = []
            for i, (suite, counts) in enumerate(suites.items()):
                for j, part in enumerate(counts):
                    f = os.path.join(root, f"r{n}-{i}-{j}.json")
                    with open(f, "w") as w:
                        json.dump({"suite": suite, "counts": part}, w)
                    files.append(f)
            return codemap.coverage_ingest(root, idx, files)
        run(1, cards=[{"old.js:gone#1": 4}], roles=[{"r.js:x#1": 1}])
        cov = run(2, cards=[{"page.js:draw#1": 2}, {"page.js:draw#1": 3}])
        self.assertEqual(cov["suites"]["cards"], {"page.js:draw#1": 5})
        self.assertEqual(cov["suites"]["roles"], {"r.js:x#1": 1})


if __name__ == "__main__":
    unittest.main()
