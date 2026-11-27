"""State 37 to 38: every design record in today's shape.

design.py read three older shapes and never wrote them back: a language from
before themes (one scheme and its ten colors, 29 Sep), choices and rules
kept on the language rather than on its themes (before 29 Sep), and notes
from before rules, one string (28 Sep); and a page saved before pages had
rules of their own. Each is written here as design.py read it on 27 Nov, with
its palettes copied in as they stood then (a migration never reads a module,
which moves on), and the readers go (R205, R295).

Idempotent. Never edited once shipped (stateversion.py).
"""
import json
import os
from pathlib import Path

# design.SCHEMES and design.TOKENS on 27 Nov 2026.
SCHEMES = [('default', 'Default', {'bg': '#172136', 'panel': '#24314b', 'line': '#455e89', 'ink': '#edf4ff', 'dim': '#b2c2db', 'accent': '#00c1fd', 'warn': '#d29922', 'bad': '#f8524a', 'note': '#37a5fb', 'good': '#56d364'}), ('abyss', 'Abyss', {'bg': '#152428', 'panel': '#22353a', 'line': '#3f646e', 'ink': '#e7f7f9', 'dim': '#adc6ca', 'accent': '#00d3e4', 'warn': '#d7ab4c', 'bad': '#ef6a63', 'note': '#eb69df', 'good': '#4fd1a1'}), ('ash', 'Ash', {'bg': '#1b1b1b', 'panel': '#222322', 'line': '#555955', 'ink': '#e2e4e0', 'dim': '#a1a59f', 'accent': '#a3b18a', 'warn': '#cfa94a', 'bad': '#e26d60', 'note': '#82a7b8', 'good': '#9ccf8a'}), ('carbon', 'Carbon', {'bg': '#212127', 'panel': '#313138', 'line': '#5c5c69', 'ink': '#f3f3f5', 'dim': '#c0c0c8', 'accent': '#ff6a6b', 'warn': '#d9a441', 'bad': '#ff6b6b', 'note': '#00e2cd', 'good': '#57d17a'}), ('ember', 'Ember', {'bg': '#281f1a', 'panel': '#3a2f28', 'line': '#705940', 'ink': '#fdf1e5', 'dim': '#d0bdac', 'accent': '#ff7f08', 'warn': '#e8bb50', 'bad': '#ef5f52', 'note': '#00dee8', 'good': '#8fcf7a'}), ('ice', 'Ice', {'bg': '#1a2329', 'panel': '#27333c', 'line': '#486175', 'ink': '#ebf5fd', 'dim': '#b4c4cb', 'accent': '#00cffb', 'warn': '#d3ab52', 'bad': '#ee6a68', 'note': '#a685ff', 'good': '#5fd39a'}), ('linen', 'Linen (light)', {'bg': '#f6f1e8', 'panel': '#fffaf2', 'line': '#d5c9b6', 'ink': '#2b2620', 'dim': '#6f665b', 'accent': '#b5562a', 'warn': '#9a6a00', 'bad': '#b8322b', 'note': '#2d6a9f', 'good': '#2e8b57'}), ('mint', 'Mint (light)', {'bg': '#eef5f1', 'panel': '#ffffff', 'line': '#c3d6cb', 'ink': '#1d2a24', 'dim': '#5f6f67', 'accent': '#1f8a5b', 'warn': '#9a6a00', 'bad': '#c0392b', 'note': '#2a6f9e', 'good': '#2f9e6b'}), ('moss', 'Moss', {'bg': '#192520', 'panel': '#26362a', 'line': '#496552', 'ink': '#edf7ed', 'dim': '#b6c6b9', 'accent': '#00de7e', 'warn': '#d6ad4e', 'bad': '#e8695f', 'note': '#ad87ff', 'good': '#7fd67a'}), ('nocturne', 'Nocturne', {'bg': '#202030', 'panel': '#2f2f45', 'line': '#585886', 'ink': '#f3f2ff', 'dim': '#bfbce0', 'accent': '#a386ff', 'warn': '#e0b24d', 'bad': '#f2637b', 'note': '#00e5b2', 'good': '#6fd39a'}), ('nostromo', 'Nostromo', {'bg': '#1d2228', 'panel': '#29333c', 'line': '#50606e', 'ink': '#ecf5fd', 'dim': '#b4c3d2', 'accent': '#f6a900', 'warn': '#ffd166', 'bad': '#ff5f45', 'note': '#3da5f9', 'good': '#9ad07a'}), ('paper', 'Paper (light)', {'bg': '#f4f5f7', 'panel': '#ffffff', 'line': '#cfd4dc', 'ink': '#1f2328', 'dim': '#59636e', 'accent': '#0969da', 'warn': '#9a6700', 'bad': '#cf222e', 'note': '#0550ae', 'good': '#1a7f37'}), ('plum', 'Plum', {'bg': '#271d2e', 'panel': '#382c41', 'line': '#6d507d', 'ink': '#fbefff', 'dim': '#cdb8d7', 'accent': '#da6cef', 'warn': '#dfae52', 'bad': '#ee6183', 'note': '#2de78d', 'good': '#7fcf9a'}), ('rust', 'Rust', {'bg': '#291f1c', 'panel': '#3a2e2a', 'line': '#755450', 'ink': '#fef0ed', 'dim': '#cfbcb7', 'accent': '#ff6738', 'warn': '#d9a441', 'bad': '#e8544a', 'note': '#35e3b9', 'good': '#8fcf7a'}), ('sepia', 'Sepia', {'bg': '#262118', 'panel': '#373125', 'line': '#6b5b3f', 'ink': '#fef2dd', 'dim': '#cebfa6', 'accent': '#ebb000', 'warn': '#e3c069', 'bad': '#e0705f', 'note': '#00e2ce', 'good': '#9db98c'}), ('slate', 'Slate', {'bg': '#1d222b', 'panel': '#2b323e', 'line': '#525f6f', 'ink': '#eef4fb', 'dim': '#bac2cb', 'accent': '#569aff', 'warn': '#d9a441', 'bad': '#ef6f6c', 'note': '#97dd24', 'good': '#5fd39a'})]
TOKENS = [('bg', 'Background', 'the page'), ('panel', 'Surface', 'a raised box, a card, a bar'), ('ink', 'Text', 'the text'), ('dim', 'Muted', 'secondary text and labels'), ('line', 'Edge', 'hairlines and borders'), ('accent', 'Accent', 'the one color that means "this is the one": the active tab, the primary button, a link'), ('warn', 'Warning', 'a warning'), ('bad', 'Danger', 'an error, a destructive verb'), ('note', 'Note', 'an informational mark'), ('good', 'Good', 'success: a passing check, a legal move, a safe state')]
CARRIED = ("font", "corners", "density", "motion", "fonts", "custom")


