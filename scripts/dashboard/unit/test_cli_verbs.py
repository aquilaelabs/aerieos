"""scripts/aerie names its verbs in four places: the dispatcher's case, the
list of those the controller answers (lib/relay-verbs, read by the server
too), the subcommands of a relayed verb that run where they are typed, and
the verbs `aerie -p` refuses because they answer for this machine. A verb
added to one and not the others was refused on arrival, never sent, or
answered for the wrong space; this holds the four to each other."""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", ".."))


def text():
    with open(os.path.join(SCRIPTS, "aerie"), encoding="utf-8") as f:
        return f.read()


def dispatched(src):
    """The verbs of the last `case "${1:-help}" in`, the dispatcher."""
    body = src[src.rindex('case "${1:-help}" in'):]
    body = body[:body.index("\nesac")]
    return {v for line in re.findall(r"^    ([a-z][a-z0-9|-]*)\)", body, re.M) for v in line.split("|")}


def relayed():
    with open(os.path.join(SCRIPTS, "lib", "relay-verbs"), encoding="utf-8") as f:
        return set(f.read().split())


def kept_here(src):
    """The `VERB SUB` pairs of a relayed verb that run on the node."""
    m = re.search(r'^        ((?:"[a-z-]+ [a-z-]+"\|?)+)\) ', src, re.M)
    return [tuple(p.split()) for p in re.findall(r'"([a-z-]+ [a-z-]+)"', m.group(1))]


def refused_for_another_space(src):
    m = re.search(r'^        ([a-z|-]+)\)\n\s+die "aerie -p: aerie \$\{1\} answers for this machine', src, re.M)
    return set(m.group(1).split("|"))


class Verbs(unittest.TestCase):
    def setUp(self):
        self.src = text()
        self.verbs = dispatched(self.src)

    def test_the_dispatcher_is_read(self):
        for v in ("status", "roadmap", "tests", "toolchains", "map"):
            self.assertIn(v, self.verbs)

    def test_every_relayed_verb_is_a_verb(self):
        self.assertEqual(relayed() - self.verbs, set())

    def test_a_subcommand_kept_on_the_node_belongs_to_a_relayed_verb(self):
        pairs = kept_here(self.src)
        self.assertIn(("tests", "run"), pairs)
        self.assertEqual({v for v, _ in pairs} - relayed(), set())

    def test_what_p_refuses_is_a_verb_of_this_machine(self):
        refused = refused_for_another_space(self.src)
        self.assertIn("status", refused)
        self.assertEqual(refused - self.verbs, set())
        self.assertEqual(refused & relayed(), set())


if __name__ == "__main__":
    unittest.main()
