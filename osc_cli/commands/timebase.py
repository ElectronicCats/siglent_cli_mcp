"""Timebase (horizontal) and acquisition commands (LeCroy dialect).

Timebase: TDIV (time/div), TRDL (delay), HMAG (magnify), SARA (sample rate),
MSIZ (memory size). Acquisition: AVGA (averages), WFSU (waveform setup).
"""

from __future__ import annotations

import click

from ..cli import osc


@click.group(name="timebase")
def timebase_group():
    """Horizontal timebase and acquisition control."""


@timebase_group.command("tdiv")
@click.argument("value", type=float, required=False)
@click.pass_context
def tdiv(ctx, value):
    """Get/set horizontal scale (s/div) via TDIV."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("TDIV?"))
    else:
        o.write(f"TDIV {value}")
        click.echo(f"Time/div = {value} s")


@timebase_group.command("delay")
@click.argument("value", type=float, required=False)
@click.pass_context
def delay(ctx, value):
    """Get/set horizontal trigger delay (s) via TRDL."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("TRDL?"))
    else:
        o.write(f"TRDL {value}")
        click.echo(f"Delay = {value} s")


@timebase_group.command("samplerate")
@click.pass_context
def samplerate(ctx):
    """Query the current sample rate (Sa/s) via SARA."""
    click.echo(osc(ctx).query("SARA?"))


@timebase_group.command("memory")
@click.argument("value", required=False)
@click.pass_context
def memory(ctx, value):
    """Get/set memory size (e.g. 14M, 1.4M) via MSIZ."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("MSIZ?"))
    else:
        o.write(f"MSIZ {value}")
        click.echo(f"Memory size = {value}")


@timebase_group.command("averages")
@click.argument("value", type=int, required=False)
@click.pass_context
def averages(ctx, value):
    """Get/set acquisition averages via AVGA."""
    o = osc(ctx)
    if value is None:
        click.echo(o.query("AVGA?"))
    else:
        o.write(f"AVGA {value}")
        click.echo(f"Averages = {value}")


@timebase_group.command("run")
@click.pass_context
def run(ctx):
    """Start continuous acquisition (ARM)."""
    osc(ctx).write("ARM")
    click.echo("Acquisition running.")


@timebase_group.command("stop")
@click.pass_context
def stop(ctx):
    """Stop acquisition (STOP)."""
    osc(ctx).write("STOP")
    click.echo("Acquisition stopped.")


@timebase_group.command("status")
@click.pass_context
def status(ctx):
    """Show timebase/acquisition settings."""
    o = osc(ctx)
    click.echo(f"Time/div   : {o.query('TDIV?')}")
    click.echo(f"Delay      : {o.query('TRDL?')}")
    click.echo(f"Sample rate: {o.query('SARA?')}")
    click.echo(f"Memory     : {o.query('MSIZ?')}")
    click.echo(f"Averages   : {o.query('AVGA?')}")
