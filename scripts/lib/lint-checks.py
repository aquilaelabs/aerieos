"""Behind three of `aerie lint`'s own checks (cmd_lint in bb): whether this
project's workflows pin its node's runner, whether an XML file is
well-formed, and whether the container's settings agree across compose,
.env.example, the Unraid template and docs/reference.md.

The first argument is the check. `runner` takes nodes.py's path and the
project's node, with DASHBOARD_STATE saying where the store is; `xml`
takes the file; `settings` takes nothing and reads the four files from the
current directory. Each prints its lines and exits non-zero on a failure.
"""
import os
import pathlib
import re
import sys
# The XML read here is this repository's own (the Unraid template, the
# workflows): no input from outside, so defusedxml would guard nothing.
import xml.dom.minidom  # nosemgrep: python.lang.security.use-defused-xml.use-defused-xml
import xml.etree.ElementTree as ET  # nosemgrep: python.lang.security.use-defused-xml.use-defused-xml
import xml.parsers.expat  # nosemgrep: python.lang.security.use-defused-xml.use-defused-xml

import dash

verb, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])


def newest_release(tags):
    """The newest of these vX.Y.Z and vX.Y.Z-NAME.N tags: by its numbers, a
    release above every pre-release that leads to it. git's own version
    sort puts v0.9.0-dev.5341 above v0.9.0, so once 0.9.0 was tagged the
    checks that compare against the newest release would have kept reading
    a dev tag (the audit of 13 Nov). "" when none of them is a version."""
    def key(t):
        m = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)(?:-([a-z][a-z0-9]*)\.(\d+))?", t)
        if not m:
            return None
        x, y, z, name, n = m.groups()
        return (int(x), int(y), int(z), 0 if name else 1, int(n or 0))
    known = [(key(t), t) for t in tags if key(t) is not None]
    return max(known)[1] if known else ""


def runner():
    nodes = dash.load("nodes", dash.beside(args[0]))
    try:
        nodes.db.open_readonly(os.environ["DASHBOARD_STATE"])
        label = nodes.node_runner_label(args[1])
    except Exception:
        label = ""
    if label:
        # runs-on lines that name self-hosted and NOT this node. A hosted runner
        # (ubuntu-latest) is a deliberate choice and none of this applies to it.
        loose = []
        for f in sorted(pathlib.Path(".github/workflows").glob("*.y*ml")):
            for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                m = re.match(r"\s*runs-on:\s*(.+?)\s*$", line)
                if not m:
                    continue
                v = m.group(1)
                # An expression is a deliberate choice of runner made at
                # dispatch (the smoke test does exactly this), so it is not a
                # workflow that forgot to pin.
                if "self-hosted" in v and label not in v and "${{" not in v:
                    loose.append(f"{f.name}:{i}")
        if loose:
            print(f"  [note] this project's node is {label}, and "
                  f"{len(loose)} workflow job{'s' if len(loose) > 1 else ''} "
                  f"do{'' if len(loose) > 1 else 'es'} not pin it "
                  f"({', '.join(loose[:6])}{', …' if len(loose) > 6 else ''})")
            print("         their runs-on matches every AerieOS runner, so GitHub sends the")
            print("         job to whichever is idle, which may be a machine without the")
            print("         toolchain. To land on this space's node:")
            print(f"           runs-on: [self-hosted, {label}]")


# A hosted runner named by a moving label: GitHub repoints ubuntu-latest at a
# new release on its own date (Ubuntu 26 from 19 Oct 2026), and a workflow
# that built yesterday fails tomorrow with nothing in the repository changed.
# A pinned image moves only when somebody moves it, in a commit.
PINNED = {"ubuntu": "ubuntu-24.04", "windows": "windows-2025", "macos": "macos-15"}


def hosted():
    strict = "--strict" in args
    found = []
    for f in sorted(pathlib.Path(".github/workflows").glob("*.y*ml")):
        for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
            m = re.match(r"\s*runs-on:\s*(.+?)\s*(#.*)?$", line)
            if not m or "${{" in m.group(1):
                continue
            for os_ in re.findall(r"\b(ubuntu|windows|macos)-latest\b", m.group(1)):
                found.append((f"{f.name}:{i}", f"{os_}-latest", PINNED[os_]))
    if not found:
        print("  [ok]   every hosted job names a pinned image")
        sys.exit(0)
    tag = "[FAIL]" if strict else "[note]"
    for where, label, pin in found:
        print(f"  {tag} {where} runs on {label}, which GitHub moves to a new release on its own date;"
              f" runs-on: {pin} moves only when a commit moves it")
    sys.exit(1 if strict else 0)


