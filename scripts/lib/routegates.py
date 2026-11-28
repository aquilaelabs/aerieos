"""What a handler of the dashboard's API asks of whoever calls it, read off
its own code.

A route whose handler refuses for itself says so in the route record
(server.py ROUTES) as ("handler", NAME, ...): the names of everything the
handler asks, so that who may reach a route is read in the table and a route
that asks nothing is seen there. The names are derived here from the checks
the handler makes, and a unit test holds the record to them, so the table
cannot say one thing while the code does another. tools/api-doc.py prints
the same names in docs/api.md.

The names:

  space             the request names a space this account sees
  unlocked          ...which is not locked against the asker, or read-only
  space-owner       the asker owns the space the request names
  PERM              a permission asked of the install, or of the space named
                    (controller, settings, docker-write: users.may's names)
  node:PERM         a permission asked of the node the request names
  instance:PERM     ...or of one instance of an area (a cluster, a runner)
  dial:NAME         a session's ask goes through the space's Agents may dial
  admin, owner      whether the asker administers the install, or owns it
  own               the asking account's own things (its profile, its bell)
  theirs            a terminal session of the asker's own
  seen              any account; the answer holds what the asker may see
  open              any account, the same answer for each

A name is everything the handler consults, so it is no smaller than what it
refuses on: a handler that reads a permission to draw a dead button names it
too. What exactly is refused is the handler's docstring and its code.

A handler whose asks are a table is read off the table. One in its module,
walked row by row (`for ... in prefs.SAVE_ASKS`): each row's first word is
what a change asks, "node" there the right to place a space on a node,
"space:NAME" a permission asked of the space, and a row that asks nothing
names nothing. One of server.py's own, an action to its row (VERSION_ACTS):
each row's `ask` is a permission a person needs on the space and its `dial`
the Agents may dial a session's ask goes through.
"""
import ast
import os

DASH = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dashboard"))

# The handler's helpers that write a refusal, and what each asks. A helper
# with a permission's name as its first argument asks that permission.
PERM_CALLS = {"_refused": "", "_space_write": "", "_session_held": "", "_refused_on_node": "node:", "_refused_instance": "instance:"}
SPACE_CALLS = ("_project_asked", "_not_project", "_not_card", "_not_space", "_space_write")
UNLOCKED_CALLS = ("_readonly", "_space_write")
# Helpers of the Handler that only carry a request or an answer: nothing in
# them is a gate, so they are not read into.
PLUMBING = {"_json", "_q", "_who", "_principal", "_result", "_read_json", "_content_length", "_attachment", "_static", "_origin",
            "_send_bundle", "_gzip", "_authed", "_deny", "_who_raw", "_cookie", "_read_form", "_ctr_checks"}


def _literal(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _self_call(node):
    """The method's name for `self.NAME(...)`, else ''."""
    f = node.func
    return f.attr if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "self" else ""


def _dotted(node):
    f = node.func
    return f"{f.value.id}.{f.attr}" if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else ""


def table_asks(module, name, dash=DASH):
    """The names a module's table of asks carries, in its order: the first
    word of each row of `name` in MODULE.py beside server.py."""
    try:
        with open(os.path.join(dash, f"{module}.py"), encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except OSError:
        return []
    out = []
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)):
            continue
        if isinstance(node.value, (ast.Tuple, ast.List)):
            for row in node.value.elts:
                word = _literal(row.elts[0]) if isinstance(row, (ast.Tuple, ast.List)) and row.elts else None
                if word:
                    out.append("node:node" if word == "node" else word[len("space:"):] if word.startswith("space:") else word)
        elif isinstance(node.value, ast.Dict):
            # An action to its row: what a person is asked, then a session's
            # dial. Several actions sharing a row are written as one (**{...}).
            for row in node.value.values:
                row = row.value if isinstance(row, ast.DictComp) else row
                for kw in row.keywords if isinstance(row, ast.Call) else ():
                    if kw.arg in ("ask", "dial") and _literal(kw.value):
                        out.append(("dial:" if kw.arg == "dial" else "") + _literal(kw.value))
    return out


