# -*- coding: utf-8 -*-
"""解析、指标与分位带的回归测试。"""
import unittest

from paper_voice.metrics import compute
from paper_voice.profiles import band_status
from paper_voice.report import evaluate
from paper_voice.text import parse

SAMPLE_EN = """# A short title

## Abstract

Here we show that X increases Y. These results suggest that X limits Y.

## Results

We find that X increases Y [1]. Previous work demonstrated that X matters.

## Discussion

These results do not demonstrate a causal effect.

## References

[1] Example et al. 2020.
"""

SAMPLE_ZH = """# 一个题目

## 摘要

本文讨论 X 与 Y 的关系。研究认为 X 构成 Y 的前提。

## 一、问题

然而，已有研究不足[1]。
"""


class TestParsing(unittest.TestCase):
    def test_language(self):
        self.assertEqual(parse(SAMPLE_EN).language, "en")
        self.assertEqual(parse(SAMPLE_ZH).language, "zh")

    def test_references_are_cut(self):
        doc = parse(SAMPLE_EN)
        self.assertNotIn("Example et al", doc.body)
        self.assertEqual(doc.body.count("[[CITE]]"), 1)

    def test_abstract(self):
        doc = parse(SAMPLE_EN)
        self.assertIn("Here we show", doc.abstract)
        self.assertGreater(len(doc.sentences), 3)

    def test_title(self):
        self.assertEqual(parse(SAMPLE_EN).title, "A short title")


class TestMetrics(unittest.TestCase):
    def test_unsupported_strong_claim(self):
        values = compute(parse(SAMPLE_EN))
        self.assertGreater(values["strong_claim_unsupported_per_k"], 0)

    def test_negated_strong_claim_is_not_counted(self):
        text = """# T

## Results

We show that X increases Y. These results do not demonstrate a causal effect.
"""
        values = compute(parse(text))
        self.assertEqual(values["strong_claim_unsupported_per_k"], 0)

    def test_citation_end(self):
        text = """# T

## Results

We find that X increases Y [1]. Previous work [2] reported a similar pattern.
"""
        values = compute(parse(text))
        self.assertGreater(values["citation_end_ratio"], 0)
        self.assertLess(values["citation_end_ratio"], 1)

    def test_zh_metrics(self):
        values = compute(parse(SAMPLE_ZH))
        self.assertGreater(values["metadiscourse_per_k"], 0)
        self.assertGreaterEqual(values["citation_end_ratio"], 0)
        self.assertGreater(values["abstract_chars"], 0)


class TestBands(unittest.TestCase):
    band = {"p25": 0.5, "p50": 0.7, "p75": 1.0}

    def test_in(self):
        self.assertEqual(band_status(0.7, self.band), "in")

    def test_low(self):
        self.assertEqual(band_status(0.2, self.band), "out")

    def test_near(self):
        self.assertEqual(band_status(1.05, self.band), "near")

    def test_evaluate_has_rows(self):
        _, _, rows = evaluate(parse(SAMPLE_EN), "nature")
        ids = {r.id for r in rows}
        self.assertIn("citation_end_ratio", ids)
        self.assertIn("strong_claim_unsupported_per_k", ids)


if __name__ == "__main__":
    unittest.main()
