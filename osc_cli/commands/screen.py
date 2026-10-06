"""Screen capture (SCDP) command - returns raw BMP."""

from __future__ import annotations

import click

from ..cli import osc
from ..ops import screen as ops_screen


@click.group(name="screen")
def screen_group():
    """Capture the oscilloscope screen as an image."""


@screen_group.command("capture")
@click.option("--output", "-o", required=True, help="Output image file (e.g. shot.bmp).")
@click.pass_context
def capture(ctx, output):
    """Capture the screen (SCDP) and save as BMP."""
    data = ops_screen.capture_bmp(osc(ctx))
    with open(output, "wb") as f:
        f.write(data)
    click.echo(f"Screen saved to {output} ({len(data)} bytes, BMP).")
