"""AWG (arbitrary waveform generator) control commands.

The SDS1104X-E has an integrated function/AWG generator controlled via a
Siglent-style command set (NOT the LeCroy X-Stream dialect used by the rest
of the scope). The command strings live in osc_cli.ops.awg.
"""

from __future__ import annotations

import click

from ..cli import osc
from ..ops import awg as ops_awg

WAVE_TYPES = ops_awg.WAVE_TYPES
LOADS = ops_awg.LOADS
ARB_WAVEFORMS = ops_awg.ARB_WAVEFORMS


@click.group(name="awg")
def awg_group():
    """Waveform generator (AWG) control."""


def _echo_part(full: str, prefix: str, fallback: bool = False) -> None:
    for part in full.split(","):
        if part.startswith(prefix):
            click.echo(part)
            return
    if fallback:
        click.echo(full)


def _basic_get_or_set(ctx, key, prefix, value, message):
    o = osc(ctx)
    if value is None:
        _echo_part(ops_awg.query_basic(o), prefix)
    else:
        ops_awg.write_basic(o, key, value)
        click.echo(message.format(value=value))


@awg_group.command("status")
@click.pass_context
def status(ctx):
    """Show the full AWG configuration."""
    o = osc(ctx)
    click.echo(f"Output : {ops_awg.query_output(o)}")
    click.echo(f"Wave   : {ops_awg.query_basic(o)}")
    click.echo(f"Mod    : {ops_awg.query_modulation(o)}")


@awg_group.command("on")
@click.pass_context
def on(ctx):
    """Turn the AWG output on."""
    ops_awg.set_output(osc(ctx), True)
    click.echo("AWG output enabled.")


@awg_group.command("off")
@click.pass_context
def off(ctx):
    """Turn the AWG output off."""
    ops_awg.set_output(osc(ctx), False)
    click.echo("AWG output disabled.")


@awg_group.command("wave")
@click.argument("value", type=click.Choice(WAVE_TYPES), required=False)
@click.pass_context
def wave(ctx, value):
    """Get/set the waveform type (SINE/SQUARE/RAMP/PULSE/NOISE/ARB/DC)."""
    o = osc(ctx)
    if value is None:
        _echo_part(ops_awg.query_basic(o), "WVTP", fallback=True)
    else:
        ops_awg.write_basic(o, "WVTP", value)
        click.echo(f"Waveform type = {value}")


@awg_group.command("freq")
@click.argument("value", type=float, required=False)
@click.pass_context
def freq(ctx, value):
    """Get/set the output frequency (Hz)."""
    _basic_get_or_set(ctx, "FRQ", "FRQ", value, "Frequency = {value} Hz")


@awg_group.command("amp")
@click.argument("value", type=float, required=False)
@click.pass_context
def amp(ctx, value):
    """Get/set the amplitude (Vpp)."""
    _basic_get_or_set(ctx, "AMP", "AMP,", value, "Amplitude = {value} Vpp")


@awg_group.command("offset")
@click.argument("value", type=float, required=False)
@click.pass_context
def offset(ctx, value):
    """Get/set the DC offset (V)."""
    _basic_get_or_set(ctx, "OFST", "OFST", value, "Offset = {value} V")


@awg_group.command("phase")
@click.argument("value", type=float, required=False)
@click.pass_context
def phase(ctx, value):
    """Get/set the phase (degrees)."""
    _basic_get_or_set(ctx, "PHSE", "PHSE", value, "Phase = {value} deg")


@awg_group.command("duty")
@click.argument("value", type=float, required=False)
@click.pass_context
def duty(ctx, value):
    """Get/set the square-wave duty cycle (%)."""
    _basic_get_or_set(ctx, "DUTY", "DUTY", value, "Duty cycle = {value}%")


@awg_group.command("load")
@click.argument("value", type=click.Choice(LOADS), required=False)
@click.pass_context
def load(ctx, value):
    """Get/set output load (HZ = high-impedance, 50 = 50 ohm)."""
    o = osc(ctx)
    if value is None:
        _echo_part(ops_awg.query_output(o), "LOAD")
    else:
        ops_awg.set_load(o, value)
        click.echo(f"Load = {value}")


