# -*- coding: utf-8 -*-
"""稿件解析：去参考文献、切节、切段、切句、标记引文。

面向 Markdown 或纯文本稿件，不处理 docx。参考文献列表会整段剔除，
所以引文统计只覆盖正文。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

HAN_RE = re.compile("[\u4e00-\u9fff]")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
YAML_RE = re.compile(r"\A---\n.*?\n---\n", re.S)
FENCE_RE = re.compile(r"```.*?```", re.S)
URL_RE = re.compile(r"https?://\S+|www\.\S+")
EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
CAPTION_RE = re.compile(r"^\s*(?:Figure|Fig\.|Table|Extended Data Fig\.)\s*\d+", re.I)

CITE_PATTERNS = (
    re.compile(r"\[\s*\d+(?:\s*[-,–]\s*\d+)*\s*\]"),
    re.compile(r"\(\s*[A-Z][A-Za-z\-']+(?:\s+et al\.?)?\s*,\s*\d{4}[a-z]?(?:\s*;\s*[^)]*)?\)"),
    re.compile(r"\^\d+(?:\s*[,\-]\d+)*"),
    re.compile(r"[\u2460-\u2473]"),
)

SECTION_ALIASES = {
    "abstract": ("abstract", "summary", "摘要", "内容提要"),
    "introduction": ("introduction", "background", "引言", "导言", "绪论"),
    "results": ("results", "findings", "结果", "研究结果"),
    "discussion": ("discussion", "讨论"),
    "conclusion": ("conclusion", "conclusions", "outlook", "结语", "结论"),
    "methods": ("methods", "method", "materials and methods", "methodology",
                "experimental", "材料与方法", "方法"),
    "references": ("references", "bibliography", "works cited", "参考文献", "引用文献"),
}

EN_ABBR = (
    "e.g", "i.e", "et al", "Fig", "Figs", "vs", "approx", "no", "ref",
    "Eq", "Dr", "Prof", "St", "cf", "suppl", "Ext",
)
DOT = "<DOT>"
CLOSERS = "”’」』）)》】\"'"


@dataclass
class Para:
    text: str
    section: str
    index: int


@dataclass
class Sent:
    text: str
    section: str
    para: int
    length: float
    has_citation: bool = False


@dataclass
class Doc:
    text: str
    language: str
    title: str
    sections: List[Dict[str, str]] = field(default_factory=list)
    paragraphs: List[Para] = field(default_factory=list)
    sentences: List[Sent] = field(default_factory=list)
    abstract: str = ""
    unit: str = "word"

    @property
    def body(self) -> str:
        return " ".join(p.text for p in self.paragraphs)

    @property
    def total(self) -> float:
        if self.language == "zh":
            return float(len(HAN_RE.findall(self.body)))
        return float(len(WORD_RE.findall(self.body)))


def detect_language(text: str) -> str:
    han = len(HAN_RE.findall(text))
    latin = len(WORD_RE.findall(text))
    if han == 0:
        return "en"
    return "zh" if han / float(han + latin * 3.2) > 0.5 else "en"


def word_count(text: str) -> int:
    return len(WORD_RE.findall(text))


def char_count(text: str) -> int:
    return len(HAN_RE.findall(text))


def mask(text: str) -> str:
    out = YAML_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
    out = FENCE_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), out)
    out = URL_RE.sub(" ", out)
    out = EMAIL_RE.sub(" ", out)
    lines = []
    for line in out.split("\n"):
        if CAPTION_RE.match(line) or line.lstrip().startswith("|"):
            lines.append(" " * len(line))
        else:
            lines.append(line)
    return "\n".join(lines)


def mark_citations(text: str) -> str:
    out = text
    for pattern in CITE_PATTERNS:
        out = pattern.sub(" [[CITE]] ", out)
    return out


def _section_key(title: str) -> str:
    low = title.strip().lower()
    low = re.sub(r"^\d+[.、)\s]+", "", low)
    for key, aliases in SECTION_ALIASES.items():
        for alias in aliases:
            if low == alias or low.startswith(alias + " ") or low.startswith(alias + ":"):
                return key
    return ""


def split_sections(text: str) -> Tuple[str, List[Dict[str, str]]]:
    """返回 (标题, 节列表)。优先用 Markdown 标题，其次识别独立标题行。"""
    lines = text.split("\n")
    title = ""
    sections: List[Dict[str, str]] = []
    current_title = ""
    buffer: List[str] = []

    def flush() -> None:
        nonlocal buffer
        if buffer:
            body = "\n".join(buffer).strip()
            if body:
                sections.append({"title": current_title, "body": body})
        buffer = []

    md_headings = [ln for ln in lines if HEADING_RE.match(ln)]
    use_md = len(md_headings) >= 2

    for line in lines:
        heading = HEADING_RE.match(line)
        if heading:
            flush()
            current_title = heading.group(2).strip()
            if not title:
                title = current_title
            continue

        stripped = line.strip()
        if not use_md and stripped and len(stripped) <= 60:
            key = _section_key(stripped)
            if key:
                flush()
                current_title = key
                continue

        buffer.append(line)

    flush()
    if not title and sections:
        title = sections[0]["body"].split("\n")[0][:120]
    return title, sections


def _cut_references(sections: List[Dict[str, str]]) -> List[Dict[str, str]]:
    kept = []
    for sec in sections:
        if _section_key(sec["title"]) == "references":
            break
        kept.append(sec)
    return kept


def _split_paragraphs(body: str) -> List[str]:
    blocks = re.split(r"\n\s*\n", body)
    return [re.sub(r"\s+", " ", b).strip() for b in blocks if b.strip()]


def split_sentences_en(text: str) -> List[str]:
    protected = text
    for abbr in EN_ABBR:
        protected = re.sub(r"\b" + re.escape(abbr) + r"\.", abbr + DOT, protected)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])", protected)
    return [p.replace(DOT, ".").strip() for p in parts if word_count(p) >= 2]


def split_sentences_zh(text: str) -> List[str]:
    result = []
    start = 0
    i = 0
    n = len(text)
    while i < n:
        if text[i] in "。！？!?…":
            j = i + 1
            while j < n and text[j] in "。！？!?…":
                j += 1
            while j < n and text[j] in CLOSERS:
                j += 1
            chunk = text[start:j].strip()
            if char_count(chunk) >= 2:
                result.append(chunk)
            start = j
            i = j
        else:
            i += 1
    tail = text[start:].strip()
    if char_count(tail) >= 2:
        result.append(tail)
    return result


def parse(text: str) -> Doc:
    cleaned = mask(text)
    language = detect_language(cleaned)
    title, sections = split_sections(cleaned)
    sections = _cut_references(sections)

    doc = Doc(text=cleaned, language=language, title=title,
              sections=sections, unit="字" if language == "zh" else "词")

    para_index = 0
    for sec in sections:
        sec_key = _section_key(sec["title"]) or sec["title"]
        for block in _split_paragraphs(sec["body"]):
            marked = mark_citations(block)
            doc.paragraphs.append(Para(marked, sec_key, para_index))
            raw_sents = split_sentences_zh(marked) if language == "zh" else split_sentences_en(marked)
            for sent in raw_sents:
                length = char_count(sent) if language == "zh" else word_count(sent)
                doc.sentences.append(Sent(
                    sent, sec_key, para_index, float(length),
                    has_citation="[[CITE]]" in sent,
                ))
            para_index += 1

    for sec in sections:
        if _section_key(sec["title"]) == "abstract":
            doc.abstract = re.sub(r"\s+", " ", sec["body"]).replace("[[CITE]]", "").strip()
            break
    if not doc.abstract:
        for sec in sections[:2]:
            if 40 <= (char_count(sec["body"]) if language == "zh" else word_count(sec["body"])) <= 400:
                doc.abstract = re.sub(r"\s+", " ", sec["body"]).strip()
                break

    return doc


def section_map(doc: Doc) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for sec in doc.sections:
        key = _section_key(sec["title"])
        if key and key not in result:
            result[key] = sec["body"]
    return result
