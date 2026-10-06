import os
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

pytestmark = pytest.mark.anyio

# name: (read_only, destructive, idempotent) — the table in the spec.
EXPECTED = {
    "siglent_identify": (True, False, True),
    "siglent_get_status": (True, False, True),
    "siglent_get_channel": (True, False, True),
    "siglent_get_timebase": (True, False, True),
    "siglent_get_trigger": (True, False, True),
    "siglent_measure": (True, False, True),
    "siglent_capture_screen": (True, False, True),
    "siglent_read_counter": (True, False, True),
    "siglent_get_awg": (True, False, True),
    "siglent_get_error": (True, False, True),
    "siglent_wait_for_acquisition": (True, False, True),
    "siglent_set_channel": (False, False, True),
    "siglent_set_timebase": (False, False, True),
    "siglent_set_trigger": (False, False, True),
    "siglent_control_acquisition": (False, False, False),
    "siglent_capture_waveform": (False, False, True),
    "siglent_decode_uart": (False, False, True),
    "siglent_decode_i2c": (False, False, True),
    "siglent_decode_spi": (False, False, True),
    "siglent_configure_uart_trigger": (False, False, True),
    "siglent_configure_i2c_trigger": (False, False, True),
    "siglent_configure_spi_trigger": (False, False, True),
    "siglent_set_math": (False, False, True),
    "siglent_set_display": (False, False, True),
    "siglent_set_counter": (False, False, True),
    "siglent_save_setup": (False, False, True),
    "siglent_recall_setup": (False, True, True),
    "siglent_set_awg": (False, True, True),
    "siglent_set_awg_burst": (False, True, True),
    "siglent_set_awg_sweep": (False, True, True),
    "siglent_reset": (False, True, True),
    "siglent_run_selftest": (False, True, False),
    "siglent_calibrate": (False, True, False),
    "siglent_send_raw_command": (False, True, False),
}


async def test_tool_catalog_and_annotations(client):
    tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == set(EXPECTED)
    for name, (read_only, destructive, idempotent) in EXPECTED.items():
        a = tools[name].annotations
        assert (a.read_only_hint, a.destructive_hint, a.idempotent_hint) == (read_only, destructive, idempotent), name
        assert a.open_world_hint is False, name
        assert tools[name].description, name
        if name != "siglent_capture_screen":
            assert tools[name].output_schema is not None, name


async def test_stdio_server_starts_without_a_scope(tmp_path):
    root = Path(__file__).resolve().parents[2]
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "siglent_mcp.server"],
        cwd=str(root),
        env={**os.environ, "OSC_DATA_DIR": str(tmp_path), "OSC_LOG_LEVEL": "DEBUG"},
    )
    async with Client(params) as c:
        tools = (await c.list_tools()).tools
    assert len(tools) == len(EXPECTED)
