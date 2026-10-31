# -*- coding: utf-8 -*-
"""顶刊语体基准的加载与比对。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .rules import PROFILE_ALIASES

DATA_DIR = Path(__file__).resolve().parent / "data"


def available() -> List[str]:
    if not DATA_DIR.exists():
        return []
    return sorted(p.stem for p in DATA_DIR.glob("*.json"))


def resolve_name(name: str) -> str:
    key = PROFILE_ALIASES.get(name.lower(), name.lower())
    path = DATA_DIR / (key + ".json")
    if not path.exists() and (DATA_DIR / (name.lower() + ".json")).exists():
        path = DATA_DIR / (name.lower() + ".json")
        key = name.lower()
    if not path.exists():
        raise FileNotFoundError(
            "profile %r not found; available: %s" % (name, ", ".join(available()))
        )
    return path.stem


def load(name: str) -> Dict[str, object]:
    key = resolve_name(name)
    with open(DATA_DIR / (key + ".json"), "r", encoding="utf-8") as fh:
        data = json.load(fh)
    for metric, band in data.get("metrics", {}).items():
        if "p25" not in band or "p75" not in band:
            raise ValueError("profile %s metric %s missing p25/p75" % (key, metric))
    return data


def band_status(value: float, band: Dict[str, float], tolerance: float = 0.25) -> str:
    low = float(band["p25"])
    high = float(band["p75"])
    if low <= value <= high:
        return "in"
    width = max(high - low, 1e-9)
    distance = (low - value) if value < low else (value - high)
    return "near" if distance / width <= tolerance else "out"


def direction(value: float, band: Dict[str, float]) -> str:
    if value < float(band["p25"]):
        return "low"
    if value > float(band["p75"]):
        return "high"
    return "in"


def format_band(band: Dict[str, float], unit: str) -> str:
    return "%s–%s %s" % (_fmt(band["p25"]), _fmt(band["p75"]), unit)


def _fmt(value) -> str:
    number = float(value)
    if number >= 100:
        return "%.0f" % number
    if number >= 10:
        return "%.1f" % number
    if number >= 1:
        return "%.2f" % number
    return "%.3f" % number


def band_center(band: Dict[str, float]) -> float:
    return (float(band["p25"]) + float(band["p75"])) / 2.0


def distance_ratio(value: float, band: Dict[str, float]) -> float:
    low = float(band["p25"])
    high = float(band["p75"])
    width = max(high - low, 1e-9)
    if value < low:
        return (low - value) / width
    if value > high:
        return (value - high) / width
    return 0.0


def pick_profile(doc) -> str:
    return "cn-t1" if doc.language == "zh" else "nature"
