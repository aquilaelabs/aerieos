"""The page as it is served, without its comments (R228 step 15).

The tree keeps every comment; what a browser is sent leaves them out, a third
of the page's bytes. A tokenizer, not a pattern: a `//` inside a string, a
template literal (its `${}` code included) or a regular expression is not a
comment, and a newline a comment ended on is kept wherever automatic
semicolon insertion could read it. Lines inside a template literal are never
touched, so its whitespace is exactly the source's.

strip_js, strip_css and strip_html each take text and give text; served()
gives a page file's bytes as served, kept by what the file is on disk.
"""
import os
import re
import threading

# Where removing a comment left nothing on its line but whitespace: the line
# goes. Never in the source (a control character no file here carries).
_MARK = "\x01"

# After one of these words a `/` starts a regular expression, not a division.
_BEFORE_REGEX = frozenset(("return", "typeof", "instanceof", "in", "of", "new", "delete", "void",
                           "throw", "case", "do", "else", "yield", "await"))
_IDENT = re.compile(r"[A-Za-z0-9_$]")
# The characters that interest the scanner; everything between is copied.
_JS_NEXT = re.compile(r"[\"'`/{}]")
_TPL_NEXT = re.compile(r"[\\`$]")


def _regex_may_start(out):
    """Whether a `/` read now opens a regular expression, from what the
    code before it ends with."""
    j = len(out) - 1
    while j >= 0 and out[j] in " \t\r\n" + _MARK:
        j -= 1
    if j < 0:
        return True
    c = out[j]
    if c in ")]":
        return False
    if _IDENT.match(c):
        k = j
        while k >= 0 and _IDENT.match(out[k]):
            k -= 1
        return out[k + 1:j + 1] in _BEFORE_REGEX
    # An operator, an opening bracket, a comma, a semicolon, `}` (the end of
    # a block, after which a statement starts): an expression starts here.
    return True


def _code(s, i, out, in_template):
    """Copy code from s[i] into out, comments left out, until the end or,
    inside a template literal's ${...}, the `}` that closes it (returned
    past). Strings, templates and regular expressions are copied whole."""
    depth = 0
    n = len(s)
    while i < n:
        m = _JS_NEXT.search(s, i)
        if not m:
            out.append(s[i:])
            return n
        j = m.start()
        out.append(s[i:j])
        c = s[j]
        if c in "\"'":
            k = j + 1
            while k < n and s[k] != c and s[k] != "\n":
                k += 2 if s[k] == "\\" else 1
            out.append(s[j:k + 1])
            i = k + 1
        elif c == "`":
            i = _template(s, j, out)
        elif c == "{":
            depth += 1
            out.append(c)
            i = j + 1
        elif c == "}":
            if in_template and depth == 0:
                out.append(c)
                return j + 1
            depth -= 1
            out.append(c)
            i = j + 1
        else:                                           # "/"
            nxt = s[j + 1] if j + 1 < n else ""
            if nxt == "/":
                k = s.find("\n", j)
                k = n if k < 0 else k
                out.append(_MARK)
                i = k
            elif nxt == "*":
                k = s.find("*/", j + 2)
                k = n if k < 0 else k + 2
                out.append(_MARK + "\n" if "\n" in s[j:k] else _MARK)
                i = k
            elif _regex_may_start("".join(out[-8:]) if len(out) > 8 else "".join(out)):
                k, in_class = j + 1, False
                while k < n and s[k] != "\n":
                    if s[k] == "\\":
                        k += 2
                        continue
                    if s[k] == "[":
                        in_class = True
                    elif s[k] == "]":
                        in_class = False
                    elif s[k] == "/" and not in_class:
                        break
                    k += 1
                out.append(s[j:k + 1])
                i = k + 1
            else:
                out.append(c)
                i = j + 1
    return n


