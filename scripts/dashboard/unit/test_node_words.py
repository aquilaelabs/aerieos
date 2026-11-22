"""What a person reads about a node is one short sentence, with no key's
characters and no command to type (the leftovers audit, 21 Nov): the node's
Updates fact named its release keys by their first characters, the
Un-enroll dialog and the root-off line named console commands, and the bell
said a reused token in three sentences where the server's own row says it
in one. A switched-off pack's bell row is titled as switched off, not as
withdrawn by the catalog."""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.normpath(os.path.join(HERE, ".."))


def text(name):
    with open(os.path.join(DASH, name), encoding="utf-8") as f:
        return f.read()


def between(src, start, end):
    i = src.index(start)
    return src[i:src.index(end, i + len(start))]


class Words(unittest.TestCase):
    def test_the_updates_fact_names_no_key_by_its_characters(self):
        fact = between(text("tab-nodes.js"), "function ndUpdatesFact(n){", "\nfunction ndFacts(")
        self.assertNotRegex(fact, r"\.slice\(0, *\d+\)")
        self.assertIn('"the release key and its spare"', fact)

    def test_no_console_command_on_the_nodes_page(self):
        page = text("tab-nodes.js")
        for command in ("bb-sandbox uninstall", "aerieos-agent root-asks on"):
            self.assertNotIn(command, page)
        off = between(page, "function nodeRootOffLine(n){", "\nfunction ")
        self.assertIn("which alone switches it back on", off)
        self.assertNotIn("<code>", off)

    def test_the_reused_token_row_is_the_servers_one_sentence(self):
        bell = between(text("page-bell.js"), 'if (a.kind === "token-reuse"){', "\n  }")
        said = re.search(r'<div class="bsum">([^<]*)</div>', bell).group(1)
        server = text("server.py")
        words = between(server, 'if k == "token-reuse":', "if k == ")
        self.assertIn(said.split(", so ")[0], words)
        self.assertEqual(said, "it presented a token it had already replaced, so every token of it is revoked: "
                               "Enroll script on its row if you restored it, and treat its disk as copied if you did not")
        self.assertEqual(said.count(". "), 0, "one sentence")

    def test_a_switched_off_pack_is_titled_so(self):
        bell = between(text("page-bell.js"), 'if (a.kind === "pack"){', "\n  }")
        self.assertIn("${a.unfit ? `${esc(a.name)} is switched off` : `The catalog withdrew ${esc(a.name)}`}", bell)


if __name__ == "__main__":
    unittest.main()
