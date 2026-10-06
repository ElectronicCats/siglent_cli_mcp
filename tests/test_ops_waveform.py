import math

import pytest

from osc_cli.device import OscError, parse_wavedesc
from osc_cli.ops import waveform
from tests.fakes import FakeOscilloscope, make_wavedesc_block

CODES = bytes([0, 16, 32, 255, 224])  # 0, 16, 32, -1, -32


def raw_of(codes, **kw):
    return parse_wavedesc(make_wavedesc_block(codes, **kw))


def test_stats_match_direct_computation():
    raw = raw_of(CODES, vdiv=0.5, offset=0.1, interval=1e-6)
    volts = [0.5 / 32 * c - 0.1 for c in (0, 16, 32, -1, -32)]
    s = waveform.stats(raw)
    assert s["n"] == 5
    assert s["min"] == pytest.approx(min(volts))
    assert s["max"] == pytest.approx(max(volts))
    assert s["vpp"] == pytest.approx(max(volts) - min(volts))
    assert s["mean"] == pytest.approx(sum(volts) / 5)
    assert s["rms"] == pytest.approx(math.sqrt(sum(v * v for v in volts) / 5))
    assert s["sample_rate"] == pytest.approx(1e6)
    assert s["duration"] == pytest.approx(5e-6)


def test_stats_rejects_empty():
    with pytest.raises(OscError, match="empty"):
        waveform.stats(raw_of(b""))


def test_decimate_keeps_single_sample_glitch():
    codes = bytearray(10000)
    codes[5003] = 100
    points = waveform.decimate(raw_of(bytes(codes), vdiv=0.32), 100)
    assert len(points) <= 100
    assert max(v for _, v in points) == pytest.approx(1.0)  # 100 * 0.32 / 32


def test_decimate_odd_length_and_two_points():
    codes = bytes(range(0, 127)) + bytes(range(0, 74))  # 201 samples, peak at 126
    points = waveform.decimate(raw_of(codes, vdiv=3.2), 2)
    assert [round(v, 6) for _, v in points] == [0.0, 12.6]


def test_decimate_returns_everything_when_small():
    assert len(waveform.decimate(raw_of(CODES), 500)) == 5


def test_csv_lines_and_limit():
    raw = raw_of(CODES, vdiv=0.5, interval=1e-6)
    lines = list(waveform.csv_lines(raw))
    assert lines[0] == "index,voltage,time"
    assert lines[4] == "3,-0.015625,0.000003000"
    assert len(list(waveform.csv_lines(raw, limit=2))) == 3


def fake_with(codes=CODES, count=None):
    fake = FakeOscilloscope()
    fake.blocks["C1"] = make_wavedesc_block(codes)
    fake.blocks["C2"] = make_wavedesc_block(codes)
    if count is not None:
        fake.responses["SANU? C1"] = f"SANU {count:.2E}pts"
    return fake


def test_fetch_without_limit_skips_sample_count():
    fake = fake_with()
    waveform.fetch(fake, "C1")
    assert fake.log == [("wf", "C1", 1)]


def test_fetch_requests_sparsing_above_limit():
    fake = fake_with(bytes(5000), count=5000)
    fake.honor_sparsing = True
    raw = waveform.fetch(fake, "C1", max_samples=1000)
    assert ("wf", "C1", 5) in fake.log
    assert len(raw.codes) == 1000


def test_fetch_refuses_when_scope_ignores_sparsing():
    fake = fake_with(bytes(5000), count=5000)
    with pytest.raises(OscError, match="OSC_MAX_SAMPLES"):
        waveform.fetch(fake, "C1", max_samples=1000)


def test_capture_multiple_sources_stops_and_writes_csv(tmp_path):
    fake = fake_with()
    seen = []
    result = waveform.capture(
        fake, ["C1", "C2", "C1"], max_points=4,
        csv_path_for=lambda s: tmp_path / f"{s}.csv",
        progress=lambda done, total, msg: seen.append((done, total)),
    )
    assert fake.writes[0] == "STOP"
    assert result["acquisition_stopped"] is True
    assert list(result["sources"]) == ["C1", "C2"]
    assert (tmp_path / "C1.csv").read_text().startswith("index,voltage,time\n0,")
    assert len(result["sources"]["C2"]["points"]) <= 4
    assert seen == [(1, 2), (2, 2)]


def test_capture_single_source_does_not_stop():
    fake = fake_with()
    result = waveform.capture(fake, ["C1"])
    assert "STOP" not in fake.writes
    assert result["acquisition_stopped"] is False
    assert "csv_path" not in result["sources"]["C1"]
