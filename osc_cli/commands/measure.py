"""Automatic measurements via the LeCroy PAVA parameter readout.

Syntax: C<n>:PAVA? <param>  ->  "C<n>:PAVA <param>,<value><unit>"
Supported params (verified): VPP, PKPK, MAX, MIN, TOP, BASE, AMPL, MEAN, RMS,
PER, FREQ, RISE, FALL, WID, and ALL.
"""

from __future__ import annotations

import click

from ..cli import osc
from ..device import parse_float

PARAMS = [
    "PKPK", "MAX", "MIN", "TOP", "BASE", "AMPL", "MEAN", "RMS",
    "PER", "FREQ", "RISE", "FALL", "WID", "DUTY", "OVSN",
    "FPRE", "CMEAN", "CRMS",
]
SOURCES = ["C1", "C2", "C3", "C4"]


@click.group(name="measure")
def measure_group():
    """Automatic measurements (PAVA readout)."""


@measure_group.command("item")
@click.option("--item", "-i", type=click.Choice(PARAMS), required=True, help="Measurement type.")
@click.option("--source", "-s", type=click.Choice(SOURCES), default="C1", show_default=True, help="Source channel.")
@click.pass_context
def item(ctx, item, source):
    """Query a single measurement (e.g. --item VPP --source C1)."""
    click.echo(osc(ctx).query(f"{source}:PAVA? {item}"))


@measure_group.command("all")
@click.option("--source", "-s", type=click.Choice(SOURCES), default="C1", show_default=True)
@click.pass_context
def all_(ctx, source):
    """Query all common measurements for a channel."""
    o = osc(ctx)
    for p in ["PKPK", "MAX", "MIN", "MEAN", "RMS", "PER", "FREQ", "DUTY", "RISE", "FALL"]:
        try:
            val = o.query(f"{source}:PAVA? {p}")
            click.echo(val)
        except Exception as e:  # noqa: BLE001
            click.echo(f"{p}: (error: {e})")


@measure_group.command("vpp")
@click.option("--source", "-s", type=click.Choice(SOURCES), default="C1", show_default=True)
@click.pass_context
def vpp(ctx, source):
    click.echo(osc(ctx).query(f"{source}:PAVA? PKPK"))


@measure_group.command("freq")
@click.option("--source", "-s", type=click.Choice(SOURCES), default="C1", show_default=True)
@click.pass_context
def freq(ctx, source):
    click.echo(osc(ctx).query(f"{source}:PAVA? FREQ"))


@measure_group.command("rms")
@click.option("--source", "-s", type=click.Choice(SOURCES), default="C1", show_default=True)
@click.pass_context
def rms(ctx, source):
    click.echo(osc(ctx).query(f"{source}:PAVA? RMS"))


@measure_group.command("mean")
@click.option("--source", "-s", type=click.Choice(SOURCES), default="C1", show_default=True)
@click.pass_context
def mean(ctx, source):
    click.echo(osc(ctx).query(f"{source}:PAVA? MEAN"))


@measure_group.command("period")
@click.option("--source", "-s", type=click.Choice(SOURCES), default="C1", show_default=True)
@click.pass_context
def period(ctx, source):
    click.echo(osc(ctx).query(f"{source}:PAVA? PER"))