def pinned():
    """Every action a workflow uses is named by its commit:
    `uses: owner/action@v4` runs whatever its publisher points v4 at
    that day, in jobs that hold the release key and may write packages and
    releases. A note in any project, a failure in this one (--strict)."""
    strict = "--strict" in args
    found = []
    for f in sorted(pathlib.Path(".github/workflows").glob("*.y*ml")):
        for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
            m = re.match(r"\s*-?\s*uses:\s*([^\s#]+)", line)
            if not m or m.group(1).startswith(("./", "docker://")):
                continue
            name, _, ref = m.group(1).partition("@")
            if not re.fullmatch(r"[0-9a-f]{40}", ref):
                found.append((f"{f.name}:{i}", name, ref or "no version"))
    if not found:
        print("  [ok]   every action is pinned by its commit")
        sys.exit(0)
    tag = "[FAIL]" if strict else "[note]"
    for where, name, ref in found:
        print(f"  {tag} {where} uses {name} at {ref}, which its publisher can move;"
              f" name the commit (uses: {name}@<40 hex>   # the version) so it moves only in a commit here")
    sys.exit(1 if strict else 0)


def xml_():
    try:
        xml.dom.minidom.parse(args[0])
    except xml.parsers.expat.ExpatError as e:
        raise SystemExit(f'  {e}') from None


def layout():
    """docs/layout.md names every tracked file: a row is a path, a
    directory (which covers what is under it only when nothing beneath it
    is listed) or a glob, and a tracked file no row names fails. A tree
    that grows a module the page does not name is a newcomer's dead end."""
    import fnmatch
    import subprocess
    try:
        lay = open("docs/layout.md", encoding="utf-8").read().split("```")[1].splitlines()
    except (OSError, IndexError):
        print("  [FAIL] docs/layout.md has no code block to read")
        return 1
    rows, stack = [], []
    for ln in lay:
        m = re.match(r"^(\s*)([A-Za-z0-9_.\-/*]+)", ln)
        if not m or not ln.strip():
            continue
        ind, tok = len(m.group(1)), m.group(2)
        while stack and stack[-1][0] >= ind:
            stack.pop()
        path = (stack[-1][1] if stack else "") + tok
        if tok.endswith("/"):
            stack.append((ind, path))
        rows.append(path)
    leaf_dirs = {r for r in rows if r.endswith("/") and not any(x != r and x.startswith(r) for x in rows)}
    tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=False).stdout.split()
    if not tracked:
        print("  [skip] not a git checkout, so nothing to hold the page to")
        return 0

    def named(f):
        return any(r == f or (r in leaf_dirs and f.startswith(r)) or ("*" in r and fnmatch.fnmatch(f, r))
                   for r in rows)
    miss = [f for f in tracked if not named(f)]
    if miss:
        print(f"  [FAIL] {len(miss)} tracked file(s) docs/layout.md does not name: " + " ".join(miss[:12])
              + (" ..." if len(miss) > 12 else ""))
        return 1
    print(f"  [ok]   docs/layout.md names every one of the {len(tracked)} tracked files")
    return 0


