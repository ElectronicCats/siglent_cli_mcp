import pytest
from mcp import Client

from osc_cli.device import OscNotFoundError
from siglent_mcp.server import create_server
from siglent_mcp.session import Session
from tests.mcp_server.conftest import call

pytestmark = pytest.mark.anyio


async def test_identify(client, fake):
    result = await call(client, "siglent_identify")
    assert result.structured_content["model"] == "SDS1104X-E"
    assert fake.log[0] == ("w", "CHDR SHORT")


async def test_status_lists_enabled_channels(client):
    s = (await call(client, "siglent_get_status")).structured_content
    assert s["acquisition_state"] == "Trig'd"
    assert [c["channel"] for c in s["channels"]] == [1, 2]
    assert s["trigger"]["mode"] == "AUTO"
    assert s["timebase"]["memory"] == "14M"


async def test_get_channel_one_or_all(client):
    all_four = (await call(client, "siglent_get_channel")).structured_content["channels"]
    assert [c["channel"] for c in all_four] == [1, 2, 3, 4]
    one = (await call(client, "siglent_get_channel", channel=3)).structured_content["channels"]
    assert one[0]["enabled"] is False


async def test_get_channel_rejects_out_of_range(client):
    result = await client.call_tool("siglent_get_channel", {"channel": 5})
    assert result.is_error


async def test_timebase_trigger_counter_awg_error(client):
    assert (await call(client, "siglent_get_timebase")).structured_content["tdiv"] == 0.001
    assert (await call(client, "siglent_get_trigger")).structured_content["level"] == 1.5
    assert (await call(client, "siglent_read_counter")).structured_content["frequency_hz"] == 1000.0
    assert (await call(client, "siglent_get_awg")).structured_content["wave"] == "SINE"
    assert (await call(client, "siglent_get_error")).structured_content == {"code": 0, "message": "No error"}


async def test_measure_invalid_value_has_note(client, fake):
    fake.responses["C1:PAVA? FREQ"] = "C1:PAVA FREQ,****"
    m = (await call(client, "siglent_measure", items=["FREQ", "PKPK"])).structured_content
    assert m["measurements"]["FREQ"]["value"] is None
    assert "note" in m["measurements"]["FREQ"]
    assert m["measurements"]["PKPK"] == {"value": 1.0, "unit": "V"}


async def test_wait_for_acquisition(client, fake):
    fake.responses["SAST?"] = ["SAST Ready", "SAST Stop"]
    w = (await call(client, "siglent_wait_for_acquisition", timeout_s=2)).structured_content
    assert w["triggered"] is True and w["state"] == "Stop"


async def test_missing_scope_gives_actionable_error(storage):
    def factory():
        raise OscNotFoundError("No USBTMC device found.")

    server = create_server(session=Session(factory), storage=storage, max_samples=1000)
    async with Client(server) as c:
        result = await c.call_tool("siglent_identify", {})
    assert result.is_error
    assert "udev rule" in result.content[0].text
