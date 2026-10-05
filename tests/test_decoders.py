"""Offline tests for the software serial decoders (no oscilloscope needed)."""

from osc_cli import decoders

DT = 1e-6  # 1 MHz sample rate
HI, LO = 3.3, 0.0


def uart_wave(data, baud, bits=8, parity="NONE", idle=HI, lsb=True):
    spb = round(1 / (baud * DT))
    lvl = lambda b: HI if b else LO
    out = [HI] * (spb * 3)
    for byte in data:
        seq = [0]
        order = range(bits) if lsb else range(bits - 1, -1, -1)
        seq += [(byte >> k) & 1 for k in order]
        if parity != "NONE":
            ones = bin(byte).count("1")
            seq.append((ones % 2) if parity == "EVEN" else (1 - ones % 2))
        seq.append(1)
        for b in seq:
            out += [lvl(b)] * spb
    out += [HI] * (spb * 3)
    if idle == LO:
        out = [HI - v for v in out]
    return out


def test_uart_plain():
    msg = b"Hola\x00\xff"
    got = decoders.uart_decode(uart_wave(msg, 9600), DT, 9600)
    assert bytes(f["value"] for f in got) == msg
    assert not any(f["errors"] for f in got)


def test_uart_parity_and_msb():
    msg = b"\x55\xa3"
    got = decoders.uart_decode(
        uart_wave(msg, 19200, parity="EVEN", lsb=False), DT, 19200, parity="EVEN", lsb_first=False
    )
    assert bytes(f["value"] for f in got) == msg
    assert not any(f["errors"] for f in got)


def test_uart_parity_error_flagged():
    got = decoders.uart_decode(uart_wave(b"\x01", 9600, parity="EVEN"), DT, 9600, parity="ODD")
    assert got and got[0]["errors"] == ["parity"]


def test_uart_inverted_polarity():
    got = decoders.uart_decode(uart_wave(b"AB", 9600, idle=LO), DT, 9600, polarity="LOW")
    assert bytes(f["value"] for f in got) == b"AB"


def test_uart_sample_rate_too_low():
    try:
        decoders.uart_decode([0, 1] * 10, 1e-4, 9600)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def i2c_wave(txns, half=5):
    scl, sda = [HI] * half, [HI] * half

    def put(c, d, n=half):
        scl.extend([c] * n)
        sda.extend([d] * n)

    for addr, rw, data in txns:
        put(HI, HI)
        put(HI, LO)  # START
        for byte in [(addr << 1) | rw] + list(data):
            for k in range(7, -1, -1):
                bit = HI if (byte >> k) & 1 else LO
                put(LO, bit); put(HI, bit); put(LO, bit)
            put(LO, LO); put(HI, LO); put(LO, LO)  # ACK
        put(LO, LO)
        put(HI, LO)
        put(HI, HI)  # STOP
    return scl, sda


def test_i2c_write_and_read():
    scl, sda = i2c_wave([(0x50, 0, [0x12, 0x34]), (0x68, 1, [0xAB])])
    got = decoders.i2c_decode(scl, sda, DT)
    assert [(t["address"], t["read"], t["data"]) for t in got] == [
        (0x50, False, [0x12, 0x34]),
        (0x68, True, [0xAB]),
    ]
    assert all(all(t["acks"]) for t in got)


def spi_wave(words, cpol=0, cpha=0, half=4, with_cs=True):
    clk, mosi, cs = [], [], []
    idle = HI if cpol else LO

    def put(c, d, s, n=half):
        clk.extend([c] * n); mosi.extend([d] * n); cs.extend([s] * n)

    put(idle, LO, HI)
    for w in words:
        put(idle, LO, LO)
        for k in range(7, -1, -1):
            bit = HI if (w >> k) & 1 else LO
            lead, trail = (LO if cpol == 0 else HI), idle
            lead = HI if cpol == 0 else LO
            if cpha == 0:
                put(idle, bit, LO); put(lead, bit, LO); put(idle, bit, LO)
            else:
                put(idle, LO, LO); put(lead, bit, LO); put(idle, bit, LO)
        put(idle, LO, LO)
        put(idle, LO, HI)
    return clk, mosi, cs


def test_spi_mode0_with_cs():
    clk, mosi, cs = spi_wave([0xA5, 0x3C])
    got = decoders.spi_decode(clk, mosi, None, cs, DT)
    assert [f["mosi"] for f in got] == [[0xA5], [0x3C]]


def test_spi_mode0_without_cs_single_frame():
    clk, mosi, _ = spi_wave([0xA5, 0x3C])
    got = decoders.spi_decode(clk, mosi, None, None, DT)
    assert got[0]["mosi"] == [0xA5, 0x3C]


if __name__ == "__main__":
    import sys
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn(); print("ok  ", name)
            except Exception as e:  # noqa: BLE001
                fails += 1; print("FAIL", name, repr(e))
    sys.exit(1 if fails else 0)
