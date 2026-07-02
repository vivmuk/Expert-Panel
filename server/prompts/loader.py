"""Prompt templates live as markdown files next to this module.

Files use {placeholder} slots filled via str.format; literal braces in prompt
text must be doubled ({{ }})."""
import os
from functools import lru_cache

_ROOT = os.path.dirname(__file__)


@lru_cache(maxsize=None)
def _read(template_path):
    path = os.path.join(_ROOT, f"{template_path}.md")
    with open(path, encoding="utf-8") as f:
        return f.read()


def render(__template, **kwargs):
    return _read(__template).format(**kwargs)
