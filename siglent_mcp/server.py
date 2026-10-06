"""MCP server exposing the Siglent SDS1104X-E oscilloscope over stdio."""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

from mcp.server.mcpserver import MCPServer

from osc_cli.ops.waveform import DEFAULT_MAX_SAMPLES

from .session import Session
from .storage import Storage
from .tools import capture, config, decode, status
from .tools.common import Deps

SERVER_NAME = "siglent_sds1104xe_mcp"
INSTRUCTIONS = """\
Controls a Siglent SDS1104X-E oscilloscope (4 channels and a built-in waveform \
generator) over USB.

Start with siglent_get_status to learn the current configuration before changing \
anything. Units are SI: volts, seconds, hertz. Tools marked destructive drive the \
generator output into the circuit under test or overwrite the scope configuration; \
confirm with the user before using them. Captures and decodes save the full data \
under the data directory and return the file paths."""
TOOL_MODULES = (status, config, capture, decode)


def create_server(session: Session | None = None, storage: Storage | None = None,
                  max_samples: int | None = None) -> MCPServer:
    session = session or Session()
    storage = storage or Storage()
    if max_samples is None:
        max_samples = int(os.environ.get("OSC_MAX_SAMPLES", DEFAULT_MAX_SAMPLES))

    @asynccontextmanager
    async def lifespan(_server):
        try:
            yield {}
        finally:
            session.close()

    server = MCPServer(SERVER_NAME, instructions=INSTRUCTIONS, lifespan=lifespan)
    deps = Deps(session=session, storage=storage, max_samples=max_samples)
    for module in TOOL_MODULES:
        module.register(server, deps)
    return server


# Module-level object so `mcp dev siglent_mcp/server.py` can find it.
server = create_server()


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=os.environ.get("OSC_LOG_LEVEL", "INFO"))
    server.run()


if __name__ == "__main__":
    main()
