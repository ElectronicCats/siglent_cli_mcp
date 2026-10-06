import pytest

from tests.fakes import FakeOscilloscope, run_cli

LIST_LOG = [
    ("q", f"C{n}:{m}?") for n in (1, 2, 3, 4) for m in ("TRA", "VDIV", "OFST", "CPL")
]
LIST_OUT = "".join(
    f"C{n}: trace={'ON' if n <= 2 else 'OFF'}  v/div=5.00E-01V  offset=0.00E+00V  coupling=D1M\n"
    for n in (1, 2, 3, 4)
)

CASES = [
    (["channel", "list"], LIST_LOG, LIST_OUT),
    (["channel", "on", "-c", "3"], [("w", "C3:TRA ON")], "C3 trace enabled.\n"),
    (["channel", "off"], [("w", "C1:TRA OFF")], "C1 trace disabled.\n"),
    (["channel", "vdiv", "-c", "2"], [("q", "C2:VDIV?")], "C2:VDIV 5.00E-01V\n"),
    (["channel", "vdiv", "-c", "2", "0.2"], [("w", "C2:VDIV 0.2")], "C2 v/div = 0.2 V\n"),
    (["channel", "offset", "0.5"], [("w", "C1:OFST 0.5")], "C1 offset = 0.5 V\n"),
    (["channel", "coupling", "-c", "4", "A50"], [("w", "C4:CPL A50")], "C4 coupling = A50\n"),
    (["channel", "bwlimit"], [("q", "C1:BWL?")], "C1:BWL OFF\n"),
    (["channel", "probe", "10"], [("w", "C1:ATTN 10.0")], "C1 probe attenuation = 10.0\n"),
    (["channel", "invert", "ON"], [("w", "C1:INVT ON")], "C1 invert = ON\n"),
    (["channel", "unit", "-c", "2", "A"], [("w", "C2:UNIT A")], "C2 unit = A\n"),
    (["channel", "skew", "-c", "2"], [("q", "C2:SKEW?")], "C2:SKEW 0.00E+00S\n"),
]


@pytest.mark.parametrize("args,log,output", CASES)
def test_channel_cli(monkeypatch, args, log, output):
    fake = FakeOscilloscope()
    result = run_cli(monkeypatch, fake, *args)
    assert result.exit_code == 0, result.output
    assert result.output == output
    assert fake.log == log
