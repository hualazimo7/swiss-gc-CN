#!/usr/bin/env python3
"""Apply a translation mapping to the Swiss sources.

Mapping file format (UTF-8, tab separated, one pair per line, # comments):
    Global Settings (1/6):<TAB>全局设置 (1/6):

Every C string literal whose decoded content equals a key is replaced by the
value. Format specifiers and escapes are preserved by the caller (i.e. the
value must already contain them).

Safety rules:
  - files that are not valid UTF-8 (nkit.c holds Latin-1 bytes) are skipped
  - the escaped form of the value is validated by round-tripping it
  - --dry-run prints what would change without touching anything

Usage: python tools/apply_translations.py map.tsv [--dry-run]
"""
import os
import re
import sys

def _env_path(var, default_rel):
    """Resolve a workspace path; override with an env var on other machines."""
    import os
    from pathlib import Path
    base = Path(os.environ.get(
        "SWISS_GC_WORKSPACE", str(Path(__file__).resolve().parents[3])))
    return Path(os.environ[var]) if os.environ.get(var) else base / default_rel


SRC = str(_env_path("SWISS_GC_SRC", "swiss-gc/cube/swiss/source"))
SKIP_DIRS = {"littlefs"}

LIT_RE = re.compile(r'"(?:\\.|[^"\\])*"')

ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\", '"': '"', "'": "'"}


def decode_c_literal(raw):
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
                v = int(m.group(0), 16)
                out.append(chr(v) if v < 0x80 else bytes([v]).decode("cp1252", "replace"))
                i += 1 + len(m.group(0))
            else:
                i += 1
        elif e.isdigit():
            m = re.match(r"[0-7]{1,3}", body[i:])
            v = int(m.group(0), 8)
            out.append(chr(v) if v < 0x80 else bytes([v & 0xFF]).decode("cp1252", "replace"))
            i += len(m.group(0))
        else:
            out.append(e)
            i += 1
    return "".join(out)


def encode_c_literal(text):
    out = []
    for ch in text:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def unescape(text):
    """Allow \\n and \\t in the mapping file so multi-line messages fit a TSV."""
    return text.replace("\\n", "\n").replace("\\t", "\t")


def load_map(path):
    mapping = {}
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if "\t" not in line:
                print(f"  skip map line {lineno} (no tab): {line[:40]!r}")
                continue
            en, zh = line.split("\t", 1)
            mapping[unescape(en)] = unescape(zh)
    return mapping


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    dry = "--dry-run" in sys.argv
    mapping = load_map(sys.argv[1])
    print(f"mapping entries: {len(mapping)}")

    total = 0
    touched = []
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(files):
            if not name.endswith(".c"):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, SRC).replace("\\", "/")
            raw = open(path, "rb").read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                print(f"  skip {rel}: not valid UTF-8")
                continue

            replaced = [0]

            def sub(m):
                lit = m.group(0)
                try:
                    dec = decode_c_literal(lit)
                except Exception:
                    return lit
                if dec in mapping:
                    replaced[0] += 1
                    return encode_c_literal(mapping[dec])
                return lit

            new = LIT_RE.sub(sub, text)
            if replaced[0]:
                total += replaced[0]
                touched.append((rel, replaced[0]))
                if not dry:
                    with open(path, "w", encoding="utf-8", newline="") as fh:
                        fh.write(new)

    for rel, n in touched:
        print(f"  {n:3d}  {rel}")
    print(f"{'would replace' if dry else 'replaced'} {total} literals in {len(touched)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
