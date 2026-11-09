#!/usr/bin/env python3
"""Extract hardcoded UI strings from the Swiss source tree.

Strategy: lexical scan (comments/strings aware) + call-site analysis.
Only string literals that actually reach a UI drawing API are collected,
which avoids the thousands of lookup-table strings in nkit.c / tzdata.c.
"""
import os
import re
import csv
import sys
import json
from collections import OrderedDict

def _env_path(var, default_rel):
    """Resolve a workspace path; override with an env var on other machines."""
    import os
    from pathlib import Path
    base = Path(os.environ.get(
        "SWISS_GC_WORKSPACE", str(Path(__file__).resolve().parents[3])))
    return Path(os.environ[var]) if os.environ.get(var) else base / default_rel


SRC_ROOT = str(_env_path("SWISS_GC_SRC", "swiss-gc/cube/swiss/source"))
OUT_DIR = str(_env_path("SWISS_I18N_OUT", "swiss-gc-CN/out"))

# Functions whose const char* arguments are rendered on screen.
UI_FUNCS = {
    "drawString", "drawStringWithCaret", "drawStringEllipsis",
    "DrawLabel", "DrawStyledLabel", "DrawStyledLabelWithCaret",
    "DrawStyledLabelEllipsis", "DrawFadingLabel",
    "DrawMessageBox", "DrawSelectableButton", "DrawTooltip",
    "DrawProgressBar", "DrawFileBrowserButton", "DrawFileBrowserButtonMeta",
    "DrawFileCarouselEntry", "DrawArgsSelector", "DrawCheatsSelector",
    "DrawGetTextEntry",
    "drawSettingEntryString", "drawSettingEntryBoolean", "drawSettingEntryInt",
    "drawSettingEntryEnum",
    # internal helpers that end up in DrawLabel/drawString
    "DrawDynamicLabelText",
}

# Buffers that are painted on screen after being filled by sprintf/strcpy.
DISPLAY_BUFFERS = {
    "fbTextBuffer", "txtbuffer", "sramHOffsetStr", "sramTemperatureStr",
    "uiVModeStr", "appsVModeStr", "msgBuffer", "strbuf",
}

TOKEN_RE = re.compile(r"""
    (?P<ws>\s+)
  | (?P<str>"(?:\\.|[^"\\])*")
  | (?P<chr>'(?:\\.|[^'\\])*')
  | (?P<id>[A-Za-z_]\w*)
  | (?P<num>0[xX][0-9a-fA-F]+|\d+\.?\d*[fFuUlL]*)
  | (?P<op>[{}\[\]()<>=+\-*/%&|^!~?:;,.])
""", re.X)

ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\", '"': '"', "'": "'"}


def decode_c_string(raw):
    """raw includes the surrounding quotes"""
    body = raw[1:-1]
    out = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        i += 1
        if i >= len(body):
            break
        e = body[i]
        if e in ESCAPES:
            out.append(ESCAPES[e])
            i += 1
        elif e == "x":
            m = re.match(r"[0-9a-fA-F]{1,2}", body[i + 1:])
            if m:
                val = int(m.group(0), 16)
                out.append(chr(val) if val < 0x80 else bytes([val]).decode("cp1252", "replace"))
                i += 1 + len(m.group(0))
            else:
                i += 1
        elif e.isdigit():
            m = re.match(r"[0-7]{1,3}", body[i:])
            val = int(m.group(0), 8)
            if val < 0x80:
                out.append(chr(val))
            else:
                # source uses Win-1252 bytes (0x85 = …, 0x93/0x94 = curly quotes)
                out.append(bytes([val & 0xFF]).decode("cp1252", "replace"))
            i += len(m.group(0))
        else:
            out.append(e)
            i += 1
    return "".join(out)


def strip_comments_keep_lines(text):
    """Replace comments with spaces, preserving newlines so line numbers stay valid."""
    out = []
    i, n = 0, len(text)
    state = None
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if state is None:
            if ch == "/" and nxt == "/":
                state = "line"
                out.append("  ")
                i += 2
                continue
            if ch == "/" and nxt == "*":
                state = "block"
                out.append("  ")
                i += 2
                continue
            if ch == '"':
                state = "str"
                out.append(ch)
                i += 1
                continue
            if ch == "'":
                state = "chr"
                out.append(ch)
                i += 1
                continue
            out.append(ch)
            i += 1
        elif state == "line":
            if ch == "\n":
                state = None
                out.append("\n")
            else:
                out.append(" ")
            i += 1
        elif state == "block":
            if ch == "*" and nxt == "/":
                state = None
                out.append("  ")
                i += 2
                continue
            out.append("\n" if ch == "\n" else " ")
            i += 1
        elif state in ("str", "chr"):
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if (state == "str" and ch == '"') or (state == "chr" and ch == "'"):
                state = None
            i += 1
    return "".join(out)


