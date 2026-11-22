"""The lab's own record (R3 step 8): what each lab suite walked, on what,
and when, written by the run that walked it.

The vetted lines beside the systems a node can be (systems.py) carried
dates typed by hand, and the code they vouch for moved on under them. A lab
suite now prints one line for each subject it walked with nothing failed
(lib.mjs record(): a system for lab-systems, a git host for lab-forge), and
`aerie tests lab` hands the run's output here: each line is kept in
lab-record.json beside this file, dated, with the build it ran against.
The file is the tree's, committed with the work and shipped in the image,
so a system's vetted line is read from the newest walk on record and one
with no walk on record is not vetted.

    labrecord.py add --from FILE --build VERSION [--at YYYY-MM-DD] [--file PATH]
    labrecord.py show [--file PATH]
"""
import datetime
import json
import os
import re
import sys

FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lab-record.json")
FORMAT = 1
KEEP = 3                      # walks kept of each suite and subject, newest first
LINE = re.compile(r"RECORD\s+suite=([a-z0-9-]{1,40})\s+subject=([A-Za-z0-9._-]{1,60})\s+said=(.{0,200})")
_FIELDS = ("suite", "subject", "said", "at", "build")


def rows(path=FILE):
    """Every walk on record, newest first; [] for a file that is missing,
    spoiled or of a format this build does not read."""
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(d, dict) or d.get("format") != FORMAT or not isinstance(d.get("walks"), list):
        return []
    got = [r for r in d["walks"] if isinstance(r, dict) and all(isinstance(r.get(k), str) for k in _FIELDS)]
    return sorted(got, key=lambda r: r["at"], reverse=True)


def newest(match, path=FILE):
    """The newest walk `match(row)` is true of, or None."""
    return next((r for r in rows(path) if match(r)), None)


def parse(text):
    """[(suite, subject, said)] for each line a suite printed with record()."""
    out = []
    for line in str(text or "").splitlines():
        m = LINE.search(line)
        if m:
            out.append((m.group(1), m.group(2), " ".join(m.group(3).split())))
    return out


def add(found, build, at="", path=FILE):
    """The walks `found` (parse()'s) kept as of `at` (today when not said)
    against `build`: the newest KEEP of each suite and subject stay. The
    rows it added."""
    at = at or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", at):
        raise ValueError(f"not a date: {at}")
    new = [{"suite": s, "subject": sub, "said": said, "at": at, "build": str(build or "")} for s, sub, said in found]
    if not new:
        return []
    have = [r for r in rows(path) if not any(all(r[k] == n[k] for k in ("suite", "subject", "at", "build")) for n in new)]
    kept, count = [], {}
    for r in sorted(new + have, key=lambda r: r["at"], reverse=True):
        k = (r["suite"], r["subject"])
        count[k] = count.get(k, 0) + 1
        if count[k] <= KEEP:
            kept.append(r)
    kept.sort(key=lambda r: (r["suite"], r["subject"], r["at"]))
    with open(path + ".new", "w", encoding="utf-8") as f:
        json.dump({"format": FORMAT, "walks": kept}, f, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(path + ".new", path)
    return new


def main(argv):
    def opt(name, default=""):
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default
    path = opt("--file", FILE)
    if argv[:1] == ["add"]:
        src = opt("--from")
        with (open(src, encoding="utf-8", errors="replace") if src else sys.stdin) as f:
            found = parse(f.read())
        new = add(found, opt("--build"), opt("--at"), path)
        if new:
            print(f"lab record: {len(new)} walk(s) written to {os.path.relpath(path)}, dated {new[0]['at']}: "
                  + ", ".join(f"{r['suite']} {r['subject']}" for r in new) + "; commit it with the work")
        else:
            print("lab record: no suite walked a subject whole, so nothing is written")
        return 0
    if argv[:1] == ["show"]:
        for r in rows(path):
            print(f"{r['at']}  {r['suite']:<14} {r['subject']:<18} {r['said']}" + (f"  (build {r['build']})" if r["build"] else ""))
        return 0
    print(__doc__.strip().splitlines()[-2].strip() + "\n" + __doc__.strip().splitlines()[-1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
