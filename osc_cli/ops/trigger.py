"""Trigger settings: TRMD (mode), TRSE (type), TRSR, TRLV, TRCP."""

from __future__ import annotations

from ..device import OscError
from ._parse import to_float, value_of

MODES = ("AUTO", "NORM", "SINGLE", "STOP")
TYPES = ("EDGE", "SERIAL", "PULSE", "VIDEO", "SLOPE", "PATTERN", "DROP", "INTV", "RUNT")
SOURCES = ("C1", "C2", "C3", "C4", "EXT", "LINE")
COUPLINGS = ("DC", "AC", "HFREJ", "LFREJ")
FIELDS = {"mode": "TRMD", "type": "TRSE", "source": "TRSR", "level": "TRLV", "coupling": "TRCP"}
# The scope does not answer these for every trigger type; read them as None.
OPTIONAL = ("source", "level", "coupling")
# Configure first, arm last.
_WRITE_ORDER = ("type", "source", "coupling", "level", "mode")


def query_field(o, field: str, retries: int = 3) -> str:
    return o.query(f"{FIELDS[field]}?", retries=retries)


def write_field(o, field: str, value) -> None:
    o.write(f"{FIELDS[field]} {value}")


def read(o) -> dict:
    state = {}
    for field in FIELDS:
        optional = field in OPTIONAL
        try:
            text = value_of(query_field(o, field, retries=0 if optional else 3))
        except OscError:
            if not optional:
                raise
            state[field] = None
            continue
        if field == "type":
            text = text.split(",")[0]
        state[field] = to_float(text) if field == "level" else text
    return state


def apply(o, **values) -> dict:
    unknown = set(values) - set(FIELDS)
    if unknown:
        raise ValueError(f"Unknown trigger setting(s): {', '.join(sorted(unknown))}")
    for field in _WRITE_ORDER:
        if values.get(field) is not None:
            write_field(o, field, values[field])
    return read(o)