def tokenize(text):
    toks = []
    line = 1
    for m in TOKEN_RE.finditer(text):
        kind = m.lastgroup
        val = m.group(0)
        if kind == "ws":
            line += val.count("\n")
            continue
        toks.append((kind, val, line))
        line += val.count("\n")
    return toks


def find_calls(toks):
    """Yield (callee, [arg_token_lists], line) for every CALL(args) construct."""
    i = 0
    n = len(toks)
    while i < n:
        kind, val, line = toks[i]
        if kind == "id" and i + 1 < n and toks[i + 1][1] == "(":
            callee = val
            j = i + 2
            depth = 1
            args = []
            cur = []
            while j < n:
                k2, v2, _ = toks[j]
                if k2 == "op" and v2 in "([{":
                    depth += 1
                    cur.append(toks[j])
                elif k2 == "op" and v2 in ")]}":
                    depth -= 1
                    if depth == 0:
                        break
                    cur.append(toks[j])
                elif k2 == "op" and v2 == "," and depth == 1:
                    args.append(cur)
                    cur = []
                else:
                    cur.append(toks[j])
                j += 1
            if cur:
                args.append(cur)
            yield callee, args, line
            # keep scanning from the next token so nested calls inside the
            # arguments are parsed too (e.g. DrawAddChild(p, DrawLabel(..., "x")))
            i += 1
        else:
            i += 1


def literals_in(arg):
    """Decode each string literal separately, then concatenate (C semantics)."""
    parts = [t[1] for t in arg if t[0] == "str"]
    if not parts:
        return None
    return "".join(decode_c_string(p) for p in parts)


