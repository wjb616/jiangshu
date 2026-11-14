#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清洗后文本质量检查
用法：python check_quality.py <清洗后目录>
输出：正常 / 可疑 / 乱码 / 空  四类清单
"""
import sys
import re
from pathlib import Path

CJK = re.compile(r"[\u4e00-\u9fff]")
EN_WORDS = re.compile(r"\b(the|and|of|in|to|for|with|is|are)\b", re.IGNORECASE)
GARBLE = re.compile(r"[ǓȞǑȘȚɑ-ʯ̀-ͯ]")


def check(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    n = len(text)
    if n < 300:
        return "空/扫描件", n, 0, 0

    cjk = len(CJK.findall(text))
    en = len(EN_WORDS.findall(text))
    garble = len(GARBLE.findall(text))

    cjk_ratio = cjk / n
    en_density = en / n * 1000
    garble_ratio = garble / n

    if garble_ratio > 0.02 or (cjk_ratio < 0.05 and en_density < 3):
        return "乱码", n, cjk_ratio, en_density
    if cjk_ratio > 0.15 or en_density > 5:
        return "正常", n, cjk_ratio, en_density
    return "可疑", n, cjk_ratio, en_density


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    split = "--split" in sys.argv
    if not args:
        print(__doc__)
        sys.exit(1)

    d = Path(args[0])
    files = sorted(d.glob("*.txt"))
    if not files:
        print(f"{d} 下没有 txt")
        return

    buckets = {"正常": [], "可疑": [], "乱码": [], "空/扫描件": []}
    for f in files:
        label, n, cjk, en = check(f)
        buckets[label].append((f.name, n, cjk, en))

    for label in ("正常", "可疑", "乱码", "空/扫描件"):
        items = buckets[label]
        print(f"\n{'='*60}\n{label}：{len(items)} 个\n{'='*60}")
        for name, n, cjk, en in items:
            print(f"  {n:>7} 字符  中文{cjk*100:>4.0f}%  英文{en:>5.1f}/千字  {name}")

    total = len(files)
    print(f"\n合计 {total} 个：正常 {len(buckets['正常'])}，"
          f"可疑 {len(buckets['可疑'])}，乱码 {len(buckets['乱码'])}，"
          f"空 {len(buckets['空/扫描件'])}")

    if split:
        import shutil
        ok_dir = d / "_可用"
        bad_dir = d / "_需OCR"
        ok_dir.mkdir(exist_ok=True)
        bad_dir.mkdir(exist_ok=True)
        for label in ("正常", "可疑"):
            for name, _, _, _ in buckets[label]:
                shutil.copy2(d / name, ok_dir / name)
        for label in ("乱码", "空/扫描件"):
            for name, _, _, _ in buckets[label]:
                shutil.copy2(d / name, bad_dir / name)
        print(f"\n已分类：\n  可用 -> {ok_dir}\n  需OCR -> {bad_dir}")


if __name__ == "__main__":
    main()
