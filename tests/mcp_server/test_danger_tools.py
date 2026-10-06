import pytest

from osc_cli.device import OscTransportError
from tests.mcp_server.conftest import call

pytestmark = pytest.mark.anyio


async def test_set_awg_turns_output_on_last(client, fake):
    state = (await call(client, "siglent_set_awg", enabled=True, wave="SQUARE", freq=5000, amp=2)).structured_content
    assert [w for w in fake.writes if w != "CHDR SHORT"] == [
        "C1:BSWV WVTP,SQUARE", "C1:BSWV FRQ,5000.0", "C1:BSWV AMP,2.0", "C1:OUTP ON",
    ]
    assert state["wave"] == "SINE"  # fake read-back


async def test_set_awg_rejects_conflicting_arb(client):
    r = await client.call_tool("siglent_set_awg", {"arb": "StairUp", "wave": "SINE"})
    assert r.is_error and "arb" in r.content[0].text


async def test_burst_and_sweep(client, fake):
    b = (await call(client, "siglent_set_awg_burst", enabled=True, cycles=3)).structured_content
    s = (await call(client, "siglent_set_awg_sweep", start=100, stop=200)).structured_content
    assert b["cycles"] == 1 and s["direction"] == "UP"
    assert "C1:BTWV NCYC,3" in fake.writes and "C1:SWWV STOP,200.0" in fake.writes


async def test_reset_restores_header(client, fake):
    await call(client, "siglent_reset")
    assert fake.writes[-2:] == ["*RST", "CHDR SHORT"]


async def test_recall_setup(client, fake):
    r = (await call(client, "siglent_recall_setup", path="/usb/a.xml")).structured_content
    assert r == {"action": "recalled", "path": "/usb/a.xml"}
    assert fake.writes[-2:] == ['RECALL_SETUP FILE,"/usb/a.xml"', "CHDR SHORT"]


async def test_selftest_and_calibrate(client, fake):
    t = (await call(client, "siglent_run_selftest")).structured_content
    assert t == {"passed": True, "result": "0", "raw": "*TST 0"}
    fake.responses["*CAL?"] = "*CAL 1"
    c = (await call(client, "siglent_calibrate")).structured_content
    assert c["passed"] is False


async def test_raw_command_restores_header(client, fake):
    r = (await call(client, "siglent_send_raw_command", command="CHDR OFF", expect_response=False)).structured_content
    assert r == {"command": "CHDR OFF", "response": None}
    assert fake.writes[-2:] == ["CHDR OFF", "CHDR SHORT"]
    q = (await call(client, "siglent_send_raw_command", command="TDIV?", expect_response=True)).structured_content
    assert q["response"] == "TDIV 1.00E-03S"


async def test_raw_command_not_retried(client, fake):
    fake.fail_writes["C1:OUTP ON"] = OscTransportError("pipe")
    r = await client.call_tool("siglent_send_raw_command", {"command": "C1:OUTP ON", "expect_response": False})
    assert r.is_error and "may or may not have run" in r.content[0].text
    assert fake.writes.count("C1:OUTP ON") == 1
