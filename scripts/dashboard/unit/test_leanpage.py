"""The page is served without its comments (R228 step 15), by a tokenizer:
what is inside a string, a template literal or a regular expression is never
a comment, and a newline a comment ended on stays where semicolon insertion
could read it. Every page script reads the same tokens after as before."""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.join(HERE, "..")
sys.path.insert(0, DASH)
import leanpage  # noqa: E402

js = leanpage.strip_js


class Js(unittest.TestCase):
    def test_comments_go_and_their_lines_with_them(self):
        self.assertEqual(js("// head\na = 1; // tail\n/* block */\nb = 2;\n"), "a = 1;\nb = 2;\n")

    def test_what_looks_like_a_comment_in_a_string_stays(self):
        src = 'u = "https://x.test/a"; v = \'/* no */\'; w = "a\\"//b";\n'
        self.assertEqual(js(src), src)

    def test_a_template_keeps_its_text_and_its_code_loses_its_comments(self):
        src = "t = `line // kept\n  /* kept */ ${a /* gone */ + `${b // gone\n}`}`;\n"
        self.assertEqual(js(src), "t = `line // kept\n  /* kept */ ${a + `${b\n}`}`;\n")

    def test_a_regular_expression_is_not_a_comment(self):
        for src in ("r = /https?:\\/\\//.test(s);\n", "if (x) return /a\\/\\/b/g;\n", "f(/[/]/, 1);\n",
                    "x = a.split(/\\/\\//);\n"):
            self.assertEqual(js(src), src, src)

    def test_a_division_is_not_a_regular_expression(self):
        self.assertEqual(js("a = (b) / 2; // half\nc = d[0] / e / f;\n"), "a = (b) / 2;\nc = d[0] / e / f;\n")

    def test_a_newline_a_comment_held_is_kept(self):
        # Without it these would join into one statement.
        self.assertEqual(js("a = b /* one\ntwo */ c()\n"), "a = b\n c()\n")
        self.assertEqual(js("x\n// y\n(z)\n"), "x\n(z)\n")

    def test_stripping_again_changes_nothing(self):
        src = open(os.path.join(DASH, "page-paint.js")).read()
        once = js(src)
        self.assertEqual(js(once), once)
        self.assertLess(len(once), len(src))


class CssHtml(unittest.TestCase):
    def test_css_comments_go_and_strings_stay(self):
        self.assertEqual(leanpage.strip_css('/* a */\n.x{content:"/* no */"} /* b */\n'), '.x{content:"/* no */"}\n')

    def test_html_comments_go_but_a_placeholder_stays(self):
        out = leanpage.strip_html('<p>a</p>\n<!-- why -->\n<!--BANNER-->\n<script>x = 1; // c\n</script>\n<pre><!-- kept --></pre>\n')
        self.assertEqual(out, '<p>a</p>\n<!--BANNER-->\n<script>x = 1;\n</script>\n<pre><!-- kept --></pre>\n')


class Served(unittest.TestCase):
    def test_a_page_file_is_served_stripped_and_kept_until_it_changes(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        p = os.path.join(d, "page-x.js")
        with open(p, "w") as f:
            f.write("// note\nlet a = 1;\n")
        self.assertEqual(leanpage.served(p), b"let a = 1;\n")
        with open(p, "w") as f:
            f.write("// note\nlet a = 22;\n")
        self.assertEqual(leanpage.served(p), b"let a = 22;\n")

    @unittest.skipUnless(shutil.which("node"), "node is not here")
    def test_every_page_script_reads_the_same_tokens(self):
        names = sorted(f for f in glob.glob(os.path.join(DASH, "*.js"))
                       if re.match(r"(tab|nb|page)-", os.path.basename(f)))
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        pairs = []
        for f in names:
            out = os.path.join(d, os.path.basename(f))
            with open(out, "w") as w:
                w.write(js(open(f).read()))
            pairs += [f, out]
        prog = ("const a=require('internal/deps/acorn/acorn/dist/acorn'),fs=require('fs');"
                "const t=s=>{const o=[];for(const k of a.tokenizer(s,{ecmaVersion:'latest',allowHashBang:true}))"
                "o.push(k.type.label+':'+(k.value instanceof RegExp?String(k.value):JSON.stringify(k.value)));return o.join('\\n')};"
                "const v=process.argv.slice(1);let bad=[];for(let i=0;i<v.length;i+=2)"
                "if(t(fs.readFileSync(v[i],'utf8'))!==t(fs.readFileSync(v[i+1],'utf8')))bad.push(v[i]);"
                "console.log(JSON.stringify(bad))")
        r = subprocess.run(["node", "--expose-internals", "-e", prog, *pairs], capture_output=True, text=True,
                           timeout=120, check=False)
        if r.returncode and "acorn" in r.stderr:
            self.skipTest("this node keeps no acorn to read tokens with")
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        self.assertEqual(r.stdout.strip(), "[]")


if __name__ == "__main__":
    unittest.main()