def settings():
    compose = open("docker-compose.yml").read()
    # The builderbot service only: the lab's services carry their own.
    svc = compose.split("\n  aerie-workshop:", 1)[1]
    svc = re.split(r"\n  [a-z][a-z0-9_-]*:\s*\n", svc, maxsplit=1)[0]
    env = {}
    for m in re.finditer(r"^\s+([A-Z][A-Z0-9_]+):\s*\$\{([A-Z][A-Z0-9_]+)(?::?-([^}]*))?\}", svc, re.M):
        if m.group(1) == m.group(2):
            env[m.group(1)] = m.group(3) or ""
    example = {}
    for ln in open(".env.example"):
        m = re.match(r"^#?\s*([A-Z][A-Z0-9_]+)=(.*)$", ln.rstrip("\n"))
        if m:
            example[m.group(1)] = m.group(2).strip()
    root = ET.parse("platforms/unraid/aerie-workshop.xml").getroot()
    tmpl = {c.get("Target"): c.get("Default") or "" for c in root.iter("Config") if c.get("Type") == "Variable"}
    paths = {c.get("Target"): c.get("Default") or "" for c in root.iter("Config") if c.get("Type") == "Path"}
    # A row may name two at once, `PUID` / `PGID` | `99` / `100`, paired in order.
    readme = {}
    for m in re.finditer(r"^\|\s*((?:`[A-Z][A-Z0-9_]+`(?:\s*/\s*)?)+)\s*\|\s*([^|]*)\|", open("docs/reference.md").read(), re.M):
        names = re.findall(r"`([A-Z][A-Z0-9_]+)`", m.group(1))
        defs = [x.strip().strip("`") for x in m.group(2).split(" / ")] if len(names) > 1 else [m.group(2).strip().strip("`")]
        for i, n in enumerate(names):
            readme[n] = defs[i] if i < len(defs) else ""
    bad = []
    for v, d in sorted(env.items()):
        if v not in example:
            bad.append(f"{v} is passed by compose and missing from .env.example")
        elif example[v] != d:
            bad.append(f"{v}: compose defaults to {d!r}, .env.example says {example[v]!r}")
        if v not in tmpl:
            bad.append(f"{v} is passed by compose and missing from the Unraid template")
        elif tmpl[v] != d:
            bad.append(f"{v}: compose defaults to {d!r}, the Unraid template to {tmpl[v]!r}")
        if v not in readme:
            bad.append(f"{v} is passed by compose and missing from docs/reference.md")
        elif readme[v] != d and not (d == "" and readme[v] in ("*(none)*", "*(empty)*")):
            bad.append(f"{v}: compose defaults to {d!r}, docs/reference.md to {readme[v]!r}")
    for v in sorted(set(tmpl) - set(env)):
        bad.append(f"{v} is in the Unraid template and compose does not pass it")
    # A bare-metal install's env file: every setting compose passes is
    # in its template, at the same default, but those the template names as
    # the container's alone; and every name the template sets is in the
    # reference, as compose's are.
    bare = open("config/controller.env").read()
    bkeys = dict(re.findall(r"^([A-Z][A-Z0-9_]+)=(.*)$", bare, re.M))
    alone = re.search(r"Not here, the container's alone: ([A-Z_ ]+)", bare)
    alone = set(alone.group(1).split()) if alone else set()
    for v, d in sorted(env.items()):
        if v in alone:
            continue
        if v not in bkeys:
            bad.append(f"{v} is passed by compose and missing from config/controller.env (a bare-metal install's)")
        elif bkeys[v].strip('"') != d:
            bad.append(f"{v}: compose defaults to {d!r}, config/controller.env to {bkeys[v]!r}")
    for v in sorted(set(bkeys) - set(readme)):
        bad.append(f"{v} is in config/controller.env and missing from docs/reference.md")
    for target, d in sorted(paths.items()):
        m = re.search(r"^\s*#?\s*-\s*\"?(?:\$\{[A-Z_]+:-([^}]*)\}([^:\"]*)|([^:\"$ ]+)):" + re.escape(target) + r"(?::r[ow])?\"?\s*$",
                      svc, re.M)
        if not m:
            continue
        cd = (m.group(1) + m.group(2)) if m.group(1) is not None else m.group(3)
        if d and cd != d:
            bad.append(f"{target}: the Unraid template mounts {d!r}, compose {cd!r}")
    for b in bad:
        print(f"  [FAIL] {b}")
    if not bad:
        print(f"  [ok]   {len(env)} settings and {len(paths)} paths agree across compose, .env.example, the template, a bare-metal install's env file and the reference")
    sys.exit(1 if bad else 0)


def _words(text):
    return re.findall(r"[a-z0-9][a-z0-9'-]*", text.lower())


