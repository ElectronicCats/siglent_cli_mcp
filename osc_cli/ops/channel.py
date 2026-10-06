"""Vertical channel settings: C<n>:TRA/ATTN/CPL/BWL/UNIT/INVT/VDIV/OFST/SKEW."""

from __future__ import annotations

from ._parse import to_bool, to_float, value_of

CHANNELS = (1, 2, 3, 4)
COUPLINGS = ("A1M", "D1M", "A50", "D50", "GND")
BW_LIMITS = ("OFF", "20M", "200M")
UNITS = ("V", "A")
# Write order matters: the probe factor rescales v/div, so it goes first.
FIELDS = {
    "enabled": "TRA",
    "probe": "ATTN",
    "coupling": "CPL",
    "bw_limit": "BWL",
    "unit": "UNIT",
    "invert": "INVT",
    "vdiv": "VDIV",
    "offset": "OFST",
    "skew": "SKEW",
}
_NUMERIC = {"probe", "vdiv", "offset", "skew"}
_BOOLEAN = {"enabled", "invert"}


def _check(channel: int) -> None:
    if channel not in CHANNELS:
        raise ValueError(f"channel must be 1-4, got {channel!r}")


def query_field(o, channel: int, field: str) -> str:
    """Raw response for one setting, e.g. 'C1:VDIV 5.00E-01V'."""
    _check(channel)
    return o.query(f"C{channel}:{FIELDS[field]}?")


def write_field(o, channel: int, field: str, value) -> None:
    _check(channel)
    if isinstance(value, bool):
        value = "ON" if value else "OFF"
    o.write(f"C{channel}:{FIELDS[field]} {value}")


def read(o, channel: int) -> dict:
    state = {"channel": channel}
    for field in FIELDS:
        text = value_of(query_field(o, channel, field))
        if field in _NUMERIC:
            state[field] = to_float(text)
        elif field in _BOOLEAN:
            state[field] = to_bool(text)
        else:
            state[field] = text
    return state


def apply(o, channel: int, **values) -> dict:
    """Write the settings that are not None, then return the channel state."""
    unknown = set(values) - set(FIELDS)
    if unknown:
        raise ValueError(f"Unknown channel setting(s): {', '.join(sorted(unknown))}")
    _check(channel)
    for field in FIELDS:
        if values.get(field) is not None:
            write_field(o, channel, field, values[field])
    return read(o, channel)