def _template(s, j, out):
    """Copy a template literal from its opening backtick at s[j]: its text
    as written, its ${...} code through _code. Returns the index past it."""
    n = len(s)
    k = j + 1
    out.append("`")
    while k < n:
        c = s[k]
        if c == "\\":
            out.append(s[k:k + 2])
            k += 2
        elif c == "`":
            out.append(c)
            return k + 1
        elif c == "$" and k + 1 < n and s[k + 1] == "{":
            out.append("${")
            k = _code(s, k + 2, out, True)
        else:
            m = _TPL_NEXT.search(s, k)
            e = m.start() if m else n
            if e == k:
                out.append(c)
                k += 1
            else:
                out.append(s[k:e])
                k = e
    return n


_GAP = re.compile(r"[ \t]*" + _MARK + r"[ \t" + _MARK + r"]*")


def _gaps(line):
    """Each run of comment marks on a line: one space between two tokens,
    nothing at either end."""
    end = len(line)
    return _GAP.sub(lambda m: "" if m.start() == 0 or m.end() == end else " ", line)


def _tidy(text):
    """The lines a removed comment left: one with nothing else on it goes;
    on one that keeps something, a comment between two tokens leaves one
    space (it kept them apart) and one at either end of the line nothing."""
    keep = []
    for line in text.split("\n"):
        if _MARK in line:
            if not line.replace(_MARK, "").strip():
                continue
            line = _gaps(line)
        keep.append(line)
    return "\n".join(keep)


def strip_js(text):
    out = []
    _code(text, 0, out, False)
    return _tidy("".join(out))


_CSS_NEXT = re.compile(r"[\"']|/\*")


def strip_css(text):
    out, i, n = [], 0, len(text)
    while i < n:
        m = _CSS_NEXT.search(text, i)
        if not m:
            out.append(text[i:])
            break
        j = m.start()
        out.append(text[i:j])
        if text[j] in "\"'":
            q, k = text[j], j + 1
            while k < n and text[k] != q and text[k] != "\n":
                k += 2 if text[k] == "\\" else 1
            out.append(text[j:k + 1])
            i = k + 1
        else:
            k = text.find("*/", j + 2)
            k = n if k < 0 else k + 2
            out.append(_MARK + "\n" if "\n" in text[j:k] else _MARK)
            i = k
    return _tidy("".join(out))


_HTML_RAW = re.compile(r"<(script|style|textarea|pre)\b[^>]*>(.*?)</\1\s*>", re.S | re.I)
# A comment of capitals alone is a place the server writes into
# (<!--BANNER-->), and stays.
_HTML_COMMENT = re.compile(r"<!--(?![A-Z_]+-->).*?-->", re.S)


def strip_html(text):
    """HTML comments left out, outside script, style, textarea and pre, but
    a placeholder the server writes into; an inline script's and style's own
    comments as the files' are."""
    out, i = [], 0
    for m in _HTML_RAW.finditer(text):
        out.append(_HTML_COMMENT.sub(_MARK, text[i:m.start()]))
        tag, body = m.group(1).lower(), m.group(2)
        head = text[m.start():m.start(2)]
        tail = text[m.end(2):m.end()]
        if tag == "script" and "src=" not in head:
            body = strip_js(body)
        elif tag == "style":
            body = strip_css(body)
        out.append(head + body + tail)
        i = m.end()
    out.append(_HTML_COMMENT.sub(_MARK, text[i:]))
    return _tidy("".join(out))


# What each page file is as served, kept by what it is on disk.
_kept = {}
_kept_lock = threading.Lock()


def served(path):
    """The bytes a page file (.js, .css, .html) is served as: without its
    comments, kept while the file stays the same; the file's own bytes for
    anything else, or when stripping fails (never a broken page for a
    smaller one)."""
    st = os.stat(path)
    sig = (st.st_ino, st.st_size, st.st_mtime_ns)
    with _kept_lock:
        got = _kept.get(path)
    if got and got[0] == sig:
        return got[1]
    with open(path, "rb") as f:
        raw = f.read()
    body = raw
    kind = os.path.splitext(path)[1]
    strip = {".js": strip_js, ".css": strip_css, ".html": strip_html}.get(kind)
    if strip:
        try:
            body = strip(raw.decode("utf-8")).encode("utf-8")
        except (UnicodeDecodeError, RecursionError, ValueError):
            body = raw
    with _kept_lock:
        if len(_kept) > 512:
            _kept.clear()
        _kept[path] = (sig, body)
    return body
