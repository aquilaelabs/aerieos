"""Behind `aerie design` (cmd_design in bb): a project's design language and
its pages, through the controller's API as the caller (design.py on the
dashboard's side), which is where the words are made.

The first argument is the verb: nothing or `list` prints the language in a
line and the pages; `show` prints the prompt for the language, or for one
page named by its id or its name; `file` prints docs/design-language.md as
the notebook would write it, for `aerie design file > docs/design-language.md`,
and `file --from FILE` the same from a record given (what `json` prints,
edited) rather than the saved one, so a branch writes it from its own design;
`json` prints the record (language, pages, and the presets they are drawn
from: every kind, template, scheme and choice by key); `schema` prints the
record's shape with every limit (B342); `save FILE` (or `-`
for stdin) writes a record of that shape back, whole, which is how a
session asked to put a design language into the notebook does it. A page
without an id is new; one with its id replaces that page; one left out is
removed. `edit NAME --text FILE` (or `--append FILE`, either `-` for stdin)
changes one rule's text (a design rule by its name, a theme's or a page's
as `aerie design show` names it, `a-dialog/layout`) or one page's notes,
and saves the record whole as `save` does, printing what changed. `--file`
on `edit` and `save` writes docs/design-language.md into the repository's
tree from what was saved. BB_DESIGN_AUTH is the auth header and
BB_DESIGN_PROJECT the project.
"""
import difflib
import json
import os
import subprocess
import sys
import urllib.parse

import bbapi
from say import die

import dash  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dashboard"))
import records  # noqa: E402

# `--format json|yaml|markdown` on list or show (R167): the record `json`
# prints, in that form; a design is one record of its pages and themes.
fmt, argv = dash.format_flag(sys.argv[1:])
verb = argv[0] if argv else "list"
auth = os.environ["BB_DESIGN_AUTH"]
proj = os.environ["BB_DESIGN_PROJECT"]
USAGE = ("usage: aerie design [list | show [ID|NAME] | file [--from FILE] | json | schema | save FILE [--file] | "
         "edit NAME --text FILE|--append FILE [--file]]")
# --file on save and edit: docs/design-language.md written into the tree.
write_file = "--file" in argv
argv = [a for a in argv if a != "--file"]


if verb == "save" and (len(argv) < 2 or argv[1] in ("-h", "--help")):
    # Help, not a file called -h (B342): the shape and every limit.
    r = bbapi.call("/api/design?project=" + urllib.parse.quote(proj) + "&show=schema", auth=auth)
    print("aerie design save FILE (or - for stdin): a JSON file of this shape, saved whole")
    print()
    print(r.get("text", "") if isinstance(r, dict) else "")
    raise SystemExit(0 if len(argv) > 1 else 1)
def read_record(src):
    """A record of the shape aerie design json prints, from a file or stdin."""
    try:
        rec = json.loads(sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read())
    except (OSError, ValueError) as e:
        die(f"could not read {src}: {e}")
    if not isinstance(rec, dict):
        die("the record is an object with language and pages")
    return rec


if verb == "file" and len(argv) > 1:
    # From a record given rather than the saved one (B227): a branch writes
    # the file from its own design, not from what other branches saved.
    if argv[1] != "--from" or len(argv) != 3:
        die("usage: aerie design file [--from FILE]")
    rec = read_record(argv[2])
    r = bbapi.call("/api/design", {"action": "render", "project": proj,
                                   "language": rec.get("language") or {},
                                   "pages": rec.get("pages") or []}, auth=auth)
    if not isinstance(r, dict):
        die("the controller answered something that is not a design")
    if r.get("error"):
        die(r["error"])
    text = str(r.get("text") or "")
    sys.stdout.write(text + ("" if text.endswith("\n") else "\n"))
    raise SystemExit(0)

def tree_file():
    """This repository's docs/design-language.md, None outside a repository."""
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                             check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return os.path.join(top, "docs", "design-language.md")


def saved_file_text():
    """docs/design-language.md as the saved design writes it."""
    r = bbapi.call("/api/design?project=" + urllib.parse.quote(proj) + "&show=file", auth=auth)
    if not isinstance(r, dict) or r.get("error"):
        die((r or {}).get("error") if isinstance(r, dict) else "the controller answered something that is not a design")
    text = str(r.get("text") or "")
    return text + ("" if text.endswith("\n") else "\n")


