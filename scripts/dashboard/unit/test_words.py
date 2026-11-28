"""What the page says, held to the words rule (the operator's words
pass of 25 Nov): a person reads space and repository, never project or repo
(the names in code and the API keep project); a toast is one sentence; a
hint is a line, not a paragraph. Read from the page's sources as text: a
string with a space in it is prose, and one that interpolates or names an
API, an attribute or a field is code."""
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
PAGE = sorted(HERE.glob("*.js")) + [HERE / "index.html"]
CODE = re.compile(r"\$\{|/api/|data-|[=/?:.]projects?\b|\bprojects?[=_./(]|\.repos?\b|\brepos?[=_./]")
# A string literal where an expression starts (after an open bracket, a
# comma, an operator or return), so the code between two strings is never
# read as one; and the text between a template's tags.
LITERAL = re.compile(r"""(?:"(?:[^"\\\n]|\\.)*"|`(?:[^`\\]|\\.)*`)""")
TEXT = re.compile(r""">([^<>{}$`"]*[A-Za-z][^<>{}$`"]*)<""")
OPENS = tuple("(,=:?[{+|&!") + ("return",)
NOTIFY = re.compile(r"""notify\(\s*(`(?:[^`\\]|\\.)*`|"(?:[^"\\]|\\.)*")""")
HINT = re.compile(r"""<div class="hint[^"]*"[^>]*>((?:(?!</div>|<div|</p>).){40,}?)</div>""", re.S)


def prose(path):
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines()
    for m in LITERAL.finditer(src):
        before = src[max(0, m.start() - 12):m.start()].rstrip()
        if not before.endswith(OPENS):
            continue
        n = src[:m.start()].count("\n") + 1
        if lines[n - 1].strip().startswith(("//", "*", "/*", "<!--")):
            continue
        # A template's static parts only: what is inside ${...} is code.
        for part in re.split(r"\$\{(?:[^{}]|\{[^}]*\})*\}", m.group(0)[1:-1]):
            for piece in re.split(r"<[^>]*>", part):
                if " " in piece.strip() and not CODE.search(piece):
                    yield n, piece.strip()
    for m in TEXT.finditer(src):
        n = src[:m.start()].count("\n") + 1
        if " " in m.group(1).strip() and not CODE.search(m.group(1)) and not lines[n - 1].strip().startswith(("//", "*", "<!--")):
            yield n, m.group(1).strip()


class Words(unittest.TestCase):
    def test_space_and_repository_never_project_or_repo(self):
        bad = [f"{p.name}:{n}: {s[:80]}" for p in PAGE for n, s in prose(p) if re.search(r"\b(projects?|repos?)\b", s)]
        self.assertEqual(bad, [], "a person reads space and repository")

    def test_a_toast_is_one_sentence(self):
        bad = []
        for p in PAGE:
            src = p.read_text(encoding="utf-8")
            for m in NOTIFY.finditer(src):
                plain = re.sub(r"\$\{(?:[^{}]|\{[^}]*\})*\}", "X", m.group(1)[1:-1])
                if len(re.findall(r"[.!?](\s|$)", plain.strip())) > 1:
                    bad.append(f"{p.name}:{src[:m.start()].count(chr(10)) + 1}: {plain[:80]}")
        self.assertEqual(bad, [], "one sentence: a colon or a semicolon joins what a second one said")

    def test_a_hint_is_a_line(self):
        bad = []
        for p in PAGE:
            src = p.read_text(encoding="utf-8")
            for m in HINT.finditer(src):
                plain = re.sub(r"<[^>]+>", "", re.sub(r"\$\{(?:[^{}]|\{[^}]*\})*\}", "X", m.group(1)))
                if len(plain.split()) > 40:
                    bad.append(f"{p.name}:{src[:m.start()].count(chr(10)) + 1}: {len(plain.split())} words")
        self.assertEqual(bad, [], "about twenty-five words: the why goes in a comment, the docs or Help")


if __name__ == "__main__":
    unittest.main()