def _shingles(text, n=8):
    w = _words(text)
    return {" ".join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


# History in an instruction: a date, a bug or roadmap number of two digits
# or more (R4 and B7 are the examples the verbs are shown with), "bug 13",
# or an attribution to the operator. The why lives in docs/decisions.md
# and aerie rules show; the prompt carries the instruction.
HISTORY = re.compile(r"\b\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b"
                     r"|\b[BR]\d{2,4}\b|\b(?:bug|roadmap|issue) #?\d+\b|\(the operator,|\bthe operator, \d")
SHINGLE = 8


def channels():
    """CLAUDE.md describes the tree, the briefing the machine and the shipped
    rules the obligations: a sentence CLAUDE.md shares with the
    briefing or a shipped rule reaches every session twice, and history in
    either is paid for on every conversation."""
    bad = []
    claude = open("CLAUDE.md").read()
    brief = re.sub(r"<!--.*?-->", "", open("config/templates/briefing.md").read(), flags=re.S)
    # The tree being linted, not the copy of bb this runs from: on a node
    # that copy is the bundle, which carries no rules.py.
    sys.path.insert(0, os.path.join(os.getcwd(), "scripts", "dashboard"))
    import rules                                                    # noqa: E402
    sources = [("the briefing", brief)] + [(f"the shipped rule {r['name']}", r["text"])
                                           for r in rules.BUILTIN + rules.ALWAYS]
    said = {}
    for name, text in sources:
        for s in _shingles(text):
            said.setdefault(s, name)
    seen = set()
    for i, line in enumerate(claude.split("\n"), 1):
        for s in _shingles(line):
            if s in said and i not in seen:
                seen.add(i)
                bad.append(f"CLAUDE.md:{i} says what {said[s]} says: \"{s}...\"")
                break
    for path, text in (("CLAUDE.md", claude), ("config/templates/briefing.md", brief)):
        for i, line in enumerate(text.split("\n"), 1):
            m = HISTORY.search(line)
            if m:
                bad.append(f"{path}:{i} carries history in an instruction ({m.group(0)!r}): it belongs in docs/decisions.md or a rule's why")
    for b in bad:
        print(f"  [FAIL] {b}")
    if not bad:
        print("  [ok]   CLAUDE.md, the briefing and the shipped rules each say their own, with no history in the prompt")
    sys.exit(1 if bad else 0)


# What a release has run on somebody's /config: the database's schema
# files and the JSON stores' migrations. An install that ran one never runs
# it again, so an edit reaches only the installs that had not, and the two
# kinds then differ in a way no later migration can know about.
SHIPPED = ("scripts/dashboard/migrations", "scripts/dashboard/statemigrations")


def _state_floor():
    """stateversion.SUPPORTED_FROM, read off the file: a state migration
    numbered at or under it never runs, so it may leave the tree."""
    m = re.search(r"^SUPPORTED_FROM = (\d+)$", pathlib.Path("scripts/dashboard/stateversion.py").read_text(), re.M)
    return int(m.group(1)) if m else 0


def formats():
    """Every manifest kept for a pack format that the newest release
    tag carried is in the tree byte-for-byte: a manifest a release read is
    what later builds must still read, so the proof is never rewritten to
    fit a change. A new manifest, and a new format's folder, are free."""
    import subprocess

    def git(*a):
        return subprocess.run(["git", *a], capture_output=True, check=False)
    where = "scripts/dashboard/unit/packformat"
    tag = newest_release(git("tag", "-l", "v[0-9]*").stdout.decode().split())
    tags = [tag] if tag else []
    names = list(filter(None, git("ls-tree", "-r", "--name-only", tags[0], "--", where).stdout.decode().split("\n"))) if tags else []
    if not names:
        print("  [ok]   no release has carried a kept manifest yet")
        sys.exit(0)
    bad = []
    for path in names:
        try:
            now = pathlib.Path(path).read_bytes()
        except OSError:
            bad.append(f"{path} was kept in {tags[0]} and is gone: a format a release read is read for good")
            continue
        if now != git("show", f"{tags[0]}:{path}").stdout:
            bad.append(f"{path} was kept in {tags[0]} and has changed: a kept manifest is never edited; "
                       "what a change needs goes in a new format's folder")
    for b in bad:
        print(f"  [FAIL] {b}")
    if not bad:
        print(f"  [ok]   every one of the {len(names)} manifest(s) kept in {tags[0]} is unchanged")
    sys.exit(1 if bad else 0)


def shipped():
    """Every migration present at the newest release tag (v*) is in the tree
    byte-for-byte, but a state migration at or under the state floor, which no
    install this build starts on runs. No tag yet, nothing shipped: it
    passes, and says so."""
    import subprocess

    def git(*a):
        return subprocess.run(["git", *a], capture_output=True, check=False)
    tag = newest_release(git("tag", "-l", "v[0-9]*").stdout.decode().split())
    if not tag:
        print("  [ok]   no release tag yet, so no migration has shipped")
        sys.exit(0)
    bad = []
    # migrations/ is the schema every supported install has: a later
    # change to it is a numbered migration in statemigrations/, in the one
    # sequence with /config's.
    for f in sorted(pathlib.Path("scripts/dashboard/migrations").glob("*.sql")):
        if f.name[:4].isdigit() and int(f.name[:4]) > 10:
            bad.append(f"{f} is a new schema file: a change to the database is statemigrations/NNNN_name.sql, "
                       "numbered with the others")
    names = git("ls-tree", "-r", "--name-only", tag, "--", *SHIPPED).stdout.decode().split("\n")
    for path in filter(None, names):
        then = git("show", f"{tag}:{path}").stdout
        try:
            now = pathlib.Path(path).read_bytes()
        except OSError:
            num = pathlib.Path(path).name[:4]
            if path.startswith("scripts/dashboard/statemigrations/") and num.isdigit() and int(num) <= _state_floor():
                continue
            bad.append(f"{path} shipped in {tag} and is gone")
            continue
        if now != then:
            bad.append(f"{path} shipped in {tag} and has changed: a shipped migration is never edited; "
                       "put the change in a new one")
    # A patch carries no migration: migrations number in one sequence
    # across releases, and a 0.6.2 taking the next number would collide with
    # the one the 0.7.0 branch already holds. The branch's line is aerie version
    # line's (its git config, else a branch named for a version).
    br = git("rev-parse", "--abbrev-ref", "HEAD").stdout.decode().strip()
    ln = git("config", f"branch.{br}.bbline").stdout.decode().strip() if br and br != "HEAD" else ""
    if not re.fullmatch(r"\d+\.\d+\.\d+", ln):
        m = re.search(r"(?:^|/)v?(\d+\.\d+\.\d+)$", br or "")
        ln = m[1] if m else ""
    if ln and not ln.endswith(".0"):
        now = {str(f) for d in SHIPPED for f in pathlib.Path(d).glob("[0-9]*.*") if f.is_file()}
        added = sorted(now - set(filter(None, names)))
        for f in added:
            bad.append(f"{f} is new on {br}, which works toward the patch {ln}: a patch carries no migration, "
                       "so what it needs waits for the next minor's branch")
    for b in bad:
        print(f"  [FAIL] {b}")
    if not bad:
        print(f"  [ok]   every migration shipped in {tag} is unchanged"
              + (f", and none is new on the patch line {ln}" if ln and not ln.endswith(".0") else ""))
    sys.exit(1 if bad else 0)


def unraid():
    """The word Unraid stays where its XML files are the subject:
    the app template and its icon script, the VM XML and
    the module that writes it, the walkthrough of installing from the
    template, and any line that names one of those; everywhere else public
    a feature is said as what it is, never by comparison."""
    allowed = ("platforms/unraid/", "docs/unraid.md", "nodes/unraid-vm.xml", "scripts/dashboard/vmtemplate.py",
               "scripts/startup.d/05-unraid-icon.root.sh", "scripts/lib/lint-checks.py", "docs/design-language.md",
               "docs/sandbox-vm.md")      # the VM XML's walkthrough, host settings and all
    names = ("template", "unraid-vm.xml", "unraid.md", "aerie-workshop.xml", "unraid_", "unraid-", "\"unraid\"", "'unraid'", "net.unraid.", "walkthrough")
    import subprocess
    files = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=False).stdout.split("\n")
    bad = []
    for f in files:
        if not f or f.startswith(allowed) or not f.endswith((".md", ".js", ".py", ".sh", ".html", ".yml", ".yaml", ".txt", ".json", ".toml", ".env", ".example")):
            continue
        try:
            lines = pathlib.Path(f).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, ln in enumerate(lines, 1):
            if "unraid" in ln.lower() and not any(n in ln.lower() for n in names):
                bad.append(f"{f}:{i}: {ln.strip()[:100]}")
    for b in bad:
        print(f"  [FAIL] {b}")
    if not bad:
        print("  [ok]   Unraid is named only where its XML files are the subject")
    sys.exit(1 if bad else 0)


