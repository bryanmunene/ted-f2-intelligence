from __future__ import annotations

import re
from typing import Iterable

WHITESPACE_PATTERN = re.compile(r"\s+")
NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9\-/ ]+")


def collapse_whitespace(value: str) -> str:
    return WHITESPACE_PATTERN.sub(" ", value).strip()


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    lowered = value.lower()
    lowered = NON_ALNUM_PATTERN.sub(" ", lowered)
    return collapse_whitespace(lowered)


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered

