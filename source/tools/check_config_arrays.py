#!/usr/bin/env python3
"""Guard: settings value arrays must stay ASCII.

Swiss reuses the same string arrays for both display and swiss.ini persistence:

    fprintf(fp, "FileBrowserType=%s", fileBrowserTypeStr[...]);   // write
    if (!strcmp(fileBrowserTypeStr[i], value)) ...                // read

Translating those arrays silently breaks config parsing: existing files no
longer match and every affected setting falls back to its default. This script
cross-checks config.c against the array definitions and fails if any
config-participating array contains a non-ASCII literal.

Usage: python tools/check_config_arrays.py
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


def arrays_used_by_config():
    names = set()
    cfg = os.path.join(SRC, "config", "config.c")
    text = open(cfg, encoding="utf-8", errors="replace").read()
    # strcmp(xxxStr[i], value)   and   fprintf(..., "%s", xxxStr[...
    names.update(re.findall(r"strcmp\(\s*(\w+)\[i\],\s*value\)", text))
    names.update(re.findall(r'"%s[^"]*"\s*,\s*(\w+)\[', text))
    return names


def array_definitions():
    defs = {}
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d != "littlefs"]
        for name in files:
            if not name.endswith(".c"):
                continue
            path = os.path.join(root, name)
            text = open(path, encoding="utf-8", errors="replace").read()
            for m in re.finditer(r"char\s+\*(\w+)\[\]\s*=\s*\{(.*?)\};", text, re.S):
                defs[m.group(1)] = (os.path.relpath(path, SRC).replace("\\", "/"), m.group(2))
    return defs


def main():
    used = arrays_used_by_config()
    defs = array_definitions()
    print(f"config-participating arrays: {len(used)}")

    bad = 0
    missing = []
    for name in sorted(used):
        if name not in defs:
            missing.append(name)
            continue
        where, body = defs[name]
        offenders = sorted({ch for ch in body if ord(ch) > 0x7F})
        if offenders:
            bad += 1
            print(f"  FAIL {name}  ({where})  non-ASCII: {''.join(offenders)}")
    if missing:
        print(f"  note: no definition found for {', '.join(missing)}")

    if bad:
        print("\nThese arrays are written to and read from swiss.ini.")
        print("Revert the translations or config parsing will fall back to defaults.")
        return 1
    print("OK: every config array is ASCII-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
