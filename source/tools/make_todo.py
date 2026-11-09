#!/usr/bin/env python3
"""Build the translation checklist from the extracted UI strings.

Outputs:
  out/TODO_translate.csv   - machine readable, zh column left empty
  out/TODO_translate.md    - grouped by source file, with checkboxes
  out/charset_estimate.json
"""
import csv
import json
import os
import re
from collections import OrderedDict, defaultdict

def _env_path(var, default_rel):
    """Resolve a workspace path; override with an env var on other machines."""
    import os
    from pathlib import Path
    base = Path(os.environ.get(
        "SWISS_GC_WORKSPACE", str(Path(__file__).resolve().parents[3])))
    return Path(os.environ[var]) if os.environ.get(var) else base / default_rel


OUT = str(_env_path("SWISS_I18N_OUT", "swiss-gc-CN/out"))

# Average advance of the IPL ANSI font at scale 1.0 (proportional, measured
# from the width table behaviour in SYS_GetFontWidth; ~8px for mixed text).
ASCII_ADV = 8.0
CJK_W = 16.0


def load():
    with open(os.path.join(OUT, "ui_strings_raw.csv"), encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def budget(en):
    """How many 16px CJK glyphs fit in the space the English text occupies."""
    n = max(1, int(len(en) * ASCII_ADV / CJK_W))
    return n


def needs_placeholders(en):
    return sorted(set(re.findall(r"%[-+ #0]*[\d.*]*(?:hh|h|ll|l|j|z|t|L)?[diouxXeEfgGcsSpn]", en)))


def main():
    rows = load()
    os.makedirs(OUT, exist_ok=True)

    work = [r for r in rows if r["category"] in ("translate", "review")]

    csv_path = os.path.join(OUT, "TODO_translate.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "source_en", "zh_cn", "category", "en_len", "zh_budget",
                    "placeholders", "newlines", "file", "line", "sites"])
        for r in work:
            en = r["source_en"]
            w.writerow([
                r["id"], en, "", r["category"], len(en), budget(en),
                " ".join(needs_placeholders(en)),
                en.count("\n"),
                r["first_file"], r["first_line"], r["sites"],
            ])

    # group by file for the human-facing checklist
    grouped = OrderedDict()
    for r in work:
        grouped.setdefault(r["first_file"], []).append(r)

    md = []
    md.append("# Swiss 汉化 · 待翻译清单\n")
    md.append(f"共 **{len(work)}** 条待翻译字符串（`translate` {sum(1 for r in work if r['category']=='translate')} 条，"
              f"`review` {sum(1 for r in work if r['category']=='review')} 条），来自 {len(grouped)} 个源文件。\n")
    md.append("长度预算 `≈` 列 = 按英文占用的像素宽度折算出的汉字数上限（16px 汉字 / 8px 平均 ASCII 宽），"
              "超过会挤压同行的其它控件。\n")
    md.append("> `%s` `%d` 等占位符必须原样保留，顺序可调整。`\\n` 是硬换行，翻译时需保留行数。\n")

    for f, items in grouped.items():
        md.append(f"\n## `{f}` （{len(items)} 条）\n")
        md.append("| # | 原文 | 译文 | ≈字数 | 约束 |")
        md.append("|---|---|---|---|---|")
        for r in items:
            en = r["source_en"].replace("|", "\\|").replace("\n", "\\n")
            ph = needs_placeholders(r["source_en"])
            cons = []
            if ph:
                cons.append("占位符 " + " ".join(f"`{p}`" for p in ph))
            if "\n" in r["source_en"]:
                cons.append(f"换行×{r['source_en'].count(chr(10))}")
            md.append(f"| {r['id']} | `{en}` |  | {budget(r['source_en'])} | {' '.join(cons)} |")

    md_path = os.path.join(OUT, "TODO_translate.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")

    # charset estimate: distinct CJK chars will only be known once zh is filled in
    stats = {
        "strings_total": len(rows),
        "strings_to_translate": len(work),
        "strings_keep": sum(1 for r in rows if r["category"] == "keep"),
        "files": len(grouped),
        "en_chars_total": sum(len(r["source_en"]) for r in work),
        "zh_budget_total_cjk": sum(budget(r["source_en"]) for r in work),
    }
    with open(os.path.join(OUT, "charset_estimate.json"), "w", encoding="utf-8") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=2)

    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print("wrote", csv_path)
    print("wrote", md_path)


if __name__ == "__main__":
    main()
