# -*- coding: utf-8 -*-
"""从 Europe PMC 抓取开放获取的 Nature 论文，算顶刊语体基准。

只保存聚合后的分位数，不保存、不再分发论文全文。

安全边界（处理外部输入时固定写死）：
- 只允许 https + www.ebi.ac.uk + /europepmc/webservices/rest/ 前缀
- 禁止重定向；PMCID 只接受 PMC + 数字
- XML 拒绝 DOCTYPE / ENTITY，限制 20 MB
- 输出路径必须落在当前项目目录内

用法：
    python scripts/build_corpus.py --per-year 8 --out benchmarks/nature.json
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional

API = "https://www.ebi.ac.uk/europepmc/webservices/rest"
ALLOWED_HOST = "www.ebi.ac.uk"
ALLOWED_PREFIX = "/europepmc/webservices/rest/"
MAX_XML_BYTES = 20 * 1024 * 1024
PMCID_RE = re.compile(r"PMC\d{1,12}\Z")

ABBR = (
    "e.g", "i.e", "et al", "Fig", "Figs", "vs", "approx", "no", "ref",
    "Eq", "Dr", "Prof", "St", "cf", "suppl", "Ext", "Extended Data",
)

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

NOMINAL_SUFFIXES = ("tion", "sion", "ment", "ness", "ity", "ance", "ence", "ization", "isation")

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")
PLACEHOLDER = "<DOT>"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect blocked", headers, fp)


OPENER = urllib.request.build_opener(NoRedirect)


def validate_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("only https allowed: %r" % url)
    if parsed.hostname != ALLOWED_HOST:
        raise ValueError("host not allowed: %r" % parsed.hostname)
    if not parsed.path.startswith(ALLOWED_PREFIX):
        raise ValueError("path not allowed: %r" % parsed.path)


def open_url(url: str, timeout: int = 60):
    validate_url(url)
    return OPENER.open(url, timeout=timeout)


def safe_output(path: str) -> Path:
    root = Path.cwd().resolve()
    target = Path(path).resolve()
    if target != root and root not in target.parents:
        raise ValueError("output must stay inside %s: %s" % (root, path))
    return target


def parse_xml(xml_text: str) -> ET.Element:
    if len(xml_text.encode("utf-8", errors="replace")) > MAX_XML_BYTES:
        raise ValueError("xml too large")
    low = xml_text.lower()
    if "<!doctype" in low or "<!entity" in low:
        raise ValueError("DTD/ENTITY not allowed")
    return ET.fromstring(xml_text)


def strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def walk_text(el: ET.Element) -> str:
    """把 JATS 元素转成纯文本，引用标记成 [[CITE]]。"""
    out: List[str] = []

    def rec(node: ET.Element) -> None:
        tag = strip_ns(node.tag)
        if tag in ("xref", "ext-link"):
            if tag == "xref":
                out.append(" [[CITE]] ")
        else:
            if node.text:
                out.append(node.text)
            for child in node:
                rec(child)
        if node.tail:
            out.append(node.tail)

    rec(el)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def split_sentences(text: str) -> List[str]:
    protected = text
    for abbr in ABBR:
        protected = re.sub(r"\b" + re.escape(abbr) + r"\.", abbr + PLACEHOLDER, protected)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])", protected)
    return [p.replace(PLACEHOLDER, ".").strip() for p in parts if p.strip()]


def words(text: str) -> List[str]:
    return WORD_RE.findall(text)


NEG_RE = re.compile(
    r"\b(?:not|no|never|cannot|can't|without|neither|nor|fail(?:s|ed)? to)\b[^.!?]{0,28}$",
    re.I,
)


def count_terms(text: str, terms: Iterable[str]) -> int:
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


def percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(float(ordered[0]), 3)
    pos = (len(ordered) - 1) * q
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    frac = pos - low
    return round(ordered[low] * (1 - frac) + ordered[high] * frac, 3)


def summarise(values: List[float]) -> Dict[str, float]:
    clean = [v for v in values if v is not None]
    return {
        "n": len(clean),
        "p25": percentile(clean, 0.25),
        "p50": percentile(clean, 0.50),
        "p75": percentile(clean, 0.75),
        "min": round(min(clean), 3) if clean else 0.0,
        "max": round(max(clean), 3) if clean else 0.0,
    }


def search_year(year: int, per_year: int) -> List[str]:
    query = 'JOURNAL:"Nature" AND OPEN_ACCESS:y AND PUB_YEAR:%d' % year
    params = urllib.parse.urlencode({
        "query": query, "format": "json", "pageSize": str(per_year),
        "resultType": "core", "sort": "CITED desc",
    })
    url = API + "/search?" + params
    with open_url(url, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    ids = []
    for row in data.get("resultList", {}).get("result", []):
        pmcid = row.get("pmcid")
        if pmcid and PMCID_RE.match(pmcid):
            ids.append(pmcid)
    return ids


def fetch_xml(pmcid: str) -> Optional[str]:
    if not PMCID_RE.match(pmcid):
        raise ValueError("bad pmcid: %r" % pmcid)
    cache_dir = Path.cwd() / "_cache"
    cache = cache_dir / (pmcid + ".xml")
    if cache.exists():
        return cache.read_text(encoding="utf-8", errors="replace")
    url = API + "/" + pmcid + "/fullTextXML"
    try:
        with open_url(url, timeout=90) as resp:
            text = resp.read(MAX_XML_BYTES + 1).decode("utf-8", errors="replace")
        cache_dir.mkdir(exist_ok=True)
        cache.write_text(text, encoding="utf-8")
        return text
    except Exception as exc:
        print("skip %s: %s" % (pmcid, exc), file=sys.stderr)
        return None


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_article(xml_text: str) -> Optional[Dict[str, object]]:
    try:
        root = parse_xml(xml_text)
    except (ET.ParseError, ValueError):
        return None

    title_el = root.find(".//article-title")
    title = normalize("".join(title_el.itertext())) if title_el is not None else ""

    abstract_el = root.find(".//abstract")
    abstract = walk_text(abstract_el) if abstract_el is not None else ""
    abstract = abstract.replace("[[CITE]]", "")

    body = root.find(".//body")
    if body is None:
        return None

    paragraphs: List[str] = []
    sections: List[Dict[str, str]] = []
    for sec in body.findall(".//sec"):
        title_el = sec.find("title")
        sec_title = normalize("".join(title_el.itertext())) if title_el is not None else ""
        sec_paras = []
        for p in sec.findall("./p"):
            text = walk_text(p)
            if words(text):
                sec_paras.append(text)
                paragraphs.append(text)
        sections.append({"title": sec_title, "text": " ".join(sec_paras)})

    if len(paragraphs) < 5:
        return None

    return {
        "title": title,
        "abstract": abstract,
        "paragraphs": paragraphs,
        "sections": sections,
    }


def metrics_for(article: Dict[str, object]) -> Dict[str, float]:
    paragraphs = article["paragraphs"]
    body = " ".join(paragraphs)
    all_words = words(body)
    n_words = len(all_words) or 1

    sents: List[str] = []
    for p in paragraphs:
        sents.extend(split_sentences(p))
    sent_lengths = [len(words(s)) for s in sents]
    sent_lengths = [x for x in sent_lengths if x >= 3]
    mean_len = statistics.mean(sent_lengths) if sent_lengths else 0.0
    stdev = statistics.pstdev(sent_lengths) if len(sent_lengths) > 1 else 0.0

    cite_sents = [s for s in sents if "[[CITE]]" in s]
    end_cites = 0
    for s in cite_sents:
        pos = s.rfind("[[CITE]]")
        if pos / max(1, len(s)) >= 0.6:
            end_cites += 1

    unsupported = 0
    for s in sents:
        if count_terms(s, STRONG) and "[[CITE]]" not in s and not re.search(r"\d", s):
            unsupported += 1

    abstract_words = words(article["abstract"])
    abstract_sents = split_sentences(article["abstract"])
    para_lengths = [len(words(p)) for p in paragraphs]

    result: Dict[str, float] = {
        "body_words": n_words,
        "sentence_mean": round(mean_len, 2),
        "sentence_cv": round(stdev / mean_len, 3) if mean_len else 0.0,
        "long_sentence_ratio": round(
            sum(1 for x in sent_lengths if x > 35) / max(1, len(sent_lengths)), 3),
        "short_sentence_ratio": round(
            sum(1 for x in sent_lengths if x < 12) / max(1, len(sent_lengths)), 3),
        "paragraph_mean_words": round(statistics.mean(para_lengths), 1),
        "paragraph_cv": round(
            statistics.pstdev(para_lengths) / max(1e-9, statistics.mean(para_lengths)), 3),
        "hedge_per_k": round(count_terms(body, HEDGES) * 1000.0 / n_words, 2),
        "booster_per_k": round(count_terms(body, BOOSTERS) * 1000.0 / n_words, 2),
        "connective_per_k": round(count_terms(body, CONNECTIVES) * 1000.0 / n_words, 2),
        "nominalization_per_k": round(nominalizations(all_words) * 1000.0 / n_words, 2),
        "passive_per_k": round(passive_hits(body) * 1000.0 / n_words, 2),
        "first_person_per_k": round(
            len(re.findall(r"\b(?:we|our|us)\b", body)) * 1000.0 / n_words, 2),
        "citation_per_k": round(body.count("[[CITE]]") * 1000.0 / n_words, 2),
        "citation_end_ratio": round(end_cites / max(1, len(cite_sents)), 3),
        "citation_sentence_ratio": round(len(cite_sents) / max(1, len(sents)), 3),
        "strong_claim_unsupported_per_k": round(unsupported * 1000.0 / n_words, 2),
        "abstract_words": len(abstract_words),
        "abstract_sentences": len(abstract_sents),
        "abstract_sentence_mean": round(
            len(abstract_words) / max(1, len(abstract_sents)), 1),
        "title_words": len(words(article["title"])),
        "subsection_count": len(article["sections"]),
        "slop_per_k": round(count_terms(body, SLOP) * 1000.0 / n_words, 2),
    }

    detailed = " ".join(
        s["text"] for s in article["sections"]
        if any(k in s["title"].lower() for k in ("discussion", "conclusion"))
    )
    intro = " ".join(
        s["text"] for s in article["sections"]
        if "introduction" in s["title"].lower()
    )
    if detailed:
        result["hedge_per_k_discussion"] = round(
            count_terms(detailed, HEDGES) * 1000.0 / max(1, len(words(detailed))), 2)
    if intro:
        result["hedge_per_k_introduction"] = round(
            count_terms(intro, HEDGES) * 1000.0 / max(1, len(words(intro))), 2)

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-year", type=int, default=8)
    parser.add_argument("--from-year", type=int, default=2016)
    parser.add_argument("--to-year", type=int, default=2025)
    parser.add_argument("--out", default="benchmarks/nature.json")
    parser.add_argument("--ids-out", default="benchmarks/nature-ids.json")
    parser.add_argument("--sleep", type=float, default=0.25)
    args = parser.parse_args()

    out_path = safe_output(args.out)
    ids_path = safe_output(args.ids_out)

    pmcids: List[str] = []
    for year in range(args.from_year, args.to_year + 1):
        try:
            ids = search_year(year, args.per_year)
        except Exception as exc:
            print("search %d failed: %s" % (year, exc), file=sys.stderr)
            continue
        print("%d: %d ids" % (year, len(ids)), file=sys.stderr)
        pmcids.extend(ids)
        time.sleep(args.sleep)

    seen = set()
    ordered = []
    for pid in pmcids:
        if pid not in seen:
            seen.add(pid)
            ordered.append(pid)

    per_paper = []
    used = []
    for pid in ordered:
        xml_text = fetch_xml(pid)
        time.sleep(args.sleep)
        if not xml_text:
            continue
        article = parse_article(xml_text)
        if not article:
            continue
        m = metrics_for(article)
        m["pmcid"] = pid
        per_paper.append(m)
        used.append(pid)
        if len(per_paper) % 10 == 0:
            print("parsed %d" % len(per_paper), file=sys.stderr)

    if len(per_paper) < 20:
        print("too few papers: %d" % len(per_paper), file=sys.stderr)
        return 1

    keys = [k for k in per_paper[0].keys() if k != "pmcid"]
    bench = {
        "profile": "nature-en",
        "source": (
            "Europe PMC, JOURNAL:\"Nature\" AND OPEN_ACCESS:y, "
            "%d-%d, sorted by citation" % (args.from_year, args.to_year)
        ),
        "papers": len(per_paper),
        "retrieved": time.strftime("%Y-%m-%d"),
        "metrics": {
            k: summarise([float(p[k]) for p in per_paper if k in p])
            for k in keys
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(bench, ensure_ascii=False, indent=2), encoding="utf-8")
    ids_path.write_text(json.dumps(used, indent=2), encoding="utf-8")

    print("wrote %s (%d papers)" % (out_path, len(per_paper)))
    for k in ("sentence_mean", "sentence_cv", "hedge_per_k", "booster_per_k",
              "citation_end_ratio", "abstract_words", "paragraph_mean_words"):
        m = bench["metrics"][k]
        print("%-24s P25 %7.2f  P50 %7.2f  P75 %7.2f" % (k, m["p25"], m["p50"], m["p75"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