@awg_group.command("set")
@click.option("--wave", "-w", type=click.Choice(WAVE_TYPES), help="Waveform type.")
@click.option("--freq", "-f", type=float, help="Frequency (Hz).")
@click.option("--amp", "-a", type=float, help="Amplitude (Vpp).")
@click.option("--offset", "-o", type=float, help="DC offset (V).")
@click.option("--phase", "-p", type=float, help="Phase (degrees).")
@click.option("--duty", "-d", type=float, help="Duty cycle (%).")
@click.option("--on", "enable", is_flag=True, help="Turn output on.")
@click.option("--off", "disable", is_flag=True, help="Turn output off.")
@click.pass_context
def set_(ctx, wave, freq, amp, offset, phase, duty, enable, disable):
    """Configure multiple AWG parameters at once."""
    o = osc(ctx)
    pairs = [
        (k, v)
        for k, v in (("WVTP", wave), ("FRQ", freq), ("AMP", amp),
                     ("OFST", offset), ("PHSE", phase), ("DUTY", duty))
        if v is not None
    ]
    for k, v in pairs:
        ops_awg.write_basic(o, k, v)
    if enable:
        ops_awg.set_output(o, True)
    if disable:
        ops_awg.set_output(o, False)
    if pairs or enable or disable:
        click.echo("AWG configured.")
        if pairs:
            click.echo(ops_awg.query_basic(o))
    else:
        click.echo(ops_awg.query_basic(o))


@awg_group.command("arb")
@click.argument("name", type=click.Choice(ARB_WAVEFORMS), required=False)
@click.pass_context
def arb(ctx, name):
    """Get/set the arbitrary waveform (built-in shapes)."""
    o = osc(ctx)
    if name is None:
        click.echo(ops_awg.query_arb(o))
    else:
        ops_awg.set_arb(o, name)
        click.echo(f"Arbitrary waveform = {name}")


@awg_group.command("burst")
@click.option("--on", "enable", is_flag=True, help="Enable burst mode.")
@click.option("--off", "disable", is_flag=True, help="Disable burst mode.")
@click.option("--cycles", "-c", type=int, default=None, help="Number of cycles per burst (NCYC).")
@click.option("--period", type=float, default=None, help="Burst period (s).")
@click.pass_context
def burst(ctx, enable, disable, cycles, period):
    """Configure burst mode (C1:BTWV)."""
    o = osc(ctx)
    if enable:
        ops_awg.write_burst(o, enabled=True)
    if disable:
        ops_awg.write_burst(o, enabled=False)
    ops_awg.write_burst(o, cycles=cycles, period=period)
    click.echo(ops_awg.query_burst(o))


@awg_group.command("sweep")
@click.option("--on", "enable", is_flag=True, help="Enable sweep mode.")
@click.option("--off", "disable", is_flag=True, help="Disable sweep mode.")
@click.option("--start", type=float, default=None, help="Start frequency (Hz).")
@click.option("--stop", type=float, default=None, help="Stop frequency (Hz).")
@click.option("--time", "time_", type=float, default=None, help="Sweep time (s).")
@click.option("--direction", type=click.Choice(ops_awg.SWEEP_DIRECTIONS), default=None, help="Sweep direction.")
@click.pass_context
def sweep(ctx, enable, disable, start, stop, time_, direction):
    """Configure frequency sweep (C1:SWWV)."""
    o = osc(ctx)
    if enable:
        ops_awg.write_sweep(o, enabled=True)
    if disable:
        ops_awg.write_sweep(o, enabled=False)
    ops_awg.write_sweep(o, start=start, stop=stop, time=time_, direction=direction)
    click.echo(ops_awg.query_sweep(o))


@awg_group.command("modulate")
@click.option("--on", "enable", is_flag=True, help="Enable modulation.")
@click.option("--off", "disable", is_flag=True, help="Disable modulation.")
@click.pass_context
def modulate(ctx, enable, disable):
    """Enable/disable modulation (C1:MDWV)."""
    o = osc(ctx)
    if enable:
        ops_awg.set_modulation(o, True)
    if disable:
        ops_awg.set_modulation(o, False)
    click.echo(ops_awg.query_modulation(o))


@awg_group.command("sync")
@click.argument("value", type=click.Choice(["ON", "OFF"]), required=False)
@click.pass_context
def sync(ctx, value):
    """Get/set the sync output (C1:SYNC)."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_awg.query_sync(o))
    else:
        ops_awg.set_sync(o, value)
        click.echo(f"Sync output = {value}")
