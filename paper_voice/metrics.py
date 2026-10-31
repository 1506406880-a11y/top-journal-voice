# -*- coding: utf-8 -*-
"""指标计算。英文面向 Nature 系，中文面向中文 T1 期刊。"""
from __future__ import annotations

import re
import statistics
from typing import Dict, List

from .text import Doc, char_count, section_map, word_count

HEDGES = (
    "may", "might", "could", "suggest", "suggests", "suggested", "suggesting",
    "indicate", "indicates", "indicated", "indicating", "appear", "appears",
    "appeared", "seem", "seems", "seemed", "likely", "possibly", "potentially",
    "presumably", "arguably", "perhaps", "approximately", "relatively",
    "tend", "tends", "tended", "to our knowledge",
)
BOOSTERS = (
    "clearly", "obviously", "undoubtedly", "certainly", "definitively",
    "conclusively", "unprecedented", "first-ever", "prove", "proves", "proved",
    "demonstrate", "demonstrates", "demonstrated", "establish", "establishes",
    "established", "dramatically", "remarkably", "substantially",
)
STRONG = (
    "prove", "proves", "proved", "demonstrate", "demonstrates", "demonstrated",
    "establish", "establishes", "established", "clearly", "conclusively",
    "undoubtedly", "definitively", "unprecedented",
)
CONNECTIVES = (
    "however", "therefore", "moreover", "furthermore", "additionally", "thus",
    "hence", "consequently", "in addition", "overall", "nevertheless",
    "nonetheless", "by contrast", "in contrast", "as a result",
)
SLOP = (
    "delve", "underscore", "underscores", "pivotal", "realm", "landscape",
    "testament", "intricate", "robust", "comprehensive", "crucial",
    "paramount", "leverage", "foster", "elucidate", "myriad", "nuanced",
    "holistic", "paradigm", "synergy", "tapestry",
)
NOMINAL_SUFFIXES = (
    "tion", "sion", "ment", "ness", "ity", "ance", "ence", "ization", "isation",
)
ZH_CONNECTIVES = (
    "然而", "因此", "此外", "同时", "另外", "总之", "综上", "由此可见",
    "换言之", "值得注意的是", "需要指出的是",
)
ZH_META = ("本文", "笔者", "我们认为", "作者认为", "值得注意的是", "需要指出的是")

ABSTRACT_MOVES = {
    "gap": re.compile(
        r"however|remain(s|ed)? (unclear|unknown|poorly)|little is known|"
        r"has not been|have not been|yet to be|the extent to which", re.I),
    "approach": re.compile(
        r"\bhere we\b|\bwe report\b|\bwe show\b|\bwe describe\b|\bwe present\b|"
        r"\busing\b|\bby combining\b|\bwe develop\b", re.I),
    "result": re.compile(
        r"\bwe find\b|\bwe found\b|\bwe show\b|\breveal(s|ed)?\b|"
        r"increase(s|d)?\b|decrease(s|d)?\b|reduce(s|d)?\b", re.I),
    "implication": re.compile(
        r"suggest(s|ing)?\b|implication|provide(s|d)?\b|pave(s|d)? the way|"
        r"open(s|ed)? (a )?(new )?(route|avenue)|these results", re.I),
}


NEG_RE = re.compile(
    r"\b(?:not|no|never|cannot|can't|without|neither|nor|fail(?:s|ed)? to)\b[^.!?]{0,28}$",
    re.I,
)


def count_terms(text: str, terms) -> int:
    low = text.lower()
    total = 0
    for term in terms:
        pattern = r"(?<![a-z])" + re.escape(term) + r"(?![a-z])"
        for match in re.finditer(pattern, low):
            prefix = low[max(0, match.start() - 32):match.start()]
            if NEG_RE.search(prefix):
                continue
            total += 1
    return total


def nominalizations(tokens: List[str]) -> int:
    return sum(1 for t in tokens if t.lower().endswith(NOMINAL_SUFFIXES) and len(t) > 6)


def passive_hits(text: str) -> int:
    pattern = (
        r"\b(?:is|are|was|were|be|been|being)\s+"
        r"(?:\w+ed|shown|found|made|given|taken|seen|known|used|reported|observed)\b"
    )
    return len(re.findall(pattern, text, flags=re.I))


def _mean(values: List[float]) -> float:
    return round(statistics.mean(values), 3) if values else 0.0


