"""/api/devapp's handler is its gates, in their order, and one call. The
gate was one function of 242 lines; it is seven methods, each a question
(what the request names, whose it is, what the asker may do to it, where it
would land, a session's own node and dial, a locked space, the spaces it
names), and the handler asks them in that order and hands the request to
devactions.request. Held here: the order, that the handler writes no
refusal of its own, and that every gate answers True only with a refusal
written."""
import ast
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.normpath(os.path.join(HERE, "..", "server.py")), encoding="utf-8") as _f:
    TREE = ast.parse(_f.read())
HANDLER = {f.name: f for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == "Handler" for f in n.body if isinstance(f, ast.FunctionDef)}
GATES = ["_devapp_whose", "_devapp_may", "_devapp_lands", "_devapp_session", "_devapp_locked", "_devapp_targets"]


def self_calls(fn):
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and isinstance(n.func.value, ast.Name) and n.func.value.id == "self"]
    return [n.func.attr for n in sorted(calls, key=lambda n: (n.lineno, n.col_offset))]


class Door(unittest.TestCase):
    def test_the_handler_names_the_request_asks_each_gate_in_order_and_makes_one_call(self):
        fn = HANDLER["_devapp"]
        asked = [c for c in self_calls(fn) if c.startswith("_devapp")]
        self.assertEqual(asked, ["_devapp_named"] + GATES)
        self.assertEqual([c for c in self_calls(fn) if not c.startswith("_devapp")], ["_who", "_json", "_principal"])
        onward = [ast.unparse(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call) and ast.unparse(n.func).startswith("devactions.")]
        self.assertEqual(onward, ["devactions.request"])
        self.assertLess(fn.end_lineno - fn.lineno, 45)
        words = [n.value for n in ast.walk(fn) if isinstance(n, ast.Constant) and isinstance(n.value, str) and "error" == n.value]
        self.assertEqual(words, [], "a refusal is a gate's to write")

    def test_every_gate_takes_the_same_five_and_answers_true_only_after_writing_a_refusal(self):
        for name in GATES:
            fn = HANDLER[name]
            self.assertEqual([a.arg for a in fn.args.args], ["self", "me", "sess", "name", "act", "req"], name)
            self.assertTrue(ast.get_docstring(fn), name)
            returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
            self.assertTrue(all(isinstance(r.value, ast.Constant) and r.value.value in (True, False) for r in returns), name)
            self.assertEqual(ast.unparse(fn.body[-1]), "return False", name)
            # Each `return True` follows a refusal written just before it: a
            # _json of its own, or a helper that writes one and says so.
            for parent in ast.walk(fn):
                for body in (getattr(parent, "body", None), getattr(parent, "orelse", None)):
                    if not isinstance(body, list):
                        continue
                    for i, st in enumerate(body):
                        if isinstance(st, ast.Return) and getattr(st.value, "value", None) is True:
                            before = ast.unparse(body[i - 1]) if i else ast.unparse(parent.test) if isinstance(parent, ast.If) else ""
                            self.assertRegex(before, r"self\._(json|refused|readonly|not_project|session_held|devapp_refused)\b", f"{name} line {st.lineno}")

    def test_what_the_request_names_is_read_once(self):
        fn = HANDLER["_devapp_named"]
        self.assertEqual(ast.unparse(fn.body[-1]), "return (name, act)")
        nones = [n for n in ast.walk(fn) if isinstance(n, ast.Return) and isinstance(n.value, ast.Constant) and n.value.value is None]
        self.assertEqual(len(nones), 2, "no such container, and neither a space nor a container")


if __name__ == "__main__":
    unittest.main()