def changelog():
    """The changelog names no bug or roadmap number:
    B655 and R209 are the notebook's, which a reader of the public
    repository cannot open; a line points at the commit it landed in, as
    the others do, and at nothing otherwise."""
    import subprocess  # noqa: PLC0415
    bad = []
    lines = pathlib.Path("CHANGELOG.md").read_text(encoding="utf-8", errors="replace").splitlines()
    for i, ln in enumerate(lines, 1):
        if re.search(r"\b[BR]\d{2,}(\.\d+)?\b", ln):
            bad.append(f"CHANGELOG.md:{i}: {ln.strip()[:100]}")
    # ...and every commit the unreleased lines name is one this branch holds:
    # the section is the release's notes, and a hash that is not on the
    # branch (an amended copy, a helper's worktree) links to nothing.
    head = subprocess.run(["git", "rev-list", "HEAD"], capture_output=True, text=True, check=False)
    held = head.stdout.split() if head.returncode == 0 else []
    if held:
        unreleased = True
        for i, ln in enumerate(lines, 1):
            if ln.startswith("## ") and not ln.startswith("## Unreleased"):
                unreleased = False
            if not unreleased:
                continue
            for h in re.findall(r"\b[0-9a-f]{7,12}\b", ln):
                if re.search(r"[a-f]", h) and not any(c.startswith(h) for c in held):
                    bad.append(f"CHANGELOG.md:{i}: names {h}, which is no commit on this branch")
    for b in bad:
        print(f"  [FAIL] {b}")
    if not bad:
        print("  [ok]   the changelog names commits this branch holds, never a bug's or a roadmap item's number")
    sys.exit(1 if bad else 0)


def packs():
    """The official packs under packs/ are the shipped tables in bbtool.json's
    format: tools/packs-export.py --check holds them to it."""
    import subprocess
    r = subprocess.run([sys.executable, "tools/packs-export.py", "--check"], check=False)
    sys.exit(r.returncode)