def asks(fn, handlers, depth=2, _seen=None):
    """The names of what the handler `fn` asks, in the order it asks them:
    its own checks, and those of the Handler's methods it calls, `depth`
    calls down. `handlers` is {name: FunctionDef} for the Handler class."""
    seen = set() if _seen is None else _seen
    seen.add(fn.name)
    out, own_used = [], []

    def add(name):
        if name and name not in out:
            out.append(name)
    # In the order the handler is written, so the first name is the first
    # thing it asks.
    tables = {}
    for n in ast.walk(fn):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id.endswith("_ACTS") \
                and (n.id not in tables or (n.lineno, n.col_offset) < (tables[n.id].lineno, tables[n.id].col_offset)):
            tables[n.id] = n
    calls = sorted([n for n in ast.walk(fn) if isinstance(n, (ast.Call, ast.For))] + list(tables.values()), key=lambda n: (n.lineno, n.col_offset))
    for node in calls:
        if isinstance(node, ast.Name):
            # One of server.py's own tables, an action to its row.
            for got in table_asks("server", node.id):
                add(got)
            continue
        if isinstance(node, ast.For):
            # A walk over a module's table of asks: what the table names.
            it = node.iter
            if isinstance(it, ast.Attribute) and isinstance(it.value, ast.Name) and it.attr.endswith("_ASKS"):
                for got in table_asks(it.value.id, it.attr):
                    add(got)
            continue
        name, dotted = _self_call(node), _dotted(node)
        first = _literal(node.args[0]) if node.args else None
        if name in SPACE_CALLS:
            add("space")
        if name in UNLOCKED_CALLS or (name == "_project_asked" and any(k.arg == "write" and getattr(k.value, "value", None) is True
                                                                        for k in node.keywords)):
            add("unlocked")
        if name in PERM_CALLS and first:
            add(PERM_CALLS[name] + first)
        elif name in PERM_CALLS and node.args and isinstance(node.args[0], ast.IfExp):
            # A permission picked by the action: both arms are asked.
            for arm in (node.args[0].body, node.args[0].orelse):
                if _literal(arm):
                    add(PERM_CALLS[name] + _literal(arm))
        if name == "_trash_refused":
            add("trash")
        if name == "_dialed" and len(node.args) > 1 and _literal(node.args[1]):
            add("dial:" + _literal(node.args[1]))
        if name == "_not_theirs":
            add("theirs")
        if name in ("_account",):
            add("own")
        if name in ("_node_files_admin",) or dotted == "users.is_admin":
            add("admin")
        if dotted == "users.is_owner":
            add("owner")
        if dotted == "users.may" and len(node.args) > 1 and _literal(node.args[1]):
            add(_literal(node.args[1]))
        if dotted == "users.may_node" and len(node.args) > 1 and _literal(node.args[1]):
            add("node:" + _literal(node.args[1]))
        if dotted == "users.may_instance" and len(node.args) > 1 and _literal(node.args[1]):
            add("instance:" + _literal(node.args[1]))
        if dotted in ("users.may_see", "users.may_work") or (isinstance(node.func, ast.Name) and node.func.id == "project_names"):
            add("space")
        if dotted == "projects.locked_out":
            add("unlocked")
        if dotted in ("users.uid_of", "users.whose"):
            own_used.append(1)
        if name == "_node_asked":
            add("node:read")
        # One of the Handler's own methods: what it asks, this one asks.
        if name and name in handlers and name not in PLUMBING and name not in PERM_CALLS and name not in SPACE_CALLS \
                and name not in UNLOCKED_CALLS and name not in seen and depth > 0:
            for got in asks(handlers[name], handlers, depth - 1, seen):
                if got not in ("seen", "open"):
                    add(got)
    if not out:
        # Nothing refused by name: the asker's own things where its account
        # is what is read, what it may see where it is handed on, else open.
        uses_who = any(isinstance(n, ast.Call) and _self_call(n) in ("_who", "_principal") for n in ast.walk(fn))
        out.append("own" if own_used else "seen" if uses_who else "open")
    return out


def handlers_of(tree):
    """{name: FunctionDef} for server.py's Handler class."""
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Handler":
            return {fn.name: fn for fn in node.body if isinstance(fn, ast.FunctionDef)}
    return {}


def routes_of(tree):
    """The route record's rows as (method, how, path, handler, gate node)."""
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "ROUTES" for t in node.targets):
            for el in node.value.elts:
                method, how, path, fn = (ast.literal_eval(e) for e in el.args[:4])
                gate = el.args[4] if len(el.args) > 4 else next((k.value for k in el.keywords if k.arg == "gate"), None)
                yield method, how, path, fn, gate, el
