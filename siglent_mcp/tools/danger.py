"""Destructive tools: drive the generator output or overwrite the configuration."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from osc_cli.ops import awg, misc, system
from osc_cli.ops._parse import value_of

from ..errors import tool_errors
from ..models import AwgState, BurstState, RawResult, ResetResult, SelfTestResult, SetupResult, SweepState
from .common import DANGER, DANGER_ONCE, Deps, report_progress

LONG_TIMEOUT_MS = 120_000
RAW_HELP = """Send one command string to the scope exactly as written.

This firmware speaks the LeCroy X-Stream dialect, not standard Siglent SCPI:
channel settings are C<n>:VDIV/OFST/CPL/TRA, measurements C<n>:PAVA? <param>,
timebase TDIV/TRDL/MSIZ, trigger TRMD/TRSE/TRSR/TRLV; the generator uses Siglent
C1:BSWV/C1:OUTP. Set expect_response=true for queries (commands ending in '?').
The server resets the header mode to CHDR SHORT afterwards. Check
siglent_get_error if the scope ignores a command. Prefer the dedicated tools."""


def _selftest_result(raw: str) -> dict:
    text = value_of(raw)
    code = text.strip()
    passed = (code == "0") if code.lstrip("-").isdigit() else None
    return {"passed": passed, "result": text, "raw": raw}


def register(server: MCPServer, deps: Deps) -> None:
    session = deps.session

    @server.tool(annotations=DANGER)
    @tool_errors
    def siglent_recall_setup(
        path: Annotated[str, Field(min_length=1, max_length=200, description="Setup file path on the scope.")],
    ) -> SetupResult:
        """Load a setup file stored on the scope, replacing the whole current configuration.

        Check the new state with siglent_get_status afterwards.
        """
        session.run(misc.recall_setup, path, retry=False, restore_header=True)
        return {"action": "recalled", "path": path}

    @server.tool(annotations=DANGER)
    @tool_errors
    def siglent_set_awg(
        enabled: Annotated[bool | None, Field(description="Generator output on/off; applied last when turning on, first when turning off.")] = None,
        wave: Literal["SINE", "SQUARE", "RAMP", "PULSE", "NOISE", "ARB", "DC"] | None = None,
        freq: Annotated[float | None, Field(gt=0, description="Frequency in Hz.")] = None,
        amp: Annotated[float | None, Field(gt=0, description="Amplitude in Vpp.")] = None,
        offset: Annotated[float | None, Field(description="DC offset in volts.")] = None,
        phase: Annotated[float | None, Field(ge=0, le=360, description="Phase in degrees.")] = None,
        duty: Annotated[float | None, Field(gt=0, lt=100, description="Square wave duty cycle, %.")] = None,
        load: Literal["HZ", "50"] | None = None,
        arb: Annotated[
            Literal["StairUp", "StairDn", "StairUD", "Ppulse", "Npulse", "Trapezia",
                    "Upramp", "Dnramp", "ExpFal", "ExpRise"] | None,
            Field(description="Built-in arbitrary waveform; selects wave=ARB."),
        ] = None,
        modulation: bool | None = None,
        sync: bool | None = None,
    ) -> AwgState:
        """Configure the built-in waveform generator. DRIVES A SIGNAL INTO THE CIRCUIT
        connected to the generator output when enabled: confirm amplitude and offset
        with the user first.

        Only the arguments you pass change. load is the expected termination (HZ =
        high impedance, 50 = 50 ohm) and scales the actual output voltage.
        """
        return session.run(
            awg.apply, retry=True, enabled=enabled, wave=wave, freq=freq, amp=amp, offset=offset,
            phase=phase, duty=duty, load=load, arb=arb, modulation=modulation, sync=sync,
        )

    @server.tool(annotations=DANGER)
    @tool_errors
    def siglent_set_awg_burst(
        enabled: bool | None = None,
        cycles: Annotated[int | None, Field(ge=1, le=1_000_000, description="Cycles per burst.")] = None,
        period: Annotated[float | None, Field(gt=0, description="Burst period in seconds.")] = None,
    ) -> BurstState:
        """Configure burst mode of the waveform generator (N cycles every period). Takes effect on the generator output
        when it is enabled (siglent_set_awg(enabled=True))."""
        return session.run(awg.apply_burst, enabled, cycles, period, retry=True)

    @server.tool(annotations=DANGER)
    @tool_errors
    def siglent_set_awg_sweep(
        enabled: bool | None = None,
        start: Annotated[float | None, Field(gt=0, description="Start frequency in Hz.")] = None,
        stop: Annotated[float | None, Field(gt=0, description="Stop frequency in Hz.")] = None,
        time: Annotated[float | None, Field(gt=0, description="Sweep time in seconds.")] = None,
        direction: Literal["UP", "DOWN"] | None = None,
    ) -> SweepState:
        """Configure a frequency sweep on the waveform generator. Takes effect on the generator output
        when it is enabled (siglent_set_awg(enabled=True))."""
        return session.run(awg.apply_sweep, enabled, start, stop, time, direction, retry=True)

    @server.tool(annotations=DANGER)
    @tool_errors
    def siglent_reset() -> ResetResult:
        """Restore factory defaults (*RST). Erases the whole current configuration."""
        session.run(system.reset, retry=False, restore_header=True)
        session.last_continuous_mode = None
        return {"status": "Factory defaults restored (*RST). Check the new state with siglent_get_status."}

    @server.tool(annotations=DANGER_ONCE)
    @tool_errors
    def siglent_run_selftest(ctx: Context) -> SelfTestResult:
        """Run the scope's internal self-test (*TST?). Disconnect all probes first; can
        take up to two minutes. passed is true when the scope reports 0."""
        report_progress(ctx, 0, 1, "self-test running")
        raw = session.run(system.selftest, retry=False, timeout_ms=LONG_TIMEOUT_MS)
        report_progress(ctx, 1, 1, "self-test finished")
        return _selftest_result(raw)

    @server.tool(annotations=DANGER_ONCE)
    @tool_errors
    def siglent_calibrate(ctx: Context) -> SelfTestResult:
        """Run self-calibration (*CAL?). Disconnect all probes first; takes up to two
        minutes. passed is true when the scope reports 0."""
        report_progress(ctx, 0, 1, "calibration running")
        raw = session.run(system.calibrate, retry=False, timeout_ms=LONG_TIMEOUT_MS)
        report_progress(ctx, 1, 1, "calibration finished")
        return _selftest_result(raw)

    @server.tool(annotations=DANGER_ONCE, description=RAW_HELP)
    @tool_errors
    def siglent_send_raw_command(
        command: Annotated[str, Field(min_length=1, max_length=512)],
        expect_response: bool,
    ) -> RawResult:
        if expect_response and "?" not in command:
            raise ToolError("expect_response=true needs a query (a command containing '?'); "
                            "use expect_response=false for settings.")
        response = session.run(system.raw_command, command, expect_response,
                               retry=False, restore_header=True)
        return {"command": command, "response": response}
