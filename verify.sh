#!/usr/bin/env bash
# Verify the oscilloscope connection end-to-end.
set -uo pipefail

PY="$(dirname "$0")/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

"$PY" - "$@" <<'EOF'
import sys

from osc_cli.device import get_device, OscError


def main():
    try:
        osc = get_device()
    except OscError as e:
        print(f"CONNECTION FAILED: {e}")
        return 1

    print("Connected OK.")
    print("IDN       :", osc.idn())
    print("SampleRate:", osc.query("SARA?"))
    print("Timebase  :", osc.query("TDIV?"))
    print("Trigger   :", osc.query("TRMD?"))
    print("CH1 v/div :", osc.query("C1:VDIV?"))
    osc.close()
    print("All checks passed.")
    return 0


sys.exit(main())
EOF
