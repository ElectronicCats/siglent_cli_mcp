"""Software serial decoders (UART, I2C, SPI) working on captured waveforms.

The oscilloscope's built-in decoder cannot be read back over USBTMC, so the
bytes are recovered from the sampled analog waveforms instead. All decoders
are pure Python and take plain lists of volts, so they can be tested offline.
"""

from __future__ import annotations


def to_logic(samples, threshold=None, hysteresis=0.1):
    """Digitise analog samples with a Schmitt trigger.

    threshold defaults to the midpoint of min/max. hysteresis is the fraction
    of the peak-to-peak swing around the threshold that must be crossed to
    change state, which rejects ringing and noise.
    """
    if not samples:
        return [], 0.0
    lo, hi = min(samples), max(samples)
    swing = hi - lo
    if threshold is None:
        threshold = (lo + hi) / 2.0
    band = swing * hysteresis / 2.0
    upper, lower = threshold + band, threshold - band
    state = samples[0] > threshold
    out = []
    for v in samples:
        if state and v < lower:
            state = False
        elif not state and v > upper:
            state = True
        out.append(state)
    return out, threshold


def uart_decode(
    samples,
    dt,
    baud,
    bits=8,
    parity="NONE",
    stop=1.0,
    polarity="HIGH",
    lsb_first=True,
    threshold=None,
):
    """Decode a UART line. Returns a list of dicts.

    Each frame has: time (s), value (int), errors (list of str).
    polarity is the idle level: HIGH is standard TTL/CMOS, LOW is inverted.
    """
    logic, _ = to_logic(samples, threshold)
    if polarity.upper() == "LOW":
        logic = [not b for b in logic]
    spb = 1.0 / (baud * dt)  # samples per bit
    if spb < 3:
        raise ValueError(
            f"Only {spb:.1f} samples per bit: sample rate too low for {baud} baud."
        )
    n = len(logic)
    frames = []
    i = 1
    while i < n:
        if not (logic[i - 1] and not logic[i]):  # falling edge = start bit
            i += 1
            continue
        start = i
        if start + spb * (1.5 + bits) >= n:
            break
        errors = []
        if logic[int(start + spb * 0.5)]:
            i += 1  # glitch, not a real start bit
            continue
        value = 0
        for k in range(bits):
            bit = logic[int(start + spb * (1.5 + k))]
            value |= int(bit) << (k if lsb_first else bits - 1 - k)
        pos = 1.5 + bits
        par = parity.upper()
        if par in ("EVEN", "ODD"):
            pbit = int(logic[int(start + spb * pos)])
            ones = bin(value).count("1") + pbit
            if (ones % 2 == 0) != (par == "EVEN"):
                errors.append("parity")
            pos += 1
        if not logic[int(start + spb * pos)]:
            errors.append("framing")
        frames.append({"time": start * dt, "value": value, "errors": errors})
        # Resume mid-way through the last stop bit so the next start edge
        # (which may follow immediately) is still ahead of us.
        i = int(start + spb * (pos + max(stop, 1.0) - 1.0))
    return frames


def i2c_decode(scl, sda, dt, threshold_scl=None, threshold_sda=None):
    """Decode an I2C bus. Returns a list of transactions.

    Each transaction: {time, address, read (bool), data: [int], acks: [bool],
    repeated_start (bool)}. acks[0] is the address ACK.
    """
    c, _ = to_logic(scl, threshold_scl)
    d, _ = to_logic(sda, threshold_sda)
    n = min(len(c), len(d))
    txns = []
    cur = None
    bits = []

    def finish_byte():
        nonlocal bits
        bits = []

    for i in range(1, n):
        if c[i] and d[i - 1] != d[i] and c[i - 1]:  # SDA moves while SCL high
            if cur is not None and not d[i]:  # START (repeated)
                txns.append(cur)
                cur = {"time": i * dt, "address": None, "read": False, "data": [], "acks": [], "repeated_start": True}
            elif cur is None and not d[i]:  # START
                cur = {"time": i * dt, "address": None, "read": False, "data": [], "acks": [], "repeated_start": False}
            elif cur is not None and d[i]:  # STOP
                txns.append(cur)
                cur = None
            finish_byte()
            continue
        if cur is not None and not c[i - 1] and c[i]:  # SCL rising: sample SDA
            bits.append(d[i])
            if len(bits) == 9:
                value = 0
                for b in bits[:8]:
                    value = (value << 1) | int(b)
                ack = not bits[8]  # ACK = SDA low
                if cur["address"] is None:
                    cur["address"] = value >> 1
                    cur["read"] = bool(value & 1)
                else:
                    cur["data"].append(value)
                cur["acks"].append(ack)
                finish_byte()
    if cur is not None:
        txns.append(cur)
    return txns


def spi_decode(
    clk,
    mosi=None,
    miso=None,
    cs=None,
    dt=1.0,
    bits=8,
    cpol=0,
    cpha=0,
    msb_first=True,
    threshold=None,
):
    """Decode an SPI bus. Returns a list of frames (one per CS assertion).

    Each frame: {time, mosi: [int], miso: [int]}. Without a CS line the whole
    capture is a single frame. CS is assumed active low.
    """
    k, _ = to_logic(clk, threshold)
    m = to_logic(mosi, threshold)[0] if mosi else None
    s = to_logic(miso, threshold)[0] if miso else None
    c = to_logic(cs, threshold)[0] if cs else None
    n = len(k)
    # Data is sampled on the leading edge for CPHA=0 and on the trailing edge
    # for CPHA=1. With CPOL=0 the leading edge is rising; with CPOL=1 falling.
    sample_rising = (cpol == 0) == (cpha == 0)

    frames = []
    cur = None
    wm = ws = nbits = 0

    def close():
        nonlocal cur, wm, ws, nbits
        if cur is not None and (cur["mosi"] or cur["miso"]):
            frames.append(cur)
        cur = None
        wm = ws = nbits = 0

    for i in range(1, n):
        if c is not None:
            if c[i - 1] and not c[i]:  # CS falls: new frame
                close()
                cur = {"time": i * dt, "mosi": [], "miso": []}
                continue
            if not c[i - 1] and c[i]:  # CS rises: frame ends
                close()
                continue
            if c[i]:
                continue  # CS inactive
        if cur is None:
            cur = {"time": i * dt, "mosi": [], "miso": []}
        edge = (not k[i - 1] and k[i]) if sample_rising else (k[i - 1] and not k[i])
        if not edge:
            continue
        bm = int(m[i]) if m else 0
        bs = int(s[i]) if s else 0
        if msb_first:
            wm, ws = (wm << 1) | bm, (ws << 1) | bs
        else:
            wm |= bm << nbits
            ws |= bs << nbits
        nbits += 1
        if nbits == bits:
            if m:
                cur["mosi"].append(wm)
            if s:
                cur["miso"].append(ws)
            wm = ws = nbits = 0
    close()
    return frames
