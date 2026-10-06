"""Waveform data capture commands (LeCroy block format)."""

from __future__ import annotations

import click

from ..cli import osc
from ..ops import waveform as ops_wave


@click.group(name="waveform")
def waveform_group():
    """Capture waveform sample data."""


@waveform_group.command("capture")
@click.option("--source", "-s", type=click.Choice(ops_wave.SOURCES), default="C1", show_default=True)
@click.option("--output", "-o", default=None, help="Output CSV file. Prints to stdout if omitted.")
@click.option("--points", "-n", type=int, default=0, help="Max points to keep, trimmed client-side (0 = all).")
@click.pass_context
def capture(ctx, source, output, points):
    """Capture waveform samples and save/print as CSV (index,voltage,time)."""
    raw = ops_wave.fetch(osc(ctx), source)
    # The firmware ignores NP and returns the full memory; trim client-side.
    rows = list(ops_wave.csv_lines(raw, limit=max(points, 0)))
    text = "\n".join(rows) + "\n"
    n = len(rows) - 1
    if output:
        with open(output, "w") as f:
            f.write(text)
        click.echo(
            f"Saved {n} samples to {output} "
            f"(vdiv={raw.vdiv:.4g}, interval={raw.horz_interval:.3g}s)"
        )
    else:
        click.echo(text)


@waveform_group.command("info")
@click.option("--source", "-s", type=click.Choice(ops_wave.SOURCES), default="C1", show_default=True)
@click.pass_context
def info(ctx, source):
    """Show waveform descriptor info (scaling) for a channel."""
    raw = ops_wave.fetch(osc(ctx), source)
    click.echo(f"Source        : {source}")
    click.echo(f"Points        : {raw.wave_count}")
    click.echo(f"Vertical div  : {raw.vdiv:.6g} V/div")
    click.echo(f"Vertical off. : {raw.offset:.6g}")
    click.echo(f"Horiz interval: {raw.horz_interval:.6g} s")
    click.echo(f"Horiz offset  : {raw.horz_offset:.6g} s")
    click.echo(f"First valid   : {raw.first_valid}")
    click.echo(f"Last valid    : {raw.last_valid}")