def _cv(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = statistics.mean(values)
    if not mean:
        return 0.0
    return round(statistics.pstdev(values) / mean, 3)


def _ratio(part: float, whole: float) -> float:
    return round(part / whole, 3) if whole else 0.0


def compute_en(doc: Doc) -> Dict[str, float]:
    total_words = max(1.0, doc.total)
    body = doc.body
    tokens = re.findall(r"[A-Za-z][A-Za-z'\-]*", body)
    sent_lengths = [s.length for s in doc.sentences if s.length >= 3]
    para_lengths = [float(word_count(p.text)) for p in doc.paragraphs]

    cite_sents = [s for s in doc.sentences if s.has_citation]
    end_cites = 0
    for s in cite_sents:
        pos = s.text.rfind("[[CITE]]")
        if pos / max(1, len(s.text)) >= 0.6:
            end_cites += 1

    unsupported = 0
    for s in doc.sentences:
        if count_terms(s.text, STRONG) and not s.has_citation and not re.search(r"\d", s.text):
            unsupported += 1

    abstract = doc.abstract
    moves = [name for name, pattern in ABSTRACT_MOVES.items() if pattern.search(abstract)]
    secs = section_map(doc)

    result: Dict[str, float] = {
        "sentence_mean": _mean(sent_lengths),
        "sentence_cv": _cv(sent_lengths),
        "long_sentence_ratio": _ratio(sum(1 for x in sent_lengths if x > 35), len(sent_lengths)),
        "short_sentence_ratio": _ratio(sum(1 for x in sent_lengths if x < 12), len(sent_lengths)),
        "paragraph_mean_words": _mean(para_lengths),
        "paragraph_cv": _cv(para_lengths),
        "hedge_per_k": round(count_terms(body, HEDGES) * 1000.0 / total_words, 2),
        "booster_per_k": round(count_terms(body, BOOSTERS) * 1000.0 / total_words, 2),
        "connective_per_k": round(count_terms(body, CONNECTIVES) * 1000.0 / total_words, 2),
        "nominalization_per_k": round(nominalizations(tokens) * 1000.0 / total_words, 2),
        "passive_per_k": round(passive_hits(body) * 1000.0 / total_words, 2),
        "first_person_per_k": round(
            len(re.findall(r"\b(?:we|our|us)\b", body)) * 1000.0 / total_words, 2),
        "citation_per_k": round(body.count("[[CITE]]") * 1000.0 / total_words, 2),
        "citation_end_ratio": _ratio(end_cites, len(cite_sents)),
        "citation_sentence_ratio": _ratio(len(cite_sents), len(doc.sentences)),
        "strong_claim_unsupported_per_k": round(unsupported * 1000.0 / total_words, 2),
        "slop_per_k": round(count_terms(body, SLOP) * 1000.0 / total_words, 2),
        "abstract_words": float(word_count(abstract)),
        "abstract_sentences": float(len(doc.sentences) and len([
            s for s in doc.sentences if s.section == "abstract"])),
        "title_words": float(word_count(doc.title)),
        "section_count": float(len([k for k in secs if k in
                                    ("introduction", "results", "discussion", "conclusion", "methods")])),
        "abstract_move_count": float(len(moves)),
    }
    if "abstract" in secs:
        abs_sents = [s.length for s in doc.sentences if s.section == "abstract"]
        result["abstract_sentence_mean"] = _mean(abs_sents)
        result["abstract_sentences"] = float(len(abs_sents))
    if "introduction" in secs:
        intro = secs["introduction"]
        result["hedge_per_k_introduction"] = round(
            count_terms(intro, HEDGES) * 1000.0 / max(1, word_count(intro)), 2)
    discussion = " ".join(secs[k] for k in ("discussion", "conclusion") if k in secs)
    if discussion:
        result["hedge_per_k_discussion"] = round(
            count_terms(discussion, HEDGES) * 1000.0 / max(1, word_count(discussion)), 2)

    result["_abstract_moves"] = moves  # type: ignore[assignment]
    result["_sections_present"] = [k for k in
                                   ("abstract", "introduction", "results",
                                    "discussion", "conclusion", "methods") if k in secs]  # type: ignore
    return result


def compute_zh(doc: Doc) -> Dict[str, float]:
    total_chars = max(1.0, doc.total)
    body = doc.body
    sent_lengths = [s.length for s in doc.sentences if s.length >= 4]
    para_lengths = [float(char_count(p.text)) for p in doc.paragraphs]

    cite_paras = [p for p in doc.paragraphs if "[[CITE]]" in p.text]
    end_cites = 0
    for p in cite_paras:
        text = p.text
        pos = text.rfind("[[CITE]]")
        if pos / max(1, len(text)) >= 0.8:
            end_cites += 1

    result: Dict[str, float] = {
        "sentence_mean_chars": _mean(sent_lengths),
        "sentence_cv": _cv(sent_lengths),
        "long80_ratio": _ratio(sum(1 for x in sent_lengths if x > 80), len(sent_lengths)),
        "paragraph_mean_chars": _mean(para_lengths),
        "citation_per_k": round(body.count("[[CITE]]") * 1000.0 / total_chars, 2),
        "citation_end_ratio": _ratio(end_cites, len(cite_paras)),
        "connective_per_k": round(sum(body.count(w) for w in ZH_CONNECTIVES) * 1000.0 / total_chars, 2),
        "metadiscourse_per_k": round(sum(body.count(w) for w in ZH_META) * 1000.0 / total_chars, 2),
        "abstract_chars": float(char_count(doc.abstract)),
        "title_chars": float(char_count(doc.title)),
    }
    secs = section_map(doc)
    result["_sections_present"] = [k for k in
                                   ("abstract", "introduction", "results",
                                    "discussion", "conclusion", "methods") if k in secs]  # type: ignore
    return result


def compute(doc: Doc) -> Dict[str, float]:
    return compute_zh(doc) if doc.language == "zh" else compute_en(doc)
