"""Return types of the tools. The SDK turns them into outputSchema.

typing_extensions.TypedDict is required: pydantic rejects typing.TypedDict on
Python < 3.12.
"""

from __future__ import annotations

from typing_extensions import NotRequired, TypedDict


class Identity(TypedDict):
    manufacturer: str
    model: str
    serial: str
    firmware: str
    raw: str


class ChannelState(TypedDict):
    channel: int
    enabled: bool
    probe: float | None
    coupling: str
    bw_limit: str
    unit: str
    invert: bool
    vdiv: float | None
    offset: float | None
    skew: float | None


class ChannelList(TypedDict):
    channels: list[ChannelState]


class TimebaseState(TypedDict):
    tdiv: float | None
    delay: float | None
    sample_rate: float | None
    memory: str
    averages: int | None


class TriggerState(TypedDict):
    mode: str
    type: str
    source: str | None
    level: float | None
    coupling: str | None


class Status(TypedDict):
    acquisition_state: str
    trigger: TriggerState
    timebase: TimebaseState
    channels: list[ChannelState]


class Measurement(TypedDict):
    value: float | None
    unit: str
    note: NotRequired[str]


class MeasureResult(TypedDict):
    source: str
    measurements: dict[str, Measurement]


class CounterState(TypedDict):
    enabled: bool | None
    frequency_hz: float | None
    raw: str


class BurstState(TypedDict):
    enabled: bool
    cycles: int | None
    period_s: float | None


class SweepState(TypedDict):
    enabled: bool
    start_hz: float | None
    stop_hz: float | None
    time_s: float | None
    direction: str | None


class AwgState(TypedDict):
    enabled: bool
    load: str | None
    wave: str | None
    freq_hz: float | None
    amp_vpp: float | None
    offset_v: float | None
    phase_deg: float | None
    duty_pct: float | None
    arb: str | None
    modulation: bool | None
    sync: bool | None
    burst: BurstState | None
    sweep: SweepState | None


class ErrorState(TypedDict):
    code: int | None
    message: str


class WaitResult(TypedDict):
    triggered: bool
    state: str
    waited_s: float


class AcquisitionResult(TypedDict):
    action: str
    trigger_mode: str | None
    state: str
    note: NotRequired[str]


class SerialTriggerResult(TypedDict):
    protocol: str
    settings: dict[str, str | int | float | None]


class MathState(TypedDict):
    function: str
    offset: float | None
    scale: float | None


class DisplayState(TypedDict):
    grid: str
    intensity: int | None
    menu: bool
    cursor_mode: str


class SetupResult(TypedDict):
    action: str
    path: str


class WaveformChannel(TypedDict):
    n: int
    sample_rate: float | None
    duration: float
    min: float
    max: float
    vpp: float
    mean: float
    rms: float
    vdiv: float
    offset: float
    horz_interval: float
    horz_offset: float
    points: list[list[float]]
    csv_path: NotRequired[str]


class WaveformResult(TypedDict):
    sources: dict[str, WaveformChannel]
    acquisition_stopped: bool
    note: NotRequired[str]


class Diagnostics(TypedDict):
    min_v: float
    max_v: float
    threshold_v: float
    hint: str


class UartFrame(TypedDict):
    time: float
    value: int
    ascii: str
    errors: list[str]


class I2cTransaction(TypedDict):
    time: float
    address: int | None
    read: bool
    data: list[int]
    acks: list[bool]
    repeated_start: bool


class SpiFrame(TypedDict):
    time: float
    mosi: list[int]
    miso: list[int]


class DecodePage(TypedDict):
    total: int
    count: int
    offset: int
    has_more: bool
    next_offset: int | None
    json_path: str
    acquisition_stopped: bool
    diagnostics: NotRequired[Diagnostics]
    note: NotRequired[str]


class UartPage(DecodePage):
    frames: list[UartFrame]
    text: str


class I2cPage(DecodePage):
    transactions: list[I2cTransaction]


class SpiPage(DecodePage):
    frames: list[SpiFrame]


class ResetResult(TypedDict):
    status: str


class SelfTestResult(TypedDict):
    passed: bool | None
    result: str
    raw: str


class RawResult(TypedDict):
    command: str
    response: str | None
