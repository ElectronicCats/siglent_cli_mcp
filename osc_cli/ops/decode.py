"""Serial bus support: scope trigger setup and host-side byte extraction.

The scope's built-in decoder cannot be read back over USBTMC, so bytes are
recovered by capturing the lines and running osc_cli.decoders on the samples.
"""

from __future__ import annotations

from . import acquisition, waveform

SOURCES = ("C1", "C2", "C3", "C4")
PARITIES = ("NONE", "EVEN", "ODD")
POLARITIES = ("HIGH", "LOW")


# ---- trigger configuration on the scope ------------------------------------
def configure_uart_trigger(o, rx="C1", tx=None, baud=115200, parity="NONE",
                           stop_bits=1.0, polarity="HIGH") -> dict:
    o.write("TRSE SERIAL")
    o.write(f"TRIG_UART:RX {rx}")
    o.write(f"TRIG_UART:BAUD {baud}")
    o.write(f"TRIG_UART:PARITY {parity}")
    o.write(f"TRIG_UART:STOP {stop_bits}")
    o.write(f"TRIG_UART:POLARITY {polarity}")
    if tx:
        o.write(f"TRIG_UART:TX {tx}")
    return {"rx": rx, "tx": tx, "baud": baud, "parity": parity,
            "stop_bits": stop_bits, "polarity": polarity}


def configure_i2c_trigger(o, scl="C1", sda="C2") -> dict:
    o.write("TRSE SERIAL")
    o.write(f"TRIG_IIC:SCL {scl}")
    o.write(f"TRIG_IIC:SDA {sda}")
    return {"scl": scl, "sda": sda}


def configure_spi_trigger(o, clk="C1", miso="C2", mosi="C3", cs="C4") -> dict:
    o.write("TRSE SERIAL")
    o.write(f"TRIG_SPI:CLK {clk}")
    o.write(f"TRIG_SPI:MISO {miso}")
    o.write(f"TRIG_SPI:MOSI {mosi}")
    o.write(f"TRIG_SPI:CS {cs}")
    return {"clk": clk, "miso": miso, "mosi": mosi, "cs": cs}


# ---- samples ------------------------------------------------------------------
def load_csv(path) -> tuple[list[float], float]:
    """(volts, dt) from a CSV written by `osc waveform capture` (index,voltage,time)."""
    volts, times = [], []
    with open(path) as f:
        next(f, None)  # header: index,voltage,time
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 3:
                try:
                    volts.append(float(parts[1]))
                    times.append(float(parts[2]))
                except ValueError:
                    raise ValueError(f"{path}: not a waveform CSV (index,voltage,time)") from None
    if len(volts) < 2:
        raise ValueError(f"{path}: not enough samples.")
    return volts, (times[-1] - times[0]) / (len(times) - 1)


def capture_lines(o, sources, freeze: bool, max_samples: int | None):
    """Capture each source as volts. Returns (lines, dt, stopped).

    freeze=True stops the acquisition first so every line comes from the same
    capture; the scope is left stopped.
    """
    if freeze:
        acquisition.stop(o)
    lines, dt = {}, None
    for source in dict.fromkeys(sources):
        raw = waveform.fetch(o, source, max_samples)
        lines[source] = list(waveform.to_volts(raw))
        dt = dt or raw.horz_interval
    return lines, dt, freeze


# ---- results -----------------------------------------------------------------
def with_ascii(frames: list[dict]) -> list[dict]:
    return [{**f, "ascii": chr(f["value"]) if 32 <= f["value"] < 127 else "."} for f in frames]


def paginate(items: list, limit: int, offset: int) -> dict:
    page = items[offset : offset + limit]
    end = offset + len(page)
    has_more = end < len(items)
    return {
        "items": page,
        "total": len(items),
        "count": len(page),
        "offset": offset,
        "has_more": has_more,
        "next_offset": end if has_more else None,
    }


def diagnose(samples, threshold: float | None) -> dict:
    """Why a decode found nothing: the levels seen and what to try next."""
    lo, hi = min(samples), max(samples)
    if hi - lo < 0.2:
        hint = ("The line barely moves (swing below 0.2 V): check the channel, the probe "
                "and that the bus is active during the capture window.")
    else:
        hint = ("The line toggles but nothing decoded: check the baud rate or SPI mode, "
                "the threshold, and that the capture window (time/div) contains traffic.")
    return {
        "min_v": lo,
        "max_v": hi,
        "threshold_v": threshold if threshold is not None else (lo + hi) / 2.0,
        "hint": hint,
    }
