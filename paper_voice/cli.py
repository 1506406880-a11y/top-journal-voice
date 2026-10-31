# -*- coding: utf-8 -*-
"""命令行入口。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import profiles
from .metrics import compute
from .report import evaluate, render_compare, render_markdown, to_dict
from .text import parse

VERSION = "0.1.0"

SAMPLE_EN = """# A compact demonstration

## Abstract

However, how X controls Y remains unclear. Here we show that X increases Y in
three independent assays. These results suggest that X is a limiting factor.

## Introduction

However, the mechanism remains unclear. Previous work demonstrated an
association between X and Y [1].

## Results

We find that X increases Y. The effect was observed in all conditions.
Previous work demonstrated this association [2].

## Discussion

These results suggest that X limits Y. Further work is needed to establish
whether the effect generalises.

## Methods

Samples were collected and analysed as described previously [3].
"""

SAMPLE_ZH = """# 一个示例

## 摘要

现有研究尚未说明 X 与 Y 的关系。本文通过三组材料讨论这一问题，认为 X 并非 Y 的结果，而是 Y 的条件。

## 一、问题

然而，已有研究多从形式入手，很少讨论生产条件。这一路径留下了明显的空白。

## 二、材料

材料显示 X 与 Y 同时出现。这一现象在三个案例中重复出现。

## 三、结论

由此可见，X 构成了 Y 的前提。
"""


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _write(path: str, text: str) -> None:
    root = Path.cwd().resolve()
    target = Path(path).resolve()
    if target != root and root not in target.parents:
        raise ValueError("output must stay inside %s" % root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _selftest() -> int:
    doc_en = parse(SAMPLE_EN)
    if doc_en.language != "en" or len(doc_en.sentences) < 8:
        print("FAIL en parse: %s sentences" % len(doc_en.sentences))
        return 1
    data, values, rows = evaluate(doc_en, "nature")
    if not rows:
        print("FAIL: no rows")
        return 1
    if values.get("abstract_words", 0) < 20:
        print("FAIL: abstract not detected")
        return 1

    doc_zh = parse(SAMPLE_ZH)
    if doc_zh.language != "zh":
        print("FAIL zh language detect")
        return 1
    _, _, rows_zh = evaluate(doc_zh, "cn-t1")
    if not rows_zh:
        print("FAIL: no zh rows")
        return 1

    print("selftest: ok (%d en metrics, %d zh metrics)" % (len(rows), len(rows_zh)))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        prog="paper-voice",
        description="把稿件放进顶刊语体分位带：检查主张、证据、句段与结构。",
    )
    parser.add_argument("file", nargs="?", help="Markdown 或纯文本稿件")
    parser.add_argument("--profile", default="auto",
                        help="对照基准：auto / nature / cn-t1")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--md", metavar="PATH", help="把 Markdown 报告写到文件")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    parser.add_argument("--list-profiles", action="store_true")
    parser.add_argument("--fail-on", choices=["out", "p0", "none"], default="none")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--version", action="version", version="paper-voice " + VERSION)
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()

    if args.list_profiles:
        for name in profiles.available():
            data = profiles.load(name)
            print("%-10s %4d papers  %s" % (
                name, int(data.get("papers", 0)), data.get("source", "")))
        return 0

    if args.compare:
        before = parse(_read(args.compare[0]))
        after = parse(_read(args.compare[1]))
        text = render_compare(before, after, None if args.profile == "auto" else args.profile)
        if args.md:
            _write(args.md, text)
            print("written: %s" % args.md)
        else:
            print(text)
        return 0

    if not args.file:
        parser.print_help()
        return 2

    doc = parse(_read(args.file))
    profile = None if args.profile == "auto" else args.profile
    data, values, rows = evaluate(doc, profile)

    if args.json:
        print(json.dumps(to_dict(doc, args.file, data, values, rows),
                         ensure_ascii=False, indent=2))
    else:
        text = render_markdown(doc, args.file, data, values, rows)
        if args.md:
            _write(args.md, text)
            print("written: %s" % args.md)
        else:
            print(text)

    if args.fail_on != "none":
        if args.fail_on == "p0":
            failed = any(r.priority == 0 and r.status == "out" for r in rows)
        else:
            failed = any(r.status == "out" for r in rows)
        return 1 if failed else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