def dupes():
    """A name defined twice where the second silently wins: a function or
    method twice in one python class or module (the server's Handler
    lost a handler to a later one of the same name), and a top-level name
    declared in two of the page's classic scripts, which share one global
    scope, so the later script fails to load whole."""
    import ast
    bad = []
    for f in sorted(pathlib.Path("scripts").rglob("*.py")):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), str(f))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for scope in [tree, *(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))]:
            seen = {}
            for n in scope.body:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.decorator_list:
                    if n.name in seen:
                        bad.append(f"{f}:{n.lineno}: {n.name} again (first at line {seen[n.name]}), so only this one runs")
                    seen.setdefault(n.name, n.lineno)
    page = pathlib.Path("scripts/dashboard/index.html")
    if page.is_file():
        srcs = re.findall(r'<script src="([\w.-]+\.js)"></script>', page.read_text(encoding="utf-8"))
        owner = {}
        decl = re.compile(r"^(?:let|const|var|function\*?|async function|class)\s+([A-Za-z_$][\w$]*)")
        for src in srcs:
            f = page.parent / src
            if not f.is_file():
                continue
            for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                m = decl.match(ln)
                if not m:
                    continue
                names = [m.group(1)]
                # let a = 1, b = 2: each name the line declares at its top level
                if ln.startswith(("let ", "var ", "const ")):
                    depth, cur, out = 0, "", []
                    for ch in ln.split(None, 1)[1].rstrip(";"):
                        depth += ch in "([{" or 0
                        depth -= ch in ")]}" or 0
                        if ch == "," and depth == 0:
                            out.append(cur)
                            cur = ""
                        else:
                            cur += ch
                    out.append(cur)
                    names = [mm.group(1) for mm in (re.match(r"\s*([A-Za-z_$][\w$]*)\s*(=|$)", x) for x in out) if mm]
                for nm in names:
                    if nm in owner and owner[nm][0] != src:
                        bad.append(f"scripts/dashboard/{src}:{i}: {nm} is declared in {owner[nm][0]}:{owner[nm][1]} too, so {src} would not load")
                    owner.setdefault(nm, (src, i))
    for b in bad:
        print(f"  [FAIL] {b}")
    if not bad:
        print("  [ok]   no function, method or page-level name is defined twice")
    sys.exit(1 if bad else 0)


def releasekey():
    """config/aerieos-release.pub parses to the release key, or the key and
    its spare, each 64 hex characters, as its one reader reads it
    (releasepub.py: the Enroll script's and the build's signer's). A file
    that does not parse names no key at all, so every node enrolled from
    that build would pin nothing: a red build here, never that."""
    # The tree being linted, not the copy of aerie this runs from.
    sys.path.insert(0, os.path.join(os.getcwd(), "scripts", "lib"))
    import releasepub                                               # noqa: E402
    keys, why = releasepub.read(os.path.join("config", "aerieos-release.pub"))
    if why:
        print(f"  [FAIL] config/aerieos-release.pub: {why}. It names the release key on one line and its spare on a "
              f"second, each as {releasepub.NAME} and 64 hex characters; as it is, the Enroll script would hand a new "
              "node no key to pin")
        sys.exit(1)
    print("  [ok]   config/aerieos-release.pub names the release key" + (" and its spare" if len(keys) > 1 else "")
          + ", read as the Enroll script and the build's signer read it")
    sys.exit(0)


def releasesigners():
    """config/release-signers' dev lines are config/aerieos-release.pub's keys
    as OpenSSH writes them, each line is a signer in the one namespace it is
    named for, no stable signer is a key the release build holds, and the
    stick maker carries the same lines: tools/release-signers.py --check,
    which --write puts right. A file that drifted is an install that
    refuses every dev build, or a stick checked against other keys."""
    import subprocess
    r = subprocess.run([sys.executable, "tools/release-signers.py", "--check"], check=False)
    sys.exit(r.returncode)


def selectors():
    """A selector no browser reads: :has anywhere inside another :has's
    argument. A browser drops the whole rule for it, every selector in its
    list with it, and says nothing; the read-only Scanners page drew every
    button it meant to hide until a picture showed it."""
    bad = []
    for f in sorted(pathlib.Path("scripts/dashboard").glob("page-*.css")):
        text = f.read_text(encoding="utf-8", errors="replace")
        # Comments out, their newlines kept so a line number stays true.
        text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
        for m in re.finditer(r":has\(", text):
            depth, i = 1, m.end()
            while i < len(text) and depth:
                if text.startswith(":has(", i):
                    line = text.count("\n", 0, m.start()) + 1
                    bad.append(f"{f}:{line}: :has() inside :has(), which drops the whole rule")
                    break
                depth += {"(": 1, ")": -1}.get(text[i], 0)
                i += 1
    for b in dict.fromkeys(bad):
        print(f"  [FAIL] {b}")
    if not bad:
        print("  [ok]   no selector nests :has(), which a browser drops whole")
    return 1 if bad else 0


