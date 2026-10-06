"""Read-only tools: identity, status, settings, measurements, waiting."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from osc_cli.ops import acquisition, awg, measure, misc, system, timebase, trigger
from osc_cli.ops import channel as ops_channel

from ..errors import tool_errors
from ..models import (
    AwgState, ChannelList, CounterState, ErrorState, Identity, MeasureResult,
    Status, TimebaseState, TriggerState, WaitResult,
)
from .common import READ, Deps, Source

MeasureItem = Literal[
    "PKPK", "MAX", "MIN", "TOP", "BASE", "AMPL", "MEAN", "RMS",
    "PER", "FREQ", "RISE", "FALL", "WID", "DUTY", "OVSN",
    "FPRE", "CMEAN", "CRMS",
]


def register(server: MCPServer, deps: Deps) -> None:
    session = deps.session

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_identify() -> Identity:
        """Identify the connected oscilloscope: manufacturer, model, serial number and firmware.

        Use it to confirm the scope is reachable over USB.
        """
        return session.run(system.identify, retry=True)

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_get_status() -> Status:
        """Snapshot of the whole scope in one call: acquisition state (SAST), trigger,
        timebase and every enabled channel with its settings.

        Call this first, and before changing settings, to learn the starting
        configuration.
        """

        def snapshot(o):
            channels = [ops_channel.read(o, n) for n in ops_channel.CHANNELS]
            return {
                "acquisition_state": acquisition.state(o),
                "trigger": trigger.read(o),
                "timebase": timebase.read(o),
                "channels": [c for c in channels if c["enabled"]],
            }

        result = session.run(snapshot, retry=True)
        session.remember_mode(result["trigger"]["mode"])
        return result

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_get_channel(
        channel: Annotated[
            int | None, Field(ge=1, le=4, description="Channel 1-4; omit for all four.")
        ] = None,
    ) -> ChannelList:
        """Vertical settings of one channel or all four: enabled, probe factor,
        coupling, bandwidth limit, unit, invert, volts/div, offset (V) and skew (s)."""
        numbers = ops_channel.CHANNELS if channel is None else (channel,)
        return {"channels": session.run(lambda o: [ops_channel.read(o, n) for n in numbers], retry=True)}

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_get_timebase() -> TimebaseState:
        """Horizontal settings: time/div (s), trigger delay (s), sample rate (Sa/s),
        memory depth and number of averages."""
        return session.run(timebase.read, retry=True)

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_get_trigger() -> TriggerState:
        """Trigger settings: mode (AUTO/NORM/SINGLE/STOP), type, source, level (V)
        and coupling. source/level/coupling are null when the scope does not report
        them for the current trigger type."""
        result = session.run(trigger.read, retry=True)
        session.remember_mode(result["mode"])
        return result

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_measure(
        source: Source = "C1",
        items: Annotated[
            list[MeasureItem] | None,
            Field(description="Measurements to read; default PKPK, FREQ, PER, MEAN, RMS, MIN, MAX, DUTY."),
        ] = None,
    ) -> MeasureResult:
        """Automatic measurements on a channel, computed by the scope on the current capture.

        Values are SI (V, s, Hz, %). A value is null when the scope cannot measure
        it (no signal, clipped or too few cycles on screen); the note says how to fix it.
        """
        return {"source": source, "measurements": session.run(measure.measure, source, items, retry=True)}

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_read_counter() -> CounterState:
        """Read the hardware frequency counter (enable it with siglent_set_counter)."""
        return session.run(misc.read_counter, retry=True)

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_get_awg() -> AwgState:
        """Current waveform generator settings: output on/off, load, wave type,
        frequency (Hz), amplitude (Vpp), offset (V), phase (deg), duty (%), arbitrary
        wave, modulation, sync, burst and sweep. Unsupported fields are null."""
        return session.run(awg.read, retry=True)

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_get_error() -> ErrorState:
        """Last entry of the scope's error queue (code 0 means no error).

        Useful after siglent_send_raw_command to check that a command was accepted.
        """
        return session.run(system.last_error, retry=True)

    @server.tool(annotations=READ)
    @tool_errors
    def siglent_wait_for_acquisition(
        timeout_s: Annotated[float, Field(ge=0.1, le=300, description="Maximum wait in seconds.")] = 10.0,
    ) -> WaitResult:
        """Wait until the scope reports a completed capture (state Stop or Trig'd).

        Use after siglent_control_acquisition(action='single') before measuring or
        capturing. triggered=false means the timeout passed without a trigger:
        check the trigger level and source.
        """
        return acquisition.wait(lambda: session.run(acquisition.state, retry=True), timeout_s)
