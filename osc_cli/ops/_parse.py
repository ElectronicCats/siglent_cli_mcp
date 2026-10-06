"""Parsing helpers for LeCroy-style responses, with or without headers."""

from __future__ import annotations

import re

# "C1:VDIV 5.00E-01V" / "*IDN SIGLENT,..." / "SAST Trig'd" -> header + value.
_HEADER = re.compile(r"^\*?[A-Z][A-Z0-9_]*(?::[A-Z][A-Z0-9_]*)*\s+(.*)$", re.S)
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def value_of(response: str) -> str:
    """Strip the command echo (CHDR SHORT/LONG) and return only the value."""
    text = response.strip()
    m = _HEADER.match(text)
    return (m.group(1) if m else text).strip()


def split_number(text: str) -> tuple[float | None, str]:
    """'1.00E+03Hz' -> (1000.0, 'Hz'); '****' -> (None, '')."""
    m = _NUMBER.search(text or "")
    if not m:
        return None, ""
    return float(m.group()), text[m.end():].strip()


def to_float(text: str) -> float | None:
    return split_number(text)[0]


def to_bool(text: str) -> bool:
    return (text or "").strip().upper() in ("ON", "1", "TRUE")


def pairs(text: str) -> dict[str, str]:
    """'WVTP,SINE,FRQ,1000HZ' -> {'WVTP': 'SINE', 'FRQ': '1000HZ'}."""
    tokens = [t.strip() for t in (text or "").split(",")]
    return dict(zip(tokens[0::2], tokens[1::2]))
