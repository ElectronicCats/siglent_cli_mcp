from tests.fakes import FakeOscilloscope, make_wavedesc_block, run_cli

CSV = (
    "index,voltage,time\n"
    "0,0.000000,0.000000000\n"
    "1,0.250000,0.000001000\n"
    "2,0.500000,0.000002000\n"
    "3,-0.015625,0.000003000\n"
    "4,-0.500000,0.000004000\n"
)


def fake_with_wave():
    fake = FakeOscilloscope()
    fake.blocks["C1"] = make_wavedesc_block(bytes([0, 16, 32, 255, 224]), vdiv=0.5, interval=1e-6)
    return fake


def test_capture_prints_csv(monkeypatch):
    result = run_cli(monkeypatch, fake_with_wave(), "waveform", "capture")
    assert result.output == CSV + "\n"


def test_capture_trims_points(monkeypatch):
    result = run_cli(monkeypatch, fake_with_wave(), "waveform", "capture", "-n", "2")
    assert result.output == "".join(CSV.splitlines(keepends=True)[:3]) + "\n"


def test_capture_to_file(monkeypatch, tmp_path):
    out = tmp_path / "w.csv"
    result = run_cli(monkeypatch, fake_with_wave(), "waveform", "capture", "-o", str(out))
    assert result.output == f"Saved 5 samples to {out} (vdiv=0.5, interval=1e-06s)\n"
    assert out.read_text() == CSV


def test_info(monkeypatch):
    result = run_cli(monkeypatch, fake_with_wave(), "waveform", "info")
    assert result.output == (
        "Source        : C1\nPoints        : 5\nVertical div  : 0.5 V/div\n"
        "Vertical off. : 0\nHoriz interval: 1e-06 s\nHoriz offset  : 0 s\n"
        "First valid   : 0\nLast valid    : 4\n"
    )
