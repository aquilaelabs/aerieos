"""Migration 0039: an item finished by its last step under an older build,
logged with its words alone or with an empty row, has its row written into
its "done" event once, and reads as roadmap.py's rebuilding from the log
read it on 27 Nov: FROZEN. A row kept whole is left as it is."""
import copy
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import roadmap  # noqa: E402

STORE = json.loads(r'''{"projects": {"p": []}, "history": {"p": [{"act": "done", "id": 5, "text": "Ship the thing", "at": 900, "by": "claude"}, {"act": "done-step", "id": 5, "step": 2, "at": 890, "by": "claude", "text": "third"}, {"act": "target-step", "id": 5, "step": 1, "target": "0.7.0", "at": 880, "by": "you"}, {"act": "info", "id": 5, "text": "the files and the plan", "at": 870, "by": "you"}, {"act": "edit", "id": 5, "text": "Ship the thing, reworded", "at": 860, "by": "you"}, {"act": "info-step", "id": 5, "step": 1, "text": "how", "at": 850, "by": "you"}, {"act": "edit-step", "id": 5, "step": 0, "text": "first, reworded", "at": 840, "by": "you"}, {"act": "done-step", "id": 5, "step": 0, "at": 830, "by": "claude"}, {"act": "add-step", "id": 5, "step": 2, "text": "third", "at": 820, "by": "claude"}, {"act": "add", "id": 5, "text": "Ship the thing", "steps": 2, "at": 800, "by": "you", "target": "0.6.0"}, {"act": "done", "id": 7, "text": "An empty row", "at": 700, "by": "you", "row": {"id": 7, "text": "An empty row", "steps": []}}, {"act": "add-step", "id": 7, "step": 0, "text": "only", "at": 650, "by": "you"}, {"act": "add", "id": 7, "text": "An empty row", "at": 600, "by": "you"}, {"act": "done", "id": 6, "text": "Kept whole", "at": 500, "by": "you", "row": {"id": 6, "text": "Kept whole", "steps": [{"text": "a", "sent": 0}]}}, {"act": "add", "id": 6, "text": "Kept whole", "steps": 1, "at": 400, "by": "you"}]}}''')
# roadmap.finished("p") on 27 Nov, with the rebuilding from the log in it.
FROZEN = json.loads(r'''[{"id": 5, "text": "Ship the thing, reworded", "steps": [{"text": "first, reworded", "sent": 0, "done": 830}, {"text": "step 2 (its words were not kept)", "sent": 0, "info": "how", "target": "0.7.0"}, {"text": "third", "sent": 0, "done": 890}], "target": "0.6.0", "info": "the files and the plan", "done_at": 900, "done_by": "claude", "reopenable": true}, {"id": 7, "text": "An empty row", "steps": [{"text": "only", "sent": 0}], "done_at": 700, "done_by": "you", "reopenable": true}, {"id": 6, "text": "Kept whole", "steps": [{"text": "a", "sent": 0}], "done_at": 500, "done_by": "you", "reopenable": true}]''')


def write_json(path, data, mode=0o644):
    del mode
    with open(path, "w") as f:
        json.dump(data, f)


class FinishedRowsKept(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        self.f = self.d / "roadmap.json"
        self.f.write_text(json.dumps(copy.deepcopy(STORE)))
        os.chmod(self.f, 0o600)
        roadmap.configure(write_json=write_json, state=str(self.d))
        self.run_it = lambda: importlib.import_module("statemigrations.0039_finished_rows_kept").run({"state": str(self.d)})

    def test_each_finished_item_reads_as_it_was_rebuilt(self):
        self.run_it()
        self.assertEqual(roadmap.finished("p"), FROZEN)
        self.assertEqual(self.f.stat().st_mode & 0o777, 0o600)
        done = {e["id"]: e for e in json.loads(self.f.read_text())["history"]["p"] if e["act"] == "done"}
        self.assertTrue(all(done[i]["row"]["steps"] for i in (5, 6, 7)), "each done event holds its steps")

    def test_it_is_idempotent_and_leaves_a_kept_row_alone(self):
        self.run_it()
        once = self.f.read_text()
        self.run_it()
        self.assertEqual(self.f.read_text(), once)
        six = next(e for e in json.loads(once)["history"]["p"] if e["act"] == "done" and e["id"] == 6)
        self.assertEqual(six["row"], STORE["history"]["p"][13]["row"])


if __name__ == "__main__":
    unittest.main()
