#!/usr/bin/env python3
"""Collect the CJK charset actually used by the translation.

Reads out/TODO_translate.csv, takes every non-ASCII codepoint from the zh_cn
column, and writes out/charset.txt (sorted, one codepoint per line) plus a
stats summary. Optionally merges an extra allow-list file (e.g. GB2312 level-1).
"""
import csv
import json
import os
import sys
from collections import Counter

def _env_path(var, default_rel):
    """Resolve a workspace path; override with an env var on other machines."""
    import os
    from pathlib import Path
    base = Path(os.environ.get(
        "SWISS_GC_WORKSPACE", str(Path(__file__).resolve().parents[3])))
    return Path(os.environ[var]) if os.environ.get(var) else base / default_rel


OUT = str(_env_path("SWISS_I18N_OUT", "swiss-gc-CN/out"))


def main():
    todo = os.path.join(OUT, "TODO_translate.csv")
    with open(todo, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))

    filled = [r for r in rows if r.get("zh_cn", "").strip()]
    if not filled:
        print("zh_cn 列还是空的：先把译文填进 TODO_translate.csv 再跑这个脚本。")
        return 1

    counter = Counter()
    for r in filled:
        for ch in r["zh_cn"]:
            if ord(ch) > 0x7F:
                counter[ch] += 1

    extra = []
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        with open(sys.argv[1], encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                for ch in line:
                    if ord(ch) > 0x7F:
                        extra.append(ch)

    chars = sorted(set(counter) | set(extra))
    out_txt = os.path.join(OUT, "charset.txt")
    with open(out_txt, "w", encoding="utf-8") as fh:
        fh.write("".join(chars))

    stats = {
        "strings_translated": len(filled),
        "strings_total": len(rows),
        "cjk_instances": sum(counter.values()),
        "distinct_cjk": len(counter),
        "with_extra_allowlist": len(chars),
        "source_data_kb_16x16": round(len(chars) * 32 / 1024, 1),
    }
    with open(os.path.join(OUT, "charset_stats.json"), "w", encoding="utf-8") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=2)

    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print("wrote", out_txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
