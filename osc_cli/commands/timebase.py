"""Timebase (horizontal) and acquisition commands (LeCroy dialect).

The command strings live in osc_cli.ops.timebase and osc_cli.ops.acquisition.
"""

from __future__ import annotations

import click

from ..cli import osc
from ..ops import acquisition as ops_acq
from ..ops import timebase as ops_tb


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
        click.echo(ops_tb.query_field(o, "tdiv"))
    else:
        ops_tb.write_field(o, "tdiv", value)
        click.echo(f"Time/div = {value} s")


@timebase_group.command("delay")
@click.argument("value", type=float, required=False)
@click.pass_context
def delay(ctx, value):
    """Get/set horizontal trigger delay (s) via TRDL."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_tb.query_field(o, "delay"))
    else:
        ops_tb.write_field(o, "delay", value)
        click.echo(f"Delay = {value} s")


@timebase_group.command("samplerate")
@click.pass_context
def samplerate(ctx):
    """Query the current sample rate (Sa/s) via SARA."""
    click.echo(ops_tb.query_field(osc(ctx), "sample_rate"))


@timebase_group.command("memory")
@click.argument("value", required=False)
@click.pass_context
def memory(ctx, value):
    """Get/set memory size (e.g. 14M, 1.4M) via MSIZ."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_tb.query_field(o, "memory"))
    else:
        ops_tb.write_field(o, "memory", value)
        click.echo(f"Memory size = {value}")


@timebase_group.command("averages")
@click.argument("value", type=int, required=False)
@click.pass_context
def averages(ctx, value):
    """Get/set acquisition averages via AVGA."""
    o = osc(ctx)
    if value is None:
        click.echo(ops_tb.query_field(o, "averages"))
    else:
        ops_tb.write_field(o, "averages", value)
        click.echo(f"Averages = {value}")


@timebase_group.command("run")
@click.pass_context
def run(ctx):
    """Resume continuous acquisition (TRMD AUTO/NORM)."""
    ops_acq.resume(osc(ctx))
    click.echo("Acquisition running.")


@timebase_group.command("stop")
@click.pass_context
def stop(ctx):
    """Stop acquisition (STOP)."""
    ops_acq.stop(osc(ctx))
    click.echo("Acquisition stopped.")


@timebase_group.command("status")
@click.pass_context
def status(ctx):
    """Show timebase/acquisition settings."""
    o = osc(ctx)
    labels = {"tdiv": "Time/div", "delay": "Delay", "sample_rate": "Sample rate",
              "memory": "Memory", "averages": "Averages"}
    for field, label in labels.items():
        click.echo(f"{label:11s}: {ops_tb.query_field(o, field)}")