def collect_array_defs(toks):
    """Find `char *name[] = { "a", "b", ... }` style definitions.

    Returns {name: [(line, text), ...]} using the line of each element.
    """
    arrays = {}
    i = 0
    n = len(toks)
    while i < n:
        kind, val, _ = toks[i]
        if kind == "id" and val not in ("const", "static", "char", "unsigned"):
            # look ahead for '[' ']' '=' '{'
            j = i + 1
            if j + 2 < n and toks[j][1] == "[" and toks[j + 1][1] == "]" and toks[j + 2][1] == "=":
                k = j + 3
                if k < n and toks[k][1] == "{":
                    items = []
                    cur = []
                    depth = 1
                    k += 1
                    while k < n and depth > 0:
                        if toks[k][1] == "{":
                            depth += 1
                        elif toks[k][1] == "}":
                            depth -= 1
                            if depth == 0:
                                break
                        elif toks[k][1] == "," and depth == 1:
                            if cur:
                                items.append(cur)
                            cur = []
                            k += 1
                            continue
                        cur.append(toks[k])
                        k += 1
                    if cur:
                        items.append(cur)
                    found = []
                    for it in items:
                        s = literals_in(it)
                        if s is not None:
                            found.append((it[0][2] if it else 0, s))
                    if found:
                        arrays[val] = found
                    i = k
        i += 1
    return arrays


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    records = []   # dict: file, line, func, text, kind
    array_defs = {}
    file_calls = {}

    files = []
    for dirpath, _, names in os.walk(SRC_ROOT):
        if "littlefs" in dirpath:      # bundled 3rd party, no UI
            continue
        for nm in names:
            if nm.endswith((".c", ".h")):
                files.append(os.path.join(dirpath, nm))
    files.sort()

    for path in files:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        clean = strip_comments_keep_lines(text)
        toks = tokenize(clean)
        rel = os.path.relpath(path, SRC_ROOT).replace("\\", "/")

        # array definitions (display lookup tables)
        for name, vals in collect_array_defs(toks).items():
            array_defs.setdefault(name, []).extend([(rel, ln, v) for ln, v in vals])

        calls = list(find_calls(toks))
        file_calls[rel] = calls

        for callee, args, line in calls:
            if callee not in UI_FUNCS:
                continue
            for arg in args:
                lit = literals_in(arg)
                if lit is None:
                    continue
                records.append({
                    "file": rel, "line": line, "func": callee,
                    "text": lit, "kind": "direct",
                })

        # strings formatted into a buffer that later gets painted on screen
        for callee, args, line in calls:
            if callee not in ("sprintf", "snprintf", "strcpy", "strncpy", "strcat", "stpcpy"):
                continue
            if not args:
                continue
            dst = [t[1] for t in args[0] if t[0] == "id"]
            if not dst:
                continue
            target = dst[0]
            if target in DISPLAY_BUFFERS or re.search(r"(?i)(buffer|str)$", target):
                for arg in args[1:]:
                    lit = literals_in(arg)
                    if lit is None:
                        continue
                    if re.fullmatch(r"[%\w\s./:+\-]*", lit) and "%" not in lit:
                        continue
                    records.append({
                        "file": rel, "line": line, "func": f"{callee}({target})",
                        "text": lit, "kind": "formatted",
                    })

    # second pass: string arrays referenced inside UI calls
    for rel, calls in file_calls.items():
        for callee, args, line in calls:
            if callee not in UI_FUNCS:
                continue
            for arg in args:
                for kind, val, _ in arg:
                    if kind == "id" and val in array_defs:
                        for (arel, aline, s) in array_defs[val]:
                            records.append({
                                "file": arel, "line": aline, "func": f"{callee}({val}[])",
                                "text": s, "kind": "array",
                            })

    # dedup, keep first site and count
    uniq = OrderedDict()
    for r in records:
        key = r["text"]
        if key not in uniq:
            uniq[key] = {"text": key, "sites": [], "kinds": set(), "funcs": set()}
        u = uniq[key]
        if len(u["sites"]) < 6:
            u["sites"].append((r["file"], r["line"]))
        u["kinds"].add(r["kind"])
        u["funcs"].add(r["func"])

    def is_translatable(s):
        if s.strip() == "":
            return False
        # drop strings that are nothing but conversion specifiers / punctuation
        stripped = re.sub(r"%[-+ #0]*[\d.*]*(hh|h|ll|l|j|z|t|L)?[diouxXeEfgGcsSpn%]", "", s)
        if len(re.sub(r"[^A-Za-z]", "", stripped)) < 2:
            return False
        return True

    def categorize(s):
        """translate = user-visible prose; keep = numbers/model names; review = mixed."""
        if re.search(r"(?i)^(nintendo gamecube|npdp-|ibm |artx )", s):
            return "keep"
        # standards / units / button combos are never translated
        if s.upper() in ("NTSC", "PAL", "PAL-M", "MPAL", "TAA"):
            return "keep"
        if re.fullmatch(r"[\d.]+\s*(Hz|kHz|MHz|GHz|fps|%)", s):
            return "keep"
        # no lowercase + contains a digit or symbol -> unit or button combo (120Hz, X&Y)
        if not re.search(r"[a-z]", s) and (re.search(r"\d", s) or re.search(r"[^A-Za-z ]", s)):
            return "keep"
        # mostly a format specifier with a tiny literal fragment
        if "%" in s:
            plain = re.sub(r"%[-+ #0]*[\d.*]*(hh|h|ll|l|j|z|t|L)?[diouxXeEfgGcsSpn%]", "", s)
            if len(re.sub(r"[^A-Za-z]", "", plain)) < 4:
                return "review"
        return "translate"

    items = [v for v in uniq.values() if is_translatable(v["text"])]
    items.sort(key=lambda x: (-len(x["sites"]), x["text"]))

    raw_csv = os.path.join(OUT_DIR, "ui_strings_raw.csv")
    with open(raw_csv, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "source_en", "occurrences", "category", "kind", "api",
                    "first_file", "first_line", "sites"])
        for i, it in enumerate(items, 1):
            t = it["text"]
            w.writerow([
                i, t, len(it["sites"]), categorize(t),
                ",".join(sorted(it["kinds"])),
                ",".join(sorted(it["funcs"]))[:120],
                it["sites"][0][0] if it["sites"] else "",
                it["sites"][0][1] if it["sites"] else "",
                "; ".join(f"{f}:{l}" for f, l in it["sites"][:6]),
            ])

    # stats
    total_lit = 0
    for path in files:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            clean = strip_comments_keep_lines(fh.read())
            total_lit += sum(1 for t in tokenize(clean) if t[0] == "str")

    stats = {
        "files_scanned": len(files),
        "string_literals_in_tree": total_lit,
        "ui_strings_unique": len(items),
        "ui_strings_occurrences": len(records),
        "with_format_specifier": sum(1 for it in items if "%" in it["text"]),
        "max_len": max((len(it["text"]) for it in items), default=0),
    }
    with open(os.path.join(OUT_DIR, "stats.json"), "w", encoding="utf-8") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=2)

    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print("wrote", raw_csv)


if __name__ == "__main__":
    main()
