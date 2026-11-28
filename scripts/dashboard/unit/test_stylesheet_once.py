"""A stylesheet says a thing once.

A declaration that a later rule in the same file, layer and media sets again
for every one of its selectors never reaches the page: it only tells a
reader something the page does not do (a flex written two ways nine lines
apart, a cursor a later rule turned back). The stylesheets are read rule by
rule and each such declaration fails by its file and line. A rule that sets
a property for a group and a later one that sets it for one of the group is
how a stylesheet is written, and is not one."""
import collections
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.normpath(os.path.join(HERE, ".."))
SHEETS = ("page-skin.css", "page-components.css", "page-surfaces.css", "page-overrides.css")


def _selectors(head):
    out, depth, cur = [], 0, ""
    for ch in head:
        depth += ch in "(["
        depth -= ch in ")]"
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    return out + ([cur.strip()] if cur.strip() else [])


def rules(text):
    """[(context, line, [selector], {property: value})] in the order written."""
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    out = []

    def walk(t, base, ctx):
        i, buf = 0, ""
        while i < len(t):
            c = t[i]
            if c == "{":
                j, depth = i + 1, 1
                while j < len(t) and depth:
                    depth += (t[j] == "{") - (t[j] == "}")
                    j += 1
                head, body, buf = " ".join(buf.split()), t[i + 1:j - 1], ""
                line = base + t.count("\n", 0, i) + 1
                if head.startswith("@"):
                    if not head.startswith(("@font-face", "@keyframes", "@property", "@page")):
                        walk(body, base + t.count("\n", 0, i + 1), ctx + [head])
                else:
                    decls = {}
                    for d in re.split(r";(?![^(]*\))", body):
                        if ":" in d:
                            k, v = d.split(":", 1)
                            decls[k.strip()] = " ".join(v.split())
                    out.append((" | ".join(ctx), line, _selectors(head), decls))
                i = j
                continue
            buf = "" if c == "}" else buf + c
            i += 1
    walk(text, 0, [])
    return out


def never_reached(text):
    """[(line, selectors, property, the line that sets it again)]."""
    rs = rules(text)
    later = collections.defaultdict(list)
    for order, (ctx, line, sels, decls) in enumerate(rs):
        for s in sels:
            for p in decls:
                later[(ctx, s, p)].append((order, line))
    out = []
    for order, (ctx, line, sels, decls) in enumerate(rs):
        for p, v in decls.items():
            if "!important" in v:
                continue
            again = [next((ln for o, ln in later[(ctx, s, p)] if o > order), 0) for s in sels]
            if all(again):
                out.append((line, ", ".join(sels), p, again[0]))
    return out


class Once(unittest.TestCase):
    def test_no_declaration_is_set_again_for_all_it_names(self):
        said = []
        for name in SHEETS:
            with open(os.path.join(DASH, name), encoding="utf-8") as f:
                for line, sels, prop, again in never_reached(f.read()):
                    said.append(f"{name}:{line} {sels[:60]} sets {prop}, and line {again} sets it again for all of them")
        self.assertEqual(said, [])

    def test_it_reads_a_group_and_one_of_the_group_as_written(self):
        css = ".a,.b{color:red}\n.b{color:blue}\n@media(max-width:600px){.a{color:green}}\n"
        self.assertEqual(never_reached(css), [], "a group, then one of it, then another width: each reaches something")
        dead = ".a{gap:4px;color:red}\n.x{top:0}\n.a{gap:8px}\n"
        self.assertEqual(never_reached(dead), [(1, ".a", "gap", 3)])
        self.assertEqual(never_reached(".a,.b{gap:1px}\n.b{gap:2px}\n.a{gap:3px}\n"), [(1, ".a, .b", "gap", 3)],
                         "set again for each of the two, by two rules")
        self.assertEqual(never_reached(".a{gap:1px !important}\n.a{gap:2px}\n"), [], "an !important is not overridden by what follows")
        self.assertEqual(never_reached(":is(.a,.b) .c{gap:1px}\n:is(.a,.b) .c{gap:2px}\n")[0][1], ":is(.a,.b) .c", "a comma inside :is() is one selector's")


if __name__ == "__main__":
    unittest.main()
