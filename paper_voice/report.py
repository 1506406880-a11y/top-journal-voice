# -*- coding: utf-8 -*-
"""报告渲染：把稿件放进顶刊分位带，输出可执行的修改顺序。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .metrics import compute
from .profiles import (
    band_status, direction, distance_ratio, load, pick_profile,
)
from .rules import CHECK_ORDER, METRICS, PRIORITY_LABEL
from .text import Doc


@dataclass
class Row:
    id: str
    label: str
    unit: str
    priority: int
    value: float
    band: Dict[str, float]
    status: str
    direction: str
    distance: float
    why: str
    fix: str


def fmt_value(value: float, unit: str) -> str:
    if unit == "%":
        return "%.0f%%" % (value * 100)
    if float(value).is_integer():
        return "%d" % value
    if abs(value) >= 10:
        return "%.1f" % value
    if abs(value) >= 1:
        return "%.2f" % value
    return "%.3f" % value


def fmt_band(band: Dict[str, float], unit: str) -> str:
    if unit == "%":
        return "%.0f–%.0f%%" % (band["p25"] * 100, band["p75"] * 100)
    text = "%s–%s" % (fmt_value(band["p25"], unit), fmt_value(band["p75"], unit))
    return text + (" " + unit if unit not in ("CV",) else "")


def evaluate(doc: Doc, profile_name: Optional[str] = None) -> Tuple[Dict, Dict, List[Row]]:
    name = pick_profile(doc) if profile_name in (None, "", "auto") else profile_name
    data = load(name)
    values = compute(doc)
    rows: List[Row] = []
    for mid in CHECK_ORDER:
        band = data.get("metrics", {}).get(mid)
        if not band or mid not in values:
            continue
        value = float(values[mid])
        meta = METRICS[mid]
        status = band_status(value, band)
        side = direction(value, band)
        if side == "high":
            fix = meta.fix_high
        elif side == "low":
            fix = meta.fix_low or "偏低通常不是问题；确认这不是有意为之。"
        else:
            fix = ""
        rows.append(Row(
            id=mid, label=meta.label, unit=meta.unit, priority=meta.priority,
            value=value, band=band, status=status, direction=side,
            distance=distance_ratio(value, band), why=meta.why, fix=fix,
        ))
    order = {"out": 0, "near": 1, "in": 2}
    rows.sort(key=lambda r: (r.priority, order[r.status], -r.distance))
    return data, values, rows


def _status_label(row: Row) -> str:
    if row.status == "in":
        return "带内"
    side = "偏高" if row.direction == "high" else "偏低"
    return side if row.status == "out" else side + "（临界）"


def render_markdown(doc: Doc, path: str, data: Dict, values: Dict, rows: List[Row]) -> str:
    out: List[str] = []
    out.append("# 顶刊语体体检 · %s" % path)
    out.append("")
    out.append(
        "语言：%s ｜ 正文 %d %s ｜ %d 段 ｜ %d 句 ｜ 对照：%s（%d 篇）" % (
            "中文" if doc.language == "zh" else "英文",
            doc.total, doc.unit, len(doc.paragraphs), len(doc.sentences),
            data.get("profile", "?"), int(data.get("papers", 0)),
        )
    )
    out.append("")
    out.append("> 这不是 AI 检测。它只回答一个问题：这篇文章的语言组织，落在顶刊语体的哪个位置。")
    out.append("")
    if doc.total < 1500:
        out.append(
            "> 提醒：正文只有 %d %s。分位带按整篇论文计算，短文本的密度类指标波动很大，"
            "只作方向参考，不要为了对齐分位数改写。" % (doc.total, doc.unit)
        )
        out.append("")

    counts = {"in": 0, "near": 0, "out": 0}
    for row in rows:
        counts[row.status] += 1
    p0 = [r for r in rows if r.priority == 0 and r.status == "out"]

    out.append("## 结论")
    out.append("")
    out.append(
        "带内 %d 项，临界 %d 项，带外 %d 项。%s" % (
            counts["in"], counts["near"], counts["out"],
            ("P0 有 %d 项越界，先处理主张与证据的绑定。" % len(p0)) if p0
            else "P0 没有越界。",
        )
    )
    out.append("")

    out.append("## 修改顺序")
    out.append("")
    out.append("1. **先补证据，再改句子。** 标出所有强断言，逐条问：这句话的支撑在哪一句、哪一个图、哪一条引文。")
    out.append("2. **把引文移到被支撑句的末尾。** 句首引文只用于承接，不用于支撑本句。")
    out.append("3. **按节型调语气。** Introduction 允许对冲，Discussion 要克制，Results 只写看到了什么。")
    out.append("4. **最后才动句子长度和连接词。** 先改信息顺序，再考虑拆句。")
    out.append("")

    if p0:
        out.append("## P0 · 主张与证据")
        out.append("")
        for row in p0:
            out.append("### %s：%s（顶刊带 %s）" % (
                row.label, fmt_value(row.value, row.unit), fmt_band(row.band, row.unit)))
            out.append("")
            out.append("- 为什么：%s" % row.why)
            out.append("- 怎么改：%s" % row.fix)
            out.append("")

    out.append("## 全部指标")
    out.append("")
    out.append("| 优先级 | 指标 | 读数 | 顶刊带 | 判断 |")
    out.append("|---|---|---|---|---|")
    for row in rows:
        out.append("| %s | %s | %s | %s | %s |" % (
            PRIORITY_LABEL[row.priority].split(" · ")[0],
            row.label,
            fmt_value(row.value, row.unit),
            fmt_band(row.band, row.unit),
            _status_label(row),
        ))
    out.append("")

    actionable = [r for r in rows if r.status in ("out", "near") and r.priority >= 1]
    if actionable:
        out.append("## 其余越界项")
        out.append("")
        for row in actionable[:10]:
            out.append("- **%s**（%s，带 %s）：%s" % (
                row.label, fmt_value(row.value, row.unit),
                fmt_band(row.band, row.unit), row.fix,
            ))
        out.append("")

    moves = values.get("_abstract_moves") or []
    if doc.language != "zh":
        out.append("## 摘要四步")
        out.append("")
        wanted = [("gap", "缺口：现有研究没解决什么"),
                  ("approach", "做法：我们做了什么"),
                  ("result", "结果：看到了什么"),
                  ("implication", "意义：所以呢")]
        for key, label in wanted:
            out.append("- [%s] %s" % ("x" if key in moves else " ", label))
        out.append("")
        if len(moves) < 4:
            out.append("缺项不是硬错误，但四步齐全的摘要更容易让编辑在三十秒内看懂贡献。")
            out.append("")

    sections = values.get("_sections_present") or []
    out.append("## 结构")
    out.append("")
    out.append("识别到的节：%s" % ("、".join(sections) if sections else "未识别到标准节标题"))
    out.append("")
    if doc.language != "zh":
        missing = [s for s in ("abstract", "introduction", "results", "discussion", "methods")
                   if s not in sections]
        if missing:
            out.append("缺失：%s。非标准结构不一定是错，但编辑会按这个顺序找贡献。" % "、".join(missing))
            out.append("")

    out.append("## 语言层之外")
    out.append("")
    out.append("本工具只检查语言组织。它不能补数据、不能替代统计、不能判断结论是否成立。")
    out.append("语言再合规，也救不回一个证据不足的主张。")
    out.append("")
    out.append("Nature 系期刊要求：AI 不能署名；实质性使用须在 Methods 中披露模型与用途；")
    out.append("作者对准确性与结论负全责。详见 `docs/00-政策.md`。")
    out.append("")
    return "\n".join(out)


def render_compare(before: Doc, after: Doc, profile_name: Optional[str]) -> str:
    data_b, values_b, rows_b = evaluate(before, profile_name)
    data_a, values_a, rows_a = evaluate(after, profile_name)
    index_a = {r.id: r for r in rows_a}
    out: List[str] = []
    out.append("# 改写前后对照")
    out.append("")
    out.append("| 指标 | 改前 | 改后 | 顶刊带 |")
    out.append("|---|---|---|---|")
    for row in rows_b:
        other = index_a.get(row.id)
        if not other:
            continue
        out.append("| %s | %s | %s | %s |" % (
            row.label, fmt_value(row.value, row.unit),
            fmt_value(other.value, row.unit), fmt_band(row.band, row.unit),
        ))
    out.append("")
    out.append("只看方向，不追求把每一项推到带中心。机械对齐分位数比不改更糟。")
    out.append("")
    return "\n".join(out)


def to_dict(doc: Doc, path: str, data: Dict, values: Dict, rows: List[Row]) -> Dict:
    return {
        "file": path,
        "language": doc.language,
        "profile": data.get("profile"),
        "benchmark_papers": data.get("papers"),
        "source": data.get("source"),
        "metrics": {
            row.id: {
                "label": row.label,
                "value": row.value,
                "unit": row.unit,
                "band": {"p25": row.band["p25"], "p50": row.band.get("p50"), "p75": row.band["p75"]},
                "status": row.status,
                "direction": row.direction,
                "priority": row.priority,
            }
            for row in rows
        },
        "abstract_moves": values.get("_abstract_moves", []),
        "sections": values.get("_sections_present", []),
        "note": "不判断作者身份，不输出 AI 概率。",
    }
