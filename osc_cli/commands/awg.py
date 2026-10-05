"""AWG (arbitrary waveform generator) control commands.

The SDS1104X-E has an integrated function/AWG generator controlled via a
Siglent-style command set (NOT the LeCroy X-Stream dialect used by the rest
of the scope). Commands are prefixed with C1:.

Verified against the device:
- C1:BSWV  (basic wave: type, freq, amp, offset, phase, duty)
- C1:OUTP  (output on/off, load, polarity)
- C1:MDWV  (modulation)
"""

from __future__ import annotations

import click

from ..cli import osc

WAVE_TYPES = ["SINE", "SQUARE", "RAMP", "PULSE", "NOISE", "ARB", "DC"]
LOADS = ["HZ", "50"]

# Arbitrary waveform names discovered on the device (via C1:ARWV INDEX,n).
ARB_WAVEFORMS = [
    "StairUp", "StairDn", "StairUD", "Ppulse", "Npulse", "Trapezia",
    "Upramp", "Dnramp", "ExpFal", "ExpRise",
]


@click.group(name="awg")
def awg_group():
    """Waveform generator (AWG) control."""


def _bset(osc_obj, *pairs):
    for k, v in pairs:
        osc_obj.write(f"C1:BSWV {k},{v}")


@awg_group.command("status")
@click.pass_context
def status(ctx):
    """Show the full AWG configuration."""
    o = osc(ctx)
    click.echo(f"Output : {o.query('C1:OUTP?')}")
    click.echo(f"Wave   : {o.query('C1:BSWV?')}")
    click.echo(f"Mod    : {o.query('C1:MDWV?')}")


@awg_group.command("on")
@click.pass_context
def on(ctx):
    """Turn the AWG output on."""
    osc(ctx).write("C1:OUTP ON")
    click.echo("AWG output enabled.")


@awg_group.command("off")
@click.pass_context
def off(ctx):
    """Turn the AWG output off."""
    osc(ctx).write("C1:OUTP OFF")
    click.echo("AWG output disabled.")


@awg_group.command("wave")
@click.argument("value", type=click.Choice(WAVE_TYPES), required=False)
@click.pass_context
def wave(ctx, value):
    """Get/set the waveform type (SINE/SQUARE/RAMP/PULSE/NOISE/ARB/DC)."""
    o = osc(ctx)
    if value is None:
        full = o.query("C1:BSWV?")
        for part in full.split(","):
            if part.startswith("WVTP"):
                click.echo(part)
                return
        click.echo(full)
    else:
        o.write(f"C1:BSWV WVTP,{value}")
        click.echo(f"Waveform type = {value}")


@awg_group.command("freq")
@click.argument("value", type=float, required=False)
@click.pass_context
def freq(ctx, value):
    """Get/set the output frequency (Hz)."""
    o = osc(ctx)
    if value is None:
        full = o.query("C1:BSWV?")
        for part in full.split(","):
            if part.startswith("FRQ"):
                click.echo(part)
                return
    else:
        o.write(f"C1:BSWV FRQ,{value}")
        click.echo(f"Frequency = {value} Hz")


@awg_group.command("amp")
@click.argument("value", type=float, required=False)
@click.pass_context
def amp(ctx, value):
    """Get/set the amplitude (Vpp)."""
    o = osc(ctx)
    if value is None:
        full = o.query("C1:BSWV?")
        for part in full.split(","):
            if part.startswith("AMP,"):
                click.echo(part)
                return
    else:
        o.write(f"C1:BSWV AMP,{value}")
        click.echo(f"Amplitude = {value} Vpp")


@awg_group.command("offset")
@click.argument("value", type=float, required=False)
@click.pass_context
def offset(ctx, value):
    """Get/set the DC offset (V)."""
    o = osc(ctx)
    if value is None:
        full = o.query("C1:BSWV?")
        for part in full.split(","):
            if part.startswith("OFST"):
                click.echo(part)
                return
    else:
        o.write(f"C1:BSWV OFST,{value}")
        click.echo(f"Offset = {value} V")


@awg_group.command("phase")
@click.argument("value", type=float, required=False)
@click.pass_context
def phase(ctx, value):
    """Get/set the phase (degrees)."""
    o = osc(ctx)
    if value is None:
        full = o.query("C1:BSWV?")
        for part in full.split(","):
            if part.startswith("PHSE"):
                click.echo(part)
                return
    else:
        o.write(f"C1:BSWV PHSE,{value}")
        click.echo(f"Phase = {value} deg")


@awg_group.command("duty")
@click.argument("value", type=float, required=False)
@click.pass_context
def duty(ctx, value):
    """Get/set the square-wave duty cycle (%)."""
    o = osc(ctx)
    if value is None:
        full = o.query("C1:BSWV?")
        for part in full.split(","):
            if part.startswith("DUTY"):
                click.echo(part)
                return
    else:
        o.write(f"C1:BSWV DUTY,{value}")
        click.echo(f"Duty cycle = {value}%")


