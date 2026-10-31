# -*- coding: utf-8 -*-
"""paper-voice：顶刊语体体检。"""
from .metrics import compute
from .report import evaluate, render_markdown
from .text import parse

__version__ = "0.1.0"
__all__ = ["parse", "compute", "evaluate", "render_markdown", "__version__"]
