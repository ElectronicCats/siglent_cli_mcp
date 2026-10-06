"""Tools that change scope settings without driving the circuit under test."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from osc_cli.ops import acquisition, decode, misc, timebase, trigger
from osc_cli.ops import channel as ops_channel

from ..errors import tool_errors
from ..models import (
    AcquisitionResult, ChannelState, CounterState, DisplayState, MathState,
    SerialTriggerResult, SetupResult, TimebaseState, TriggerState,
)
from .common import WRITE, WRITE_ONCE, ChannelNumber, Deps, Source

Positive = Annotated[float | None, Field(gt=0)]
SetupPath = Annotated[str, Field(min_length=1, max_length=200, description='File path on the scope, e.g. "/usb/setup1.xml".')]


def register(server: MCPServer, deps: Deps) -> None:
    session = deps.session

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_set_channel(
        channel: ChannelNumber,
        enabled: bool | None = None,
        vdiv: Annotated[float | None, Field(gt=0, description="Volts per division.")] = None,
        offset: Annotated[float | None, Field(description="Vertical offset in volts.")] = None,
        coupling: Literal["A1M", "D1M", "A50", "D50", "GND"] | None = None,
        bw_limit: Literal["OFF", "20M", "200M"] | None = None,
        probe: Annotated[float | None, Field(gt=0, description="Probe attenuation, e.g. 1 or 10.")] = None,
        invert: bool | None = None,
        unit: Literal["V", "A"] | None = None,
        skew: Annotated[float | None, Field(description="Deskew in seconds.")] = None,
    ) -> ChannelState:
        """Change a channel's vertical settings. Only the arguments you pass change.

        coupling: A=AC, D=DC, 1M/50 = input impedance, GND = grounded. Returns the
        channel state read back from the scope.
        """
        return session.run(
            ops_channel.apply, channel, retry=True,
            enabled=enabled, vdiv=vdiv, offset=offset, coupling=coupling, bw_limit=bw_limit,
            probe=probe, invert=invert, unit=unit, skew=skew,
        )

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_set_timebase(
        tdiv: Annotated[float | None, Field(gt=0, description="Seconds per division.")] = None,
        delay: Annotated[float | None, Field(description="Horizontal trigger delay in seconds.")] = None,
        memory: Annotated[
            Literal["7K", "70K", "700K", "7M", "14K", "140K", "1.4M", "14M"] | None,
            Field(description="Memory depth. Large depths make siglent_capture_waveform slow; "
                              "7K-700K is plenty for most analysis."),
        ] = None,
        averages: Annotated[int | None, Field(ge=1, le=1024)] = None,
    ) -> TimebaseState:
        """Change horizontal settings. Only the arguments you pass change.

        The 14K/140K/1.4M/14M depths apply when at most two channels are on.
        """
        return session.run(timebase.apply, tdiv, delay, memory, averages, retry=True)

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_set_trigger(
        mode: Literal["AUTO", "NORM", "SINGLE", "STOP"] | None = None,
        type: Literal["EDGE", "SERIAL", "PULSE", "VIDEO", "SLOPE", "PATTERN", "DROP", "INTV", "RUNT"] | None = None,
        source: Literal["C1", "C2", "C3", "C4", "EXT", "LINE"] | None = None,
        level: Annotated[float | None, Field(description="Trigger level in volts.")] = None,
        coupling: Literal["DC", "AC", "HFREJ", "LFREJ"] | None = None,
    ) -> TriggerState:
        """Change trigger settings. Only the arguments you pass change; the mode is
        applied last. For one-shot captures prefer siglent_control_acquisition(action='single')."""
        result = session.run(trigger.apply, retry=True, mode=mode, type=type,
                             source=source, level=level, coupling=coupling)
        session.remember_mode(mode or result["mode"])
        return result

    @server.tool(annotations=WRITE_ONCE)
    @tool_errors
    def siglent_control_acquisition(action: Literal["run", "stop", "single", "force"]) -> AcquisitionResult:
        """Start, stop or arm the acquisition.

        run: continuous acquisition in the last AUTO/NORM mode. stop: freeze the
        current capture. single: arm one capture; then call
        siglent_wait_for_acquisition. force: trigger now even without a trigger event.
        """

        def act(o):
            mode = None
            if action == "run":
                mode = acquisition.resume(o, session.last_continuous_mode)
            elif action == "stop":
                acquisition.stop(o)
            elif action == "single":
                acquisition.single(o)
                mode = "SINGLE"
            else:
                acquisition.force(o)
            return {"action": action, "trigger_mode": mode, "state": acquisition.state(o)}

        result = session.run(act, retry=False)
        if action == "single":
            result["note"] = "Call siglent_wait_for_acquisition before measuring or capturing."
        return result

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_configure_uart_trigger(
        rx: Source = "C1",
        tx: Source | None = None,
        baud: Annotated[int, Field(ge=50, le=10_000_000)] = 115200,
        parity: Literal["NONE", "EVEN", "ODD"] = "NONE",
        stop_bits: Annotated[float, Field(ge=1, le=2)] = 1.0,
        polarity: Literal["HIGH", "LOW"] = "HIGH",
    ) -> SerialTriggerResult:
        """Set the scope's serial trigger to UART so it triggers on bus traffic.

        This configures triggering only; read the bytes with siglent_decode_uart.
        polarity is the idle level (HIGH for standard TTL/CMOS UART).
        """
        settings = session.run(decode.configure_uart_trigger, rx, tx, baud, parity,
                               stop_bits, polarity, retry=True)
        return {"protocol": "uart", "settings": settings}

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_configure_i2c_trigger(scl: Source = "C1", sda: Source = "C2") -> SerialTriggerResult:
        """Set the scope's serial trigger to I2C. Read transactions with siglent_decode_i2c."""
        return {"protocol": "i2c", "settings": session.run(decode.configure_i2c_trigger, scl, sda, retry=True)}

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_configure_spi_trigger(
        clk: Source = "C1", miso: Source = "C2", mosi: Source = "C3", cs: Source = "C4",
    ) -> SerialTriggerResult:
        """Set the scope's serial trigger to SPI. Read frames with siglent_decode_spi."""
        settings = session.run(decode.configure_spi_trigger, clk, miso, mosi, cs, retry=True)
        return {"protocol": "spi", "settings": settings}

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_set_math(
        function: Literal["FX", "FY", "FZ", "ADD", "SUB", "MUL", "DIV", "FFT"] | None = None,
        offset: Annotated[float | None, Field(description="Math trace offset.")] = None,
        scale: Annotated[float | None, Field(gt=0, description="Math trace scale per division.")] = None,
    ) -> MathState:
        """Configure the math trace (e.g. ADD of two channels or FFT). Only the arguments you pass change."""
        return session.run(misc.apply_math, function, offset, scale, retry=True)

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_set_display(
        grid: Literal["FULL", "HALF", "OFF"] | None = None,
        intensity: Annotated[int | None, Field(ge=0, le=100, description="Trace intensity, %.")] = None,
        menu: bool | None = None,
        cursor_mode: Literal["OFF", "TRACK", "HABS", "HREL", "VABS", "VREL"] | None = None,
    ) -> DisplayState:
        """Change display options (grid, trace intensity, side menu, cursors).
        Handy before siglent_capture_screen."""
        return session.run(misc.apply_display, grid, intensity, menu, cursor_mode, retry=True)

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_set_counter(enabled: bool) -> CounterState:
        """Turn the hardware frequency counter on or off and return its reading."""

        def act(o):
            misc.set_counter(o, enabled)
            return misc.read_counter(o)

        return session.run(act, retry=True)

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_save_setup(path: SetupPath) -> SetupResult:
        """Save the current scope configuration to a file on the scope (internal or USB stick).

        Restore it later with siglent_recall_setup.
        """
        if '"' in path:
            raise ValueError("Path cannot contain quotes")
        session.run(misc.save_setup, path, retry=True)
        return {"action": "saved", "path": path}
