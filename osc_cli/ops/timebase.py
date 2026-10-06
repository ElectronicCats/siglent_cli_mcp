"""Horizontal timebase and acquisition memory: TDIV, TRDL, SARA, MSIZ, AVGA."""

from __future__ import annotations

from ._parse import to_float, value_of

MEMORY_SIZES = ("7K", "70K", "700K", "7M", "14K", "140K", "1.4M", "14M")
FIELDS = {"tdiv": "TDIV", "delay": "TRDL", "memory": "MSIZ", "averages": "AVGA"}
QUERY_FIELDS = {
    "tdiv": "TDIV",
    "delay": "TRDL",
    "sample_rate": "SARA",
    "memory": "MSIZ",
    "averages": "AVGA",
}


def query_field(o, field: str) -> str:
    return o.query(f"{QUERY_FIELDS[field]}?")


def write_field(o, field: str, value) -> None:
    if field not in FIELDS:
        raise ValueError(f"{field} cannot be set")
    o.write(f"{FIELDS[field]} {value}")


def read(o) -> dict:
    v = {field: value_of(query_field(o, field)) for field in QUERY_FIELDS}
    averages = to_float(v["averages"])
    return {
        "tdiv": to_float(v["tdiv"]),
        "delay": to_float(v["delay"]),
        "sample_rate": to_float(v["sample_rate"]),
        "memory": v["memory"],
        "averages": int(averages) if averages is not None else None,
    }


def apply(o, tdiv=None, delay=None, memory=None, averages=None) -> dict:
    """Write the settings that are not None (memory first), then read back."""
    if memory is not None and memory not in MEMORY_SIZES:
        raise ValueError(f"memory must be one of {', '.join(MEMORY_SIZES)}")
    for field, value in (("memory", memory), ("tdiv", tdiv), ("delay", delay), ("averages", averages)):
        if value is not None:
            write_field(o, field, value)
    return read(o)
