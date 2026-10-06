import pytest

from osc_cli.device import OscError, parse_wavedesc
from osc_cli.ops import decode, screen, waveform
from tests.bmp_util import make_bmp, read_png
from tests.fakes import FakeOscilloscope, codes_from_volts, make_wavedesc_block
from tests.test_decoders import DT, uart_wave


def test_capture_png():
    fake = FakeOscilloscope()
    fake.raw["SCDP"] = make_bmp([[(255, 0, 0), (0, 0, 255)]])
    assert read_png(screen.capture_png(fake)) == (2, 1, [[(255, 0, 0), (0, 0, 255)]])


def test_capture_png_wraps_bad_bmp():
    fake = FakeOscilloscope()
    fake.raw["SCDP"] = make_bmp([[(0, 0, 0)]])[:-2]
    with pytest.raises(OscError, match="PNG"):
        screen.capture_png(fake)


def test_configure_triggers():
    fake = FakeOscilloscope()
    decode.configure_uart_trigger(fake, rx="C2", tx="C3", baud=9600)
    decode.configure_i2c_trigger(fake)
    decode.configure_spi_trigger(fake, cs="C1")
    assert fake.writes == [
        "TRSE SERIAL", "TRIG_UART:RX C2", "TRIG_UART:BAUD 9600", "TRIG_UART:PARITY NONE",
        "TRIG_UART:STOP 1.0", "TRIG_UART:POLARITY HIGH", "TRIG_UART:TX C3",
        "TRSE SERIAL", "TRIG_IIC:SCL C1", "TRIG_IIC:SDA C2",
        "TRSE SERIAL", "TRIG_SPI:CLK C1", "TRIG_SPI:MISO C2", "TRIG_SPI:MOSI C3", "TRIG_SPI:CS C1",
    ]


def test_capture_csv_round_trips_through_load_csv(tmp_path):
    codes = codes_from_volts(uart_wave(b"OK", 9600), 1.0)
    raw = parse_wavedesc(make_wavedesc_block(codes, vdiv=1.0, interval=DT))
    path = tmp_path / "rx.csv"
    waveform.write_csv(raw, path)
    volts, dt = decode.load_csv(path)
    assert dt == pytest.approx(DT, rel=1e-6)
    assert volts == pytest.approx(list(waveform.to_volts(raw)), abs=1e-6)



def test_load_csv_rejects_non_csv_without_echoing_content(tmp_path):
    path = tmp_path / "x.csv"
    path.write_text("index,voltage,time\n0,secret,0\n1,x,1\n")
    with pytest.raises(ValueError, match="not a waveform CSV") as e:
        decode.load_csv(path)
    assert "secret" not in str(e.value)


def test_capture_lines_freezes_once():
    fake = FakeOscilloscope()
    fake.blocks["C1"] = make_wavedesc_block(bytes(10), interval=2e-6)
    fake.blocks["C2"] = make_wavedesc_block(bytes(10), interval=2e-6)
    lines, dt, stopped = decode.capture_lines(fake, ["C1", "C2"], True, None)
    assert fake.writes == ["STOP"]
    assert set(lines) == {"C1", "C2"} and stopped is True
    assert dt == pytest.approx(2e-6)


def test_with_ascii():
    frames = decode.with_ascii([{"value": 0x41}, {"value": 0x0A}])
    assert [f["ascii"] for f in frames] == ["A", "."]


def test_paginate():
    page = decode.paginate(list(range(5)), limit=2, offset=2)
    assert page == {"items": [2, 3], "total": 5, "count": 2, "offset": 2,
                    "has_more": True, "next_offset": 4}


def test_paginate_offset_past_end():
    page = decode.paginate(list(range(5)), limit=2, offset=10)
    assert page["items"] == [] and page["has_more"] is False and page["next_offset"] is None


def test_diagnose():
    flat = decode.diagnose([0.0, 0.05, 0.1], None)
    assert flat["threshold_v"] == pytest.approx(0.05) and "barely moves" in flat["hint"]
    busy = decode.diagnose([0.0, 3.3], 1.2)
    assert busy["threshold_v"] == 1.2 and "baud" in busy["hint"]
