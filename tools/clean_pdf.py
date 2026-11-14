#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF 清洗工具 —— 匠枢知识库专用
用法：
    python clean_pdf.py <输入目录或文件> <输出目录>
依赖：
    pip install pymupdf

处理内容：
1. 去掉每页重复出现的页眉页脚
2. 去掉页码、DOI、URL、邮箱、版权声明行
3. 从 References / 参考文献 / 致谢 处截断
4. 合并 PDF 硬换行，恢复段落
5. 去掉完全重复的段落
"""

import sys
import re
from pathlib import Path
from collections import Counter

try:
    import pymupdf as fitz  # pymupdf >= 1.24
except ImportError:
    try:
        import fitz  # 旧版本
    except ImportError:
        print("[错误] 缺少依赖，请先执行: pip install pymupdf")
        sys.exit(1)

# ---------- 规则 ----------

# 参考文献起始标记（只在该行位于文档后半部分时生效）
REF_HEAD = re.compile(
    r"^\s*(references?|bibliography|literature\s+cited|works\s+cited|"
    r"参考文献|参考资料|致谢|acknowledg(e)?ments?)\s*[:：]?\s*$",
    re.IGNORECASE,
)

# 纯噪声行
NOISE = re.compile(
    r"(doi\s*:|https?://|www\.|\S+@\S+\.\w+|©|copyright|all rights reserved|"
    r"received\s*:|accepted\s*:|published\s*:|available online|"
    r"第\s*\d+\s*页|共\s*\d+\s*页|"
    r"this content was downloaded from|content from this work may be used|"
    r"published under licence|view the article online|you may also like|"
    r"all rights reserved|issn\s*[:：]|open access|creative commons|"
    r"downloaded from ip address|terms and conditions)",
    re.IGNORECASE,
)

# 纯页码行
PAGE_NO = re.compile(r"^\s*[-–—(\[]?\s*\d{1,4}\s*[-–—)\]]?\s*$")

CJK = re.compile(r"[\u4e00-\u9fff]")


def extract_pages(pdf_path: Path):
    """逐页提取文本"""
    pages = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            pages.append(page.get_text("text"))
    return pages


def find_running_lines(pages):
    """统计出现在超过一半页面上的短行，视为页眉页脚"""
    head, foot = Counter(), Counter()
    for text in pages:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            continue
        for l in lines[:2]:
            head[l] += 1
        for l in lines[-2:]:
            foot[l] += 1

    total = max(len(pages), 1)
    bad = set()
    for counter in (head, foot):
        for line, cnt in counter.items():
            if cnt / total > 0.5 and len(line) < 80:
                bad.add(line)
    return bad


def strip_page_noise(pages, running_lines):
    """删除页眉页脚、页码、噪声行"""
    cleaned = []
    for text in pages:
        keep = []
        for line in text.splitlines():
            s = line.strip()
            if not s:
                keep.append("")
                continue
            if s in running_lines:
                continue
            if PAGE_NO.match(s):
                continue
            if NOISE.search(s) and len(s) < 150:
                continue
            keep.append(line.rstrip())
        cleaned.append("\n".join(keep))
    return cleaned


def cut_references(text: str) -> str:
    """从参考文献处截断（仅当标记出现在文档后 40% 处）"""
    lines = text.splitlines()
    start_floor = int(len(lines) * 0.6)
    for i, line in enumerate(lines):
        if i < start_floor:
            continue
        if REF_HEAD.match(line.strip()):
            return "\n".join(lines[:i])
    return text


FRONT_END = re.compile(
    r"^\s*(abstract|摘\s*要|引言|introduction|1\.?\s*introduction|1\s*引\s*言)\b",
    re.IGNORECASE,
)


def cut_front_matter(text: str) -> str:
    """从正文起点（Abstract / 摘要 / Introduction）开始截取，
    去掉前面的期刊名、引用格式、推荐文献列表等出版社模板文字。
    找不到标记就原样返回，避免误删。"""
    lines = text.splitlines()
    limit = max(int(len(lines) * 0.25), 3)
    for i, line in enumerate(lines[:limit]):
        if FRONT_END.match(line.strip()):
            return "\n".join(lines[i:])
    return text


def merge_lines(text: str) -> str:
    """把 PDF 的硬换行合并成段落。

    判断段落边界的依据：学术/书籍 PDF 的正文行宽度基本一致，
    段落最后一行的长度会明显短于中位数。用这个特征断段，
    比"以句号结尾"可靠得多。
    """
    import statistics

    lines = [l.strip() for l in text.splitlines()]
    sample = [len(l) for l in lines if len(l) > 20]
    median = statistics.median(sample) if sample else 80

    out, buf = [], ""

    def flush():
        nonlocal buf
        if buf.strip():
            out.append(buf.strip())
            out.append("")
        buf = ""

    for s in lines:
        if not s:
            flush()
            continue

        if not buf:
            buf = s
            continue

        # 上一行明显短 + 以句末标点收尾 → 段落结束
        is_para_end = (
            len(buf) < median * 0.82
            and buf.endswith((".", "。", "！", "？", "!", "?", "：", ":", "；", ";"))
        )
        if is_para_end:
            flush()
            buf = s
            continue

        # 连字符断词
        if buf.endswith("-") and s[:1].islower():
            buf = buf[:-1] + s
            continue

        # 中日韩文字直接拼，英文加空格
        if CJK.search(buf[-1:]) or CJK.search(s[:1]):
            buf = buf + s
        else:
            buf = buf + " " + s

    flush()
    return "\n".join(out)


def dedup_paragraphs(text: str) -> str:
    """去掉完全重复的段落（按前 200 字归一化后比对）"""
    seen, out = set(), []
    for para in text.split("\n\n"):
        p = para.strip()
        if not p:
            continue
        key = re.sub(r"\s+", "", p)[:200]
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return "\n\n".join(out)


def clean_one(pdf_path: Path) -> str:
    pages = extract_pages(pdf_path)
    running = find_running_lines(pages)
    pages = strip_page_noise(pages, running)
    text = "\n".join(pages)
    text = cut_references(text)
    text = cut_front_matter(text)
    text = merge_lines(text)
    text = dedup_paragraphs(text)
    return text


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    dst.mkdir(parents=True, exist_ok=True)

    files = sorted(src.glob("*.pdf")) if src.is_dir() else [src]
    if not files:
        print(f"[提示] {src} 下没有找到 PDF")
        return

    print(f"共 {len(files)} 个文件，输出到 {dst}\n")
    total_before = total_after = 0

    for f in files:
        try:
            before = sum(len(p.get_text("text")) for p in fitz.open(f))
            text = clean_one(f)
            out_path = dst / (f.stem + "_clean.txt")
            out_path.write_text(text, encoding="utf-8")
            after = len(text)
            total_before += before
            total_after += after
            pct = (1 - after / before) * 100 if before else 0
            print(f"[OK] {f.name}")
            print(f"     {before:>8} -> {after:>8} 字符   去掉 {pct:.0f}%")
        except Exception as e:
            print(f"[FAIL] {f.name}: {e}")

    if total_before:
        print(f"\n合计 {total_before} -> {total_after} 字符，"
              f"整体去掉 {(1 - total_after / total_before) * 100:.0f}%")
    print("\n注意：输出为 txt，请上传到论文库（段落分隔 \\n\\n），不要放进工艺知识卡库。")


if __name__ == "__main__":
    main()
