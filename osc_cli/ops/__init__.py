"""Instrument operations shared by the `osc` CLI and the MCP server.

Each function takes an Oscilloscope and returns plain data (dicts, numbers,
bytes). This is the only place that knows the LeCroy X-Stream command strings.
"""