def _luma(h):
    h = str(h).lstrip("#")
    try:
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return 0.0
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _theme_from(key, name=""):
    k, label, colors = next((row for row in SCHEMES if row[0] == key), SCHEMES[0])
    return {"name": name or label.replace(" (light)", ""), "mode": "light" if _luma(colors["bg"]) > 0.5 else "dark",
            "colors": [{"name": t, "hex": colors[t], "means": means} for t, _, means in TOKENS]}


def _rules(raw):
    """Notes from before rules, one string, as the one rule they were read as."""
    if isinstance(raw, str):
        return [{"name": "design-notes", "text": raw}] if raw.strip() else []
    return raw


def _language(lang):
    if not isinstance(lang, dict):
        return lang
    lang = dict(lang)
    if "themes" not in lang and ("colors" in lang or "scheme" in lang):
        keys = [row[0] for row in SCHEMES]
        scheme = str(lang.get("scheme") or "default")
        base = _theme_from(scheme if scheme in keys else "default", "Custom" if scheme not in keys else "")
        colors = lang.get("colors") if isinstance(lang.get("colors"), dict) else {}
        for c in base["colors"]:
            c["hex"] = str(colors.get(c["name"]) or c["hex"]).strip().lower()
        base["colors"] += [m for m in (lang.get("more") or []) if isinstance(m, dict)]
        lang["themes"] = [base]
    raw = lang.get("themes") if isinstance(lang.get("themes"), list) else []
    raw = [dict(t) if isinstance(t, dict) else t for t in raw]
    carried = {k: lang.get(k) for k in CARRIED if lang.get(k)}
    # Only a list on the language was carried: notes kept there as a string
    # were not read, so they are not kept.
    old_rules = lang.get("rules") if isinstance(lang.get("rules"), list) else []
    if (carried or old_rules) and not raw:
        raw = [{"name": "Default", "mode": "dark", "colors": []}]
    for i, t in enumerate(raw):
        if not isinstance(t, dict):
            continue
        for k, v in carried.items():
            if k == "custom" and i:
                continue
            if not t.get(k):
                t[k] = v
        t["rules"] = _rules(t.get("rules"))
        if i == 0 and old_rules:
            t["rules"] = old_rules + (t.get("rules") if isinstance(t.get("rules"), list) else [])
    out = {k: v for k, v in lang.items() if k not in CARRIED + ("colors", "scheme", "more", "rules")}
    out["themes"] = raw
    return out


def _record(rec):
    if not isinstance(rec, dict):
        return rec
    rec = dict(rec)
    if "language" in rec:
        rec["language"] = _language(rec.get("language"))
    if isinstance(rec.get("pages"), list):
        # A page's rules were read only as a list: anything else as none.
        rec["pages"] = [{**p, "rules": p.get("rules") if isinstance(p.get("rules"), list) else []}
                        if isinstance(p, dict) else p for p in rec["pages"]]
    return rec


def run(ctx):
    f = Path(ctx["state"]) / "designs.json"
    try:
        d = json.loads(f.read_text())
    except (OSError, ValueError):
        return
    if not isinstance(d, dict):
        return
    new = {k: _record(v) for k, v in d.items()}
    if new == d:
        return
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(new, indent=1))
    os.chmod(tmp, f.stat().st_mode & 0o777)
    os.replace(tmp, f)
