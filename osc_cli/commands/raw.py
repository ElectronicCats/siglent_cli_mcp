"""Raw SCPI passthrough command (LeCroy dialect)."""

from __future__ import annotations

import click

from ..cli import osc


@click.command("raw")
@click.argument("command", nargs=-1, required=True)
@click.option("--query", "-q", is_flag=True, help="Append '?' to query instead of write.")
@click.pass_context
def raw(ctx, command, query):
    """Send an arbitrary command string to the scope.

    Examples:
        osc raw C1:VDIV 2.0
        osc raw -q "C1:PAVA? VPP"
        osc raw TDIV?
    """
    o = osc(ctx)
    cmd = " ".join(command)
    is_query = query or "?" in cmd
    if query and "?" not in cmd:
        cmd += "?"
    if is_query:
        click.echo(o.query(cmd))
    else:
        o.write(cmd)
