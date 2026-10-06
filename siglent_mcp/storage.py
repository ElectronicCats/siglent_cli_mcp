"""Where captures, screenshots and decode results are written.

Every output path is confined to one data directory so a tool argument can
never write elsewhere on disk; auto-named files are pruned to the newest N.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


def default_root() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "siglent-mcp"


class Storage:
    def __init__(self, root: str | Path | None = None, keep: int | None = None):
        root = root or os.environ.get("OSC_DATA_DIR") or default_root()
        self.root = Path(root).expanduser().resolve()
        self.keep = keep if keep is not None else int(os.environ.get("OSC_KEEP_FILES", "20"))

    def output_path(self, kind: str, suffix: str, requested: str | None = None) -> Path:
        """A path inside the data directory.

        requested: a file name or relative path chosen by the caller; it must
        stay inside the data directory. Without it the file is auto-named
        under <root>/<kind>/ with a timestamp.
        """
        if requested:
            path = (self.root / requested).resolve()
            if not path.is_relative_to(self.root):
                raise ValueError(f"Output path must be inside the data directory {self.root}")
        else:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            path = self.root / kind / f"{stamp}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def prune(self, kind: str) -> None:
        """Keep only the newest `keep` auto-named files of one kind."""
        folder = self.root / kind
        if not folder.is_dir():
            return
        files = sorted((p for p in folder.iterdir() if p.is_file()), key=lambda p: p.stat().st_mtime)
        for old in files[: max(len(files) - self.keep, 0)]:
            old.unlink(missing_ok=True)

    @staticmethod
    def input_file(path: str) -> Path:
        """An existing regular file to read (CSV input for offline decoding)."""
        p = Path(path).expanduser()
        if not p.is_file():
            raise ValueError(f"CSV file not found: {p}")
        return p.resolve()
