"""Main CLI entry point for the SDS1104X-E oscilloscope."""

from __future__ import annotations

import sys

import click

from .device import OscError, Oscilloscope, get_device


class OscState:
    def __init__(self):
        self.osc: Oscilloscope | None = None


pass_osc = click.make_pass_decorator(OscState, ensure=True)


@click.group()
@click.option(
    "--resource",
    "-r",
    default=None,
    help="Explicit VISA resource string (e.g. USB0::0xF4EC::0xEE38::...::INSTR). "
    "Auto-detected if omitted.",
)
@click.option(
    "--timeout",
    "-t",
    default=5000,
    type=int,
    show_default=True,
    help="I/O timeout in milliseconds.",
)
@click.version_option(package_name="sds1104x-cli", prog_name="osc")
@click.pass_context
def cli(ctx, resource, timeout):
    """Control a Siglent SDS1104X-E oscilloscope over USBTMC (USB).

    The device connection is opened lazily on the first command that needs it.
    """
    ctx.obj = OscState()


def osc(ctx: click.Context) -> Oscilloscope:
    """Lazy connect helper: reuse the connection if already open."""
    state: OscState = ctx.find_root().obj
    if state.osc is None:
        params = ctx.find_root().params
        state.osc = get_device(
            params.get("resource"), params.get("timeout", 5000)
        )
    return state.osc


# Register command groups
from .commands.system import system_group
from .commands.channel import channel_group
from .commands.timebase import timebase_group
from .commands.trigger import trigger_group
from .commands.measure import measure_group
from .commands.math import math_group, display_group, cursor_group
from .commands.waveform import waveform_group
from .commands.screen import screen_group
from .commands.decode import decode_group
from .commands.advanced import counter_group, save_group
from .commands.awg import awg_group
from .commands.raw import raw

cli.add_command(system_group)
cli.add_command(channel_group)
cli.add_command(timebase_group)
cli.add_command(trigger_group)
cli.add_command(measure_group)
cli.add_command(math_group)
cli.add_command(display_group)
cli.add_command(cursor_group)
cli.add_command(waveform_group)
cli.add_command(screen_group)
cli.add_command(decode_group)
cli.add_command(counter_group)
cli.add_command(save_group)
cli.add_command(awg_group)
cli.add_command(raw)


@cli.result_callback()
@click.pass_obj
def _close(obj: OscState, *args, **kwargs):
    if obj.osc is not None:
        obj.osc.close()


def run():
    try:
        cli(prog_name="osc")
    except OscError as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.secho("Interrupted.", fg="yellow", err=True)
        sys.exit(130)


if __name__ == "__main__":
    run()
