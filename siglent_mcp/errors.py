"""Turn every failure into a ToolError the agent can act on (no tracebacks)."""

from __future__ import annotations

import functools

from mcp.server.mcpserver.exceptions import ToolError

from osc_cli.device import OscError, OscNotFoundError, OscTransportError

from .session import ScopeBusy

NOT_FOUND = (
    "Oscilloscope not found. Check that it is powered on and connected over USB, "
    "and that the udev rule is installed (sudo ./install-udev.sh). Details: {detail}"
)
NOT_RESPONDING = (
    "The scope is not responding ({detail}). If this persists, power-cycle it; "
    "re-plugging the USB cable is not enough."
)
MAYBE_RAN = (
    "Communication failed ({detail}). The operation may or may not have run; "
    "check siglent_get_status before repeating it."
)
BUSY = "The scope is busy with another operation; retry in a few seconds."


def to_tool_error(exc: Exception) -> ToolError:
    if isinstance(exc, ScopeBusy):
        return ToolError(BUSY)
    if isinstance(exc, OscNotFoundError):
        return ToolError(NOT_FOUND.format(detail=exc))
    if isinstance(exc, OscTransportError):
        template = NOT_RESPONDING if getattr(exc, "retried", False) else MAYBE_RAN
        return ToolError(template.format(detail=exc))
    return ToolError(str(exc))


def tool_errors(fn):
    """Decorator for tool functions; place it under @server.tool(...)."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ToolError:
            raise
        except (ScopeBusy, OscError, ValueError, OSError) as exc:
            raise to_tool_error(exc) from exc

    return wrapper
