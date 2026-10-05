"""Waveform data capture commands (LeCroy block format)."""

from __future__ import annotations

import click

from ..cli import osc


@click.group(name="waveform")
def waveform_group():
    """Capture waveform sample data."""


@waveform_group.command("capture")
@click.option("--source", "-s", type=click.Choice(["C1", "C2", "C3", "C4"]), default="C1", show_default=True)
@click.option("--output", "-o", default=None, help="Output CSV file. Prints to stdout if omitted.")
@click.option("--points", "-n", type=int, default=0, help="Max points to keep, trimmed client-side (0 = all).")
@click.pass_context
def capture(ctx, source, output, points):
    """Capture waveform samples and save/print as CSV (index,voltage,time)."""
    o = osc(ctx)
    data = o.get_waveform(source, points)
    if points > 0:
        # The firmware ignores NP and returns the full memory; trim client-side.
        data["samples"] = data["samples"][:points]
        data["times"] = data["times"][:points]

    rows = ["index,voltage,time"]
    for i, (v, t) in enumerate(zip(data["samples"], data["times"])):
        rows.append(f"{i},{v:.6f},{t:.9f}")

    text = "\n".join(rows) + "\n"
    n = len(data["samples"])
    if output:
        with open(output, "w") as f:
            f.write(text)
        click.echo(
            f"Saved {n} samples to {output} "
            f"(vdiv={data['vdiv']:.4g}, interval={data['horz_interval']:.3g}s)"
        )
    else:
        click.echo(text)


@waveform_group.command("info")
@click.option("--source", "-s", type=click.Choice(["C1", "C2", "C3", "C4"]), default="C1", show_default=True)
@click.pass_context
def info(ctx, source):
    """Show waveform descriptor info (scaling) for a channel."""
    o = osc(ctx)
    data = o.get_waveform(source, 0)
    click.echo(f"Source        : {source}")
    click.echo(f"Points        : {data['wave_count']}")
    click.echo(f"Vertical div  : {data['vdiv']:.6g} V/div")
    click.echo(f"Vertical off. : {data['offset']:.6g}")
    click.echo(f"Horiz interval: {data['horz_interval']:.6g} s")
    click.echo(f"Horiz offset  : {data['horz_offset']:.6g} s")
    click.echo(f"First valid   : {data['first_valid']}")
    click.echo(f"Last valid    : {data['last_valid']}")