FORMS_BASELINE = pathlib.Path("scripts/dashboard/test/forms-baseline.json")
_FIELD = re.compile(r"<(input|textarea|select)\b([^>]*)", re.I)
# What is not a form's field: a tick, a choice of one, a file picker behind a
# press, a search over a list, and what is never on show.
_NOT_A_FIELD = re.compile(r'type=\\?["\'](checkbox|radio|hidden|file|search|range|color)', re.I)


def _raw_fields(text):
    """The fields a page file writes itself: every input, textarea and select
    not on a line that hands it to formField, which is where a form's control
    is written."""
    n = 0
    for line in text.splitlines():
        if "formField(" in line:
            continue
        n += sum(1 for m in _FIELD.finditer(line) if not _NOT_A_FIELD.search(m.group(2)))
    return n


def forms():
    """A form is formBox and formField (a form's
    buttons touched its field and hung past it, pointed out many times): the
    part owns the form's layout, so a page cannot write one its own way. The
    fields page code writes outside it are counted per file against
    test/forms-baseline.json, and a count only falls: a new form written by
    hand fails here, and a form moved onto the part lowers its file's number."""
    import json
    base = json.loads(FORMS_BASELINE.read_text(encoding="utf-8")) if FORMS_BASELINE.exists() else {}
    files = sorted([*pathlib.Path("scripts/dashboard").glob("tab-*.js"), *pathlib.Path("scripts/dashboard").glob("nb-*.js"),
                    *pathlib.Path("scripts/dashboard").glob("page-*.js"), pathlib.Path("scripts/dashboard/index.html")])
    bad = []
    for f in files:
        if not f.exists():
            continue
        n, was = _raw_fields(f.read_text(encoding="utf-8", errors="replace")), int(base.get(f.name, 0))
        if n > was:
            bad.append(f"{f}: {n} fields written outside formField, {was} before: a form is formBox and formField (R301)")
        elif n < was:
            bad.append(f"{f}: {n} fields written outside formField, {was} in {FORMS_BASELINE}: lower it to {n}, so it stays down")
    for b in bad:
        print(f"  [FAIL] {b}")
    if not bad:
        print(f"  [ok]   no page writes a form's field outside formField past {FORMS_BASELINE.name}")
    return 1 if bad else 0


CITES_BASELINE = pathlib.Path("tools/cites-baseline.json")
# A tracker's number as it is written (R12, B340), and a dated word of the
# operator's. A linter's rule code after noqa is neither.
_CITE_ID = re.compile(r"(?<![A-Za-z0-9_#/.-])[BR][0-9]{1,4}(?![0-9A-Za-z_-])")
_CITE_DATED = re.compile(r"[Oo]perator[^)\n]{0,40}?\b[0-9]{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)")
_CITE_NOT = re.compile(r"(?:noqa|nosemgrep)[:=]?[ \t]*[A-Za-z0-9_.,\[\] =-]*")
_CITE_ROOTS = ("scripts", "tools", "nodes", "image", "lab", "platforms", "apps")
_CITE_SKIP = (".png", ".jpg", ".ico", ".svg", ".woff2", ".zip", ".gz", ".json", ".lock", ".jar", ".keystore", ".pdf", ".md", ".txt", ".xml")


def _cites_in(text):
    text = _CITE_NOT.sub("", text)
    return len(_CITE_ID.findall(text)) + len(_CITE_DATED.findall(text))


