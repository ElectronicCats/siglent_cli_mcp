"""Screenshot and waveform capture tools."""

from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import Context, Image, MCPServer
from mcp_types import TextContent
from pydantic import Field

from osc_cli.ops import screen, waveform

from ..errors import tool_errors
from ..models import WaveformResult
from .common import READ, STOPPED_NOTE, WRITE, Deps, Source, report_progress


def register(server: MCPServer, deps: Deps) -> None:
    session, storage = deps.session, deps.storage

    @server.tool(annotations=READ, structured_output=False)
    @tool_errors
    def siglent_capture_screen(
        save_path: Annotated[
            str | None,
            Field(description="Optional PNG file name, relative to the data directory, to also save the image."),
        ] = None,
    ) -> list[Image | TextContent]:
        """Screenshot of the oscilloscope display as a PNG image you can look at.

        Good for a quick visual check of traces, cursors and on-screen measurements.
        For numbers use siglent_measure or siglent_capture_waveform instead.
        """
        path = None
        if save_path:
            if not save_path.lower().endswith(".png"):
                raise ValueError("save_path must end in .png")
            path = storage.output_path("screens", ".png", save_path)
        png = session.run(screen.capture_png, retry=True)
        content: list[Image | TextContent] = [Image(data=png, format="png")]
        if path:
            path.write_bytes(png)
            content.append(TextContent(type="text", text=f"Saved to {path}"))
        return content

    @server.tool(annotations=WRITE)
    @tool_errors
    def siglent_capture_waveform(
        ctx: Context,
        sources: Annotated[
            list[Source],
            Field(min_length=1, max_length=4, description='Channels to capture, e.g. ["C1"] or ["C1", "C2"].'),
        ],
        max_points: Annotated[
            int, Field(ge=2, le=5000, description="Points returned per channel (min/max decimated).")
        ] = 500,
        save_csv: Annotated[
            bool, Field(description="Also save every sample to a CSV (index,voltage,time) and return its path.")
        ] = True,
    ) -> WaveformResult:
        """Capture sampled data from one or more channels.

        Returns per channel: statistics over all samples (min, max, vpp, mean, rms
        in V; sample_rate in Sa/s; duration in s), up to max_points [time_s, volts]
        pairs decimated with min/max buckets so glitches are kept, and the path of a
        CSV with every sample (usable by the decode tools via *_csv). A single channel
        is read without stopping the acquisition; with several channels the acquisition
        is stopped first so they share one trigger. Captures larger than OSC_MAX_SAMPLES
        points per channel are thinned on the scope (n and sample_rate then describe
        the thinned data); if the scope cannot thin them the call is refused — reduce
        the memory depth with siglent_set_timebase.
        """

        def csv_path_for(source):
            return storage.output_path("waveforms", f"_{source}.csv")

        def progress(done, total, message):
            report_progress(ctx, done, total, message)

        result = session.run(
            waveform.capture, sources, max_points, deps.max_samples,
            csv_path_for if save_csv else None, progress, retry=True,
        )
        if save_csv:
            storage.prune("waveforms")
        if result["acquisition_stopped"]:
            result["note"] = STOPPED_NOTE
        return result
