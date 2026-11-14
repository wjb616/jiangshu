#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
整理知识库目录：
1. 原始 PDF 移到 _原始PDF归档/
2. 清洗后的 txt 按统一格式重命名，放入 01_清洗后文献/
3. 乱码/扫描件的 txt 放入 _需OCR/
用法：python organize.py <原PDF目录> <清洗后目录>
"""
import sys
import re
import shutil
from pathlib import Path

ILLEGAL = re.compile(r'[\\/:*?"<>|\r\n\t]')
DOMAIN = re.compile(r'^[a-z0-9.\-]+\.[a-z]{2,6}$')


def is_domain(part: str) -> bool:
    p = part.lower()
    return bool(DOMAIN.match(p)) or p in ("www",)


def kind_of(name: str) -> str:
    n = name.lower()
    if "标准" in name or "gbt" in n or "gb/t" in n or "osta" in n:
        return "标准"
    if "手册" in name or "manual" in n or "handbook" in n:
        return "手册"
    if ("教材" in name or "样章" in name or "基础" in name
            or "职业技术学院" in name or "教程" in name):
        return "教材"
    if "专利" in name or "cn1" in n or "cn2" in n:
        return "专利"
    return "论文"


def clean_title(stem: str) -> str:
    t = re.sub(r"^\d{3}_", "", stem)          # 去序号
    t = re.sub(r"[（(]\d{4}[)）]", "", t)      # 去年份括号
    parts = t.split("_")
    while parts and is_domain(parts[-1]):      # 去域名尾巴
        parts.pop()
    t = "_".join(parts)
    t = t.replace("_", " ")
    t = re.sub(r"[（(][^）)]*$", "", t)         # 去未闭合括号及其后内容
    t = re.sub(r"\s{2,}", " ", t).strip(" -_.·")
    return t


def get_year(stem: str, text: str) -> str:
    m = re.search(r"[（(](\d{4})[)）]", stem)
    if m:
        return m.group(1)
    m = re.search(r"\b(19[89]\d|20[0-4]\d)\b", text[:3000])
    if m:
        return m.group(1)
    return ""


def safe(name: str) -> str:
    return ILLEGAL.sub(" ", name).strip()


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    src_pdf = Path(sys.argv[1])
    src_clean = Path(sys.argv[2])
    base = src_pdf

    ok_txt = src_clean / "_可用"
    bad_txt = src_clean / "_需OCR"
    if not ok_txt.exists():
        print(f"[错误] 找不到 {ok_txt}，请先跑 check_quality.py --split")
        sys.exit(1)

    out_dir = base / "01_清洗后文献"
    arc_dir = base / "_原始PDF归档"
    ocr_dir = base / "_需OCR"
    for d in (out_dir, arc_dir, ocr_dir):
        d.mkdir(exist_ok=True)

    # 1) 归位并重命名清洗后的 txt
    used = set()
    count = 0
    for f in sorted(ok_txt.glob("*.txt")):
        stem = f.stem
        if stem.endswith("_clean"):
            stem = stem[:-6]
        text = f.read_text(encoding="utf-8", errors="ignore")

        num_m = re.match(r"^(\d{3})_", stem)
        num = num_m.group(1) if num_m else ""
        kind = kind_of(stem)
        title = safe(clean_title(stem))[:80]
        year = get_year(stem, text)

        parts = [p for p in (num, kind, title) if p]
        new = "_".join(parts)
        if year:
            new += f"_{year}"
        if not new:
            new = f.file.name
        # 防重名
        base_name, k = new, 2
        while base_name in used:
            base_name = f"{new}_{k}"
            k += 1
        used.add(base_name)

        shutil.copy2(f, out_dir / (base_name + ".txt"))
        count += 1

    # 2) 乱码 txt 归到 _需OCR
    bad = 0
    if bad_txt.exists():
        for f in bad_txt.glob("*.txt"):
            shutil.copy2(f, ocr_dir / f.name)
            bad += 1

    # 3) 原始 PDF 归档（移动，不删除）
    moved = 0
    for pattern in ("*.pdf",):
        for f in src_pdf.glob(pattern):
            target = arc_dir / f.name
            if target.exists():
                continue
            shutil.move(str(f), str(target))
            moved += 1

    print(f"[完成]")
    print(f"  重命名文献  {count} 个 -> {out_dir}")
    print(f"  需OCR       {bad} 个 -> {ocr_dir}")
    print(f"  原始PDF归档 {moved} 个 -> {arc_dir}")
    print(f"\n保留未动的：清单/ 图片/ 注塑缺陷知识卡_v1.md 注塑专利6篇_全文.*")


if __name__ == "__main__":
    main()
