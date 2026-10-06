"""Shared pieces for the tool modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

import anyio
from mcp.server.mcpserver import Context
from mcp_types import ToolAnnotations
from pydantic import Field

from ..session import Session
from ..storage import Storage


@dataclass
class Deps:
    session: Session
    storage: Storage
    max_samples: int


def _hints(*, read_only: bool, idempotent: bool, destructive: bool = False) -> ToolAnnotations:
    return ToolAnnotations(
        read_only_hint=read_only,
        destructive_hint=destructive,
        idempotent_hint=idempotent,
        open_world_hint=False,
    )


READ = _hints(read_only=True, idempotent=True)
WRITE = _hints(read_only=False, idempotent=True)
WRITE_ONCE = _hints(read_only=False, idempotent=False)
DANGER = _hints(read_only=False, idempotent=True, destructive=True)
DANGER_ONCE = _hints(read_only=False, idempotent=False, destructive=True)

Source = Literal["C1", "C2", "C3", "C4"]
ChannelNumber = Annotated[int, Field(ge=1, le=4, description="Channel number, 1-4.")]

STOPPED_NOTE = (
    "Acquisition was stopped so every channel comes from the same capture. "
    "Resume it with siglent_control_acquisition(action='run')."
)


def report_progress(ctx: Context, done: float, total: float, message: str) -> None:
    """Send a progress notification from a sync tool (runs in a worker thread)."""
    anyio.from_thread.run(ctx.report_progress, done, total, message)
