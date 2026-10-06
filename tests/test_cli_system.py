import pytest

from tests.fakes import IDN, FakeOscilloscope, run_cli

CASES = [
    (["system", "idn"], [("q", "*IDN?")], IDN + "\n"),
    (["system", "reset", "-y"], [("w", "*RST")], "Reset complete.\n"),
    (["system", "error"], [("q", "SYSTem:ERRor?")], '0,"No error"\n'),
    (["system", "trigger"], [("w", "*TRG")], ""),
    (["system", "selftest"], [("q", "*TST?")], "*TST 0\n"),
    (["system", "calibrate", "-y"], [("q", "*CAL?")], "*CAL 0\n"),
]


@pytest.mark.parametrize("args,log,output", CASES)
def test_system_cli(monkeypatch, args, log, output):
    fake = FakeOscilloscope()
    result = run_cli(monkeypatch, fake, *args)
    assert result.exit_code == 0, result.output
    assert result.output == output
    assert fake.log == log