def cites():
    """A comment says what the code does and why. Who asked for it and on
    which day is the commit's to say, and a roadmap item's or a bug's number
    is the notebook's, which a reader of the repository cannot open. Each
    tracked source file's count of such numbers and dated citations is held
    to tools/cites-baseline.json, where a file not named has none, and a
    count only falls: what is left there is a number that is the code's own
    subject (the ids' own module, a test's sample item). A migration that
    shipped is never edited, so those are not counted."""
    import json
    import subprocess
    base = json.loads(CITES_BASELINE.read_text(encoding="utf-8")) if CITES_BASELINE.exists() else {}
    listed = subprocess.run(["git", "ls-files", *_CITE_ROOTS], capture_output=True, text=True, check=False).stdout.split("\n")
    bad, seen = [], set()
    for f in listed:
        if not f or f.endswith(_CITE_SKIP) or "/statemigrations/" in f:
            continue
        try:
            n = _cites_in(pathlib.Path(f).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        seen.add(f)
        was = int(base.get(f, 0))
        if n > was:
            bad.append(f"{f}: {n} tracker numbers or dated citations, {was} allowed: say what the code does and why, "
                       "and leave who asked and when to the commit")
        elif n < was:
            bad.append(f"{f}: {n} tracker numbers or dated citations, {was} in {CITES_BASELINE}: lower it to {n}, so it stays down")
    for f in sorted(set(base) - seen):
        bad.append(f"{f} is in {CITES_BASELINE} and is no tracked source file: take its line out")
    for b in bad[:40]:
        print(f"  [FAIL] {b}")
    if len(bad) > 40:
        print(f"  [FAIL] ...and {len(bad) - 40} more")
    if not bad:
        print(f"  [ok]   no source file cites a tracker number or a dated instruction past {CITES_BASELINE.name} ({sum(base.values())} left in {len(base)} files)")
    return 1 if bad else 0


# Names this repository does not say: other projects of its maker's, which a
# reader of it cannot follow and which are not its to name. Held as hashes
# (sha256 of the name in lowercase letters and digits run together, its first
# sixteen hex digits) so that this check does not say them either; the plain
# list is in the project's notebook. One set is matched however the name's
# words are joined but by a space (Name, name, a-name, a.name, a_name), the
# other across a space too, for a name ordinary words would not make.
_UNSAID_TIGHT = frozenset((
    "0930417631d146a6", "18b5c3511317576d", "1c7454ae163a3a77", "380748f177701518", "59b888d269ed5825",
    "6e87fdb2c1f245a2", "7d6a3ef9b5108a68", "939eaa0641e023c5", "944691f4069f15df", "af07d431bed9b179",
    "d3014d162f7cad1e", "ec17d0de05966bdc", "fbc4b01f101953ce",
))
_UNSAID_LOOSE = frozenset((
    "54e6c93c5cdce0ba", "59b888d269ed5825", "6e87fdb2c1f245a2", "944691f4069f15df", "f29540481bc5888e",
))
_UNSAID_LENGTHS = frozenset((7, 8, 9, 10, 11, 12, 15, 16, 18))
_UNSAID_PART = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+")
_UNSAID_SKIP = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff2", ".zip", ".gz", ".xz", ".jar", ".keystore", ".pdf", ".apk", ".bin")


def said_hash(name):
    """A name as the two sets hold it."""
    import hashlib
    return hashlib.sha256("".join(_UNSAID_PART.findall(name)).lower().encode("utf-8")).hexdigest()[:16]


def unsaid_in(line, tight=_UNSAID_TIGHT, loose=_UNSAID_LOOSE, lengths=_UNSAID_LENGTHS):
    """The stretches of a line that say a held name, as the line has them:
    its words taken apart at capitals, digits and anything that is neither,
    then one to five in a row tried together."""
    import hashlib
    parts = [(m.group(0).lower(), m.start(), m.end()) for m in _UNSAID_PART.finditer(line)]
    found = []
    for i in range(len(parts)):
        joined, close = "", True
        for j in range(i, min(i + 5, len(parts))):
            if j > i:
                gap = line[parts[j - 1][2]:parts[j][1]]
                if len(gap) > 1 or (gap and gap not in " -_./"):
                    break
                close = close and gap != " "
            joined += parts[j][0]
            if len(joined) in lengths:
                digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]
                if digest in loose or (close and digest in tight):
                    found.append(line[parts[i][1]:parts[j][2]])
    return found


def unsaid():
    """No tracked file names another project of the maker's: where a bug was
    met is said in words, and a sample takes a made-up name."""
    import subprocess
    listed = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=False).stdout.split("\n")
    bad = []
    for f in listed:
        if not f or f.lower().endswith(_UNSAID_SKIP):
            continue
        try:
            if os.path.getsize(f) > 4_000_000:
                continue
            text = pathlib.Path(f).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for n, line in enumerate(text.split("\n"), 1):
            for words in unsaid_in(line):
                bad.append(f"{f}:{n}: '{words}' is a name this repository does not say: say what happened in words, or give a sample a made-up name")
    for b in bad[:40]:
        print(f"  [FAIL] {b}")
    if len(bad) > 40:
        print(f"  [FAIL] ...and {len(bad) - 40} more")
    if not bad:
        print("  [ok]   no file names another project of the maker's")
    return 1 if bad else 0


CHECKS = {"runner": runner, "selectors": selectors, "forms": forms, "cites": cites, "unsaid": unsaid, "xml": xml_, "settings": settings, "layout": layout, "hosted": hosted, "pinned": pinned,
          "channels": channels, "shipped": shipped, "formats": formats, "packs": packs, "unraid": unraid,
          "changelog": changelog, "dupes": dupes, "releasekey": releasekey, "releasesigners": releasesigners}

if __name__ == "__main__":
    # What a check returns is its verdict: layout answered 1 for a tracked
    # file its page does not name and this line dropped it, so the check
    # printed FAIL and lint was clean (the audit of 13 Nov).
    sys.exit(CHECKS[verb]() or 0)