@awg_group.command("load")
@click.argument("value", type=click.Choice(LOADS), required=False)
@click.pass_context
def load(ctx, value):
    """Get/set output load (HZ = high-impedance, 50 = 50 ohm)."""
    o = osc(ctx)
    if value is None:
        full = o.query("C1:OUTP?")
        for part in full.split(","):
            if part.startswith("LOAD"):
                click.echo(part)
                return
    else:
        o.write(f"C1:OUTP LOAD,{value}")
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
    pairs = []
    if wave is not None:
        pairs.append(("WVTP", wave))
    if freq is not None:
        pairs.append(("FRQ", freq))
    if amp is not None:
        pairs.append(("AMP", amp))
    if offset is not None:
        pairs.append(("OFST", offset))
    if phase is not None:
        pairs.append(("PHSE", phase))
    if duty is not None:
        pairs.append(("DUTY", duty))
    for k, v in pairs:
        o.write(f"C1:BSWV {k},{v}")
    if enable:
        o.write("C1:OUTP ON")
    if disable:
        o.write("C1:OUTP OFF")
    if pairs or enable or disable:
        click.echo("AWG configured.")
        if pairs:
            click.echo(o.query("C1:BSWV?"))
    else:
        click.echo(o.query("C1:BSWV?"))


@awg_group.command("arb")
@click.argument("name", type=click.Choice(ARB_WAVEFORMS), required=False)
@click.pass_context
def arb(ctx, name):
    """Get/set the arbitrary waveform (built-in shapes)."""
    o = osc(ctx)
    if name is None:
        click.echo(o.query("C1:ARWV?"))
    else:
        o.write(f"C1:ARWV INDEX,{name}")
        o.write("C1:BSWV WVTP,ARB")
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
        o.write("C1:BTWV STATE,ON")
    if disable:
        o.write("C1:BTWV STATE,OFF")
    if cycles is not None:
        o.write(f"C1:BTWV NCYC,{cycles}")
    if period is not None:
        o.write(f"C1:BTWV PRD,{period}")
    if not any([enable, disable, cycles is not None, period is not None]):
        click.echo(o.query("C1:BTWV?"))
    else:
        click.echo(o.query("C1:BTWV?"))


@awg_group.command("sweep")
@click.option("--on", "enable", is_flag=True, help="Enable sweep mode.")
@click.option("--off", "disable", is_flag=True, help="Disable sweep mode.")
@click.option("--start", type=float, default=None, help="Start frequency (Hz).")
@click.option("--stop", type=float, default=None, help="Stop frequency (Hz).")
@click.option("--time", "time_", type=float, default=None, help="Sweep time (s).")
@click.option("--direction", type=click.Choice(["UP", "DOWN"]), default=None, help="Sweep direction.")
@click.pass_context
def sweep(ctx, enable, disable, start, stop, time_, direction):
    """Configure frequency sweep (C1:SWWV)."""
    o = osc(ctx)
    if enable:
        o.write("C1:SWWV STATE,ON")
    if disable:
        o.write("C1:SWWV STATE,OFF")
    if start is not None:
        o.write(f"C1:SWWV START,{start}")
    if stop is not None:
        o.write(f"C1:SWWV STOP,{stop}")
    if time_ is not None:
        o.write(f"C1:SWWV TIME,{time_}")
    if direction is not None:
        o.write(f"C1:SWWV DIR,{direction}")
    if not any([enable, disable, start is not None, stop is not None, time_ is not None, direction is not None]):
        click.echo(o.query("C1:SWWV?"))
    else:
        click.echo(o.query("C1:SWWV?"))


@awg_group.command("modulate")
@click.option("--on", "enable", is_flag=True, help="Enable modulation.")
@click.option("--off", "disable", is_flag=True, help="Disable modulation.")
@click.pass_context
def modulate(ctx, enable, disable):
    """Enable/disable modulation (C1:MDWV)."""
    o = osc(ctx)
    if enable:
        o.write("C1:MDWV STATE,ON")
    if disable:
        o.write("C1:MDWV STATE,OFF")
    if not enable and not disable:
        click.echo(o.query("C1:MDWV?"))
    else:
        click.echo(o.query("C1:MDWV?"))


@awg_group.command("sync")
@click.argument("value", type=click.Choice(["ON", "OFF"]), required=False)
@click.pass_context
def sync(ctx, value):
    """Get/set the sync output (C1:SYNC)."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("C1:SYNC?"))
    else:
        o.write(f"C1:SYNC {value}")
        click.echo(f"Sync output = {value}")