def design_file():
    """docs/design-language.md written into this repository's tree from the
    saved design, as `aerie design file > docs/design-language.md` does; or,
    without --file, a line when the tree's file is not what it writes."""
    path = tree_file()
    if not write_file:
        if path and os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as f:
                if f.read() != saved_file_text():
                    print(f"{os.path.relpath(path)} in this tree is not what the saved design writes: "
                          "--file writes it (aerie design file prints it)")
        return
    if not path:
        die("--file writes into a repository's tree, and this is not inside one")
    text = saved_file_text()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {os.path.relpath(path)} from the saved design")


def save(rec, said):
    """Save a whole record, saying `said` once it lands."""
    r = bbapi.call("/api/design", {"action": "save", "project": proj,
                                   "language": rec.get("language") or {},
                                   "pages": rec.get("pages") or []}, auth=auth)
    if not isinstance(r, dict):
        die("the controller answered something that is not a design")
    if r.get("error"):
        die(r["error"])
    if r.get("held"):
        print(f"held for the operator's approval on {proj}'s notebook (Agents may: Add to the design is ask): "
              f"{r['held'].get('summary', '')}")
        raise SystemExit(0)
    print(said(r))
    design_file()
    raise SystemExit(0)


if verb == "save":
    rec = read_record(argv[1])
    save(rec, lambda r: (f"saved {proj}'s design: {len(r.get('pages') or [])} page"
                         f"{'' if len(r.get('pages') or []) == 1 else 's'}; the notebook's Design view shows it"
                         + ("" if write_file else ", and aerie design file prints docs/design-language.md from it")))

if verb == "edit":
    # One rule or one page's notes changed in place, the record saved whole.
    if len(argv) != 4 or argv[2] not in ("--text", "--append"):
        die("usage: aerie design edit NAME --text FILE|--append FILE [--file] (FILE or - for stdin)")
    name, how, src = argv[1], argv[2], argv[3]
    try:
        new = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    except OSError as e:
        die(f"could not read {src}: {e}")
    new = new.strip("\n")
    if not new.strip():
        die(f"{src} is empty; aerie design save writes a record with the rule left out")
    r = bbapi.call("/api/design?project=" + urllib.parse.quote(proj) + "&show=json", auth=auth)
    if not isinstance(r, dict) or r.get("error"):
        die((r or {}).get("error") if isinstance(r, dict) else "the controller answered something that is not a design")
    rec = json.loads(str(r.get("text") or "{}"))
    rules = {n: rule for n, rule, _ in records.design_rules(rec)}
    pages = {}
    for p in rec.get("pages") or []:
        pages.setdefault(records.design_page_key(p), p)
        pages.setdefault(str(p.get("name") or ""), p)
    if name in rules:
        holder, key, what = rules[name], "text", f"the rule {name}"
    elif name in pages:
        holder, key, what = pages[name], "notes", f"the page {name}'s notes"
    else:
        near = difflib.get_close_matches(name, [*rules, *[k for k in pages if k]], n=5, cutoff=0.6)
        die(f"the design has no rule or page called {name}" + (f"; the nearest: {', '.join(near)}" if near else "")
             + "; aerie design lists them")
    was = str(holder.get(key) or "")
    holder[key] = (was.rstrip("\n") + "\n\n" + new) if how == "--append" and was.strip() else new
    if holder[key] == was:
        print(f"{what} already reads so; nothing saved")
        raise SystemExit(0)
    diff = list(difflib.unified_diff(was.splitlines(), holder[key].splitlines(), "before", "after", lineterm="", n=1))
    save(rec, lambda _r: "\n".join([f"saved {what} in {proj}'s design:", *diff[2:]]))

if verb == "show":
    which = " ".join(argv[1:]).strip() or "language"
elif verb in ("list", "file", "json", "schema"):
    which = "json" if fmt != "text" and verb in ("list", "json") else verb
elif verb in ("-h", "--help"):
    print(USAGE)
    raise SystemExit(0)
else:
    die(USAGE)

r = bbapi.call("/api/design?project=" + urllib.parse.quote(proj) + "&show=" + urllib.parse.quote(which), auth=auth)
if not isinstance(r, dict):
    die("the controller answered something that is not a design")
if r.get("error"):
    die(r["error"])
text = str(r.get("text") or "")
if fmt not in ("text", "json") and which == "json":
    rec = json.loads(text)
    pages = rec.get("pages") if isinstance(rec, dict) and isinstance(rec.get("pages"), list) else [rec]
    text = records.dump(records.document("design", pages, proj), fmt)
sys.stdout.write(text + ("" if text.endswith("\n") else "\n"))
