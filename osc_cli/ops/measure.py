"""Automatic measurements via the LeCroy PAVA readout: C<n>:PAVA? <param>."""

from __future__ import annotations

from ._parse import split_number, value_of

PARAMS = (
    "PKPK", "MAX", "MIN", "TOP", "BASE", "AMPL", "MEAN", "RMS",
    "PER", "FREQ", "RISE", "FALL", "WID", "DUTY", "OVSN",
    "FPRE", "CMEAN", "CRMS",
)
DEFAULT_ITEMS = ("PKPK", "FREQ", "PER", "MEAN", "RMS", "MIN", "MAX", "DUTY")
SOURCES = ("C1", "C2", "C3", "C4")
INVALID_NOTE = (
    "The scope could not measure this (****): make the signal fill the screen "
    "by adjusting v/div, time/div or the trigger level."
)


def query_item(o, source: str, item: str) -> str:
    """Raw response, e.g. 'C1:PAVA FREQ,1.00E+03Hz'."""
    if source not in SOURCES:
        raise ValueError(f"source must be one of {', '.join(SOURCES)}")
    if item not in PARAMS:
        raise ValueError(f"Unknown measurement {item!r}; use one of {', '.join(PARAMS)}")
    return o.query(f"{source}:PAVA? {item}")


def measure(o, source: str, items=None) -> dict:
    """{item: {"value": float | None, "unit": str, "note"?: str}}."""
    out = {}
    for item in items or DEFAULT_ITEMS:
        text = value_of(query_item(o, source, item))
        reading = text.split(",", 1)[1] if "," in text else text
        value, unit = split_number(reading)
        entry = {"value": value, "unit": unit}
        if value is None:
            entry["note"] = INVALID_NOTE
        out[item] = entry
    return out
