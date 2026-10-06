import pytest

from osc_cli.device import OscTransportError
from tests.fakes import FakeOscilloscope, run_cli

TB_STATUS = (
    "Time/div   : TDIV 1.00E-03S\nDelay      : TRDL 0.00E+00S\n"
    "Sample rate: SARA 1.00E+09Sa/s\nMemory     : MSIZ 14M\nAverages   : AVGA 16\n"
)
TRIG_STATUS = (
    "Mode    : TRMD AUTO\nSetup   : TRSE EDGE,SR,C1,HT,OFF\nSource  : TRSR C1\n"
    "Level   : C1:TRLV 1.50E+00V\nCoupling: C1:TRCP DC\n"
)

CASES = [
    (["timebase", "tdiv"], [("q", "TDIV?")], "TDIV 1.00E-03S\n"),
    (["timebase", "tdiv", "0.001"], [("w", "TDIV 0.001")], "Time/div = 0.001 s\n"),
    (["timebase", "delay", "0.0005"], [("w", "TRDL 0.0005")], "Delay = 0.0005 s\n"),
    (["timebase", "samplerate"], [("q", "SARA?")], "SARA 1.00E+09Sa/s\n"),
    (["timebase", "memory", "14M"], [("w", "MSIZ 14M")], "Memory size = 14M\n"),
    (["timebase", "averages", "16"], [("w", "AVGA 16")], "Averages = 16\n"),
    (["timebase", "stop"], [("w", "STOP")], "Acquisition stopped.\n"),
    (["timebase", "status"],
     [("q", "TDIV?"), ("q", "TRDL?"), ("q", "SARA?"), ("q", "MSIZ?"), ("q", "AVGA?")], TB_STATUS),
    (["trigger", "mode", "NORM"], [("w", "TRMD NORM")], "Trigger mode = NORM\n"),
    (["trigger", "type"], [("q", "TRSE?")], "TRSE EDGE,SR,C1,HT,OFF\n"),
    (["trigger", "source", "C2"], [("w", "TRSR C2")], "Trigger source = C2\n"),
    (["trigger", "level"], [("q", "TRLV?")], "C1:TRLV 1.50E+00V\n"),
    (["trigger", "level", "1.2"], [("w", "TRLV 1.2")], "Trigger level = 1.2 V\n"),
    (["trigger", "coupling", "AC"], [("w", "TRCP AC")], "Trigger coupling = AC\n"),
    (["trigger", "status"],
     [("q", "TRMD?"), ("q", "TRSE?"), ("q", "TRSR?"), ("q", "TRLV?"), ("q", "TRCP?")], TRIG_STATUS),
]


@pytest.mark.parametrize("args,log,output", CASES)
def test_timebase_trigger_cli(monkeypatch, args, log, output):
    fake = FakeOscilloscope()
    result = run_cli(monkeypatch, fake, *args)
    assert result.exit_code == 0, result.output
    assert result.output == output
    assert fake.log == log


def test_trigger_status_skips_queries_the_scope_rejects(monkeypatch):
    fake = FakeOscilloscope()
    fake.responses["TRSR?"] = OscTransportError("timeout")
    result = run_cli(monkeypatch, fake, "trigger", "status")
    assert "Source" not in result.output
    assert "Level   : C1:TRLV 1.50E+00V" in result.output


def test_timebase_run_resumes_trigger_mode_instead_of_arm(monkeypatch):
    fake = FakeOscilloscope()
    fake.responses["TRMD?"] = "TRMD NORM"
    result = run_cli(monkeypatch, fake, "timebase", "run")
    assert result.output == "Acquisition running.\n"
    assert fake.log == [("q", "TRMD?"), ("w", "TRMD NORM")]
