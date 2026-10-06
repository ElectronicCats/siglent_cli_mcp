"""Waveform capture: bounded transfer, statistics, decimation and CSV export.

Samples stay as int8 ADC codes (bytes/array) until they are written out, so a
2M-point capture never becomes millions of Python floats.
"""

from __future__ import annotations

import math
from array import array
from collections import Counter

from ..device import OscError, WaveformRaw
from . import acquisition
from ._parse import to_float, value_of

SOURCES = ("C1", "C2", "C3", "C4")
DEFAULT_MAX_SAMPLES = 2_000_000


def _scale(raw: WaveformRaw) -> float:
    # 8-bit codes span the 8-division grid: 32 codes per division.
    return raw.vdiv / 32.0


def sample_count(o, source: str) -> int | None:
    """Points in the current acquisition (SANU?), or None if unknown."""
    try:
        n = to_float(value_of(o.query(f"SANU? {source}", retries=0)))
    except OscError:
        return None
    return int(n) if n else None


def plan_sparsing(count: int | None, max_samples: int | None) -> int:
    if max_samples is None or count is None or count <= max_samples:
        return 1
    return math.ceil(count / max_samples)


def transfer_deadline(points: int | None) -> float:
    """Seconds allowed for a transfer: 5 s + 2 s per million points."""
    if points is None:
        return 600.0
    return 5.0 + 2.0 * points / 1e6


def fetch(o, source: str, max_samples: int | None = None) -> WaveformRaw:
    """Transfer one channel, asking the scope to sparse it above max_samples.

    max_samples=None transfers everything (CLI behaviour).
    """
    if source not in SOURCES:
        raise ValueError(f"source must be one of {', '.join(SOURCES)}")
    count = sample_count(o, source) if max_samples is not None else None
    k = plan_sparsing(count, max_samples)
    expected = math.ceil(count / k) if count else None
    raw = o.get_waveform_raw(source, sparsing=k, deadline_s=transfer_deadline(expected))
    if max_samples is not None and len(raw.codes) > max_samples * 1.05:
        ignored = " and the scope ignored sparsing" if k > 1 else ""
        raise OscError(
            f"{source}: the capture holds {len(raw.codes)} points, above the limit of "
            f"{max_samples}{ignored}. Reduce the memory depth with "
            "siglent_set_timebase(memory=...) or raise OSC_MAX_SAMPLES."
        )
    return raw


def to_volts(raw: WaveformRaw) -> array:
    scale = _scale(raw)
    return array("d", (scale * c - raw.offset for c in array("b", raw.codes)))


def stats(raw: WaveformRaw) -> dict:
    """Summary statistics from a 256-bin histogram of the ADC codes."""
    n = len(raw.codes)
    if n == 0:
        raise OscError("The scope returned an empty waveform.")
    scale = _scale(raw)
    total = total_sq = 0.0
    lo, hi = 127, -128
    for code, count in Counter(raw.codes).items():
        signed = code - 256 if code >= 128 else code
        v = scale * signed - raw.offset
        total += v * count
        total_sq += v * v * count
        lo, hi = min(lo, signed), max(hi, signed)
    dt = raw.horz_interval
    vmin, vmax = scale * lo - raw.offset, scale * hi - raw.offset
    return {
        "n": n,
        "sample_rate": 1.0 / dt if dt > 0 else None,
        "duration": n * dt,
        "min": vmin,
        "max": vmax,
        "vpp": vmax - vmin,
        "mean": total / n,
        "rms": math.sqrt(total_sq / n),
        "vdiv": raw.vdiv,
        "offset": raw.offset,
        "horz_interval": dt,
        "horz_offset": raw.horz_offset,
    }


def decimate(raw: WaveformRaw, max_points: int) -> list[list[float]]:
    """At most max_points [time, volts] pairs keeping each bucket's min and max.

    A plain every-k-th-sample decimation would drop narrow glitches; min/max
    buckets keep them.
    """
    if max_points < 2:
        raise ValueError("max_points must be at least 2")
    codes = array("b", raw.codes)
    n = len(codes)
    scale = _scale(raw)

    def point(i):
        return [raw.horz_interval * i + raw.horz_offset, scale * codes[i] - raw.offset]

    if n <= max_points:
        return [point(i) for i in range(n)]
    buckets = max_points // 2
    out = []
    for b in range(buckets):
        lo, hi = b * n // buckets, (b + 1) * n // buckets
        segment = codes[lo:hi]
        i_min = lo + segment.index(min(segment))
        i_max = lo + segment.index(max(segment))
        for i in sorted({i_min, i_max}):
            out.append(point(i))
    return out


def csv_lines(raw: WaveformRaw, limit: int = 0):
    """'index,voltage,time' header plus one line per sample (CLI format)."""
    yield "index,voltage,time"
    codes = array("b", raw.codes)
    n = min(len(codes), raw.wave_count) if raw.wave_count > 0 else len(codes)
    if limit > 0:
        n = min(n, limit)
    scale = _scale(raw)
    for i in range(n):
        v = scale * codes[i] - raw.offset
        t = raw.horz_interval * i + raw.horz_offset
        yield f"{i},{v:.6f},{t:.9f}"


def write_csv(raw: WaveformRaw, path) -> None:
    with open(path, "w") as f:
        for line in csv_lines(raw):
            f.write(line + "\n")


def capture(o, sources, max_points: int = 500, max_samples: int | None = DEFAULT_MAX_SAMPLES,
            csv_path_for=None, progress=None) -> dict:
    """Capture one or more channels.

    With more than one source the acquisition is stopped first so every
    channel comes from the same trigger. csv_path_for(source) -> path enables
    CSV export; progress(done, total, message) reports per-channel progress.
    """
    sources = list(dict.fromkeys(sources))
    if not sources:
        raise ValueError("Give at least one source channel.")
    stopped = len(sources) > 1
    if stopped:
        acquisition.stop(o)
    result = {}
    for i, source in enumerate(sources, start=1):
        raw = fetch(o, source, max_samples)
        entry = stats(raw)
        entry["points"] = decimate(raw, max_points)
        if csv_path_for is not None:
            path = csv_path_for(source)
            write_csv(raw, path)
            entry["csv_path"] = str(path)
        result[source] = entry
        if progress is not None:
            progress(i, len(sources), f"{source} captured")
    return {"sources": result, "acquisition_stopped": stopped}
