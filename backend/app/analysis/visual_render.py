from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import struct
import zlib

from backend.app.analysis.bars import MarketBar


RENDERER_NAME = "canonical_candlestick_renderer"
RENDERER_VERSION = "1.0.0"
RENDER_SPEC_VERSION = "1.0.0"
CHANNELS = 3
COLOR_SPACE = "rgb8"
GAP_DETECTED = "gap_detected"


@dataclass(frozen=True)
class RenderSpec:
    """Geometric/colour configuration for the canonical renderer. Deliberately
    excludes channel count and colour space -- those are fixed renderer
    constants (RGB8), not a caller choice, per the Phase 5 contract's
    "kanonik görüntü" requirement that the format itself stay canonical.
    """

    width: int = 512
    height: int = 256
    padding_top: int = 8
    padding_bottom: int = 8
    padding_left: int = 8
    padding_right: int = 8
    background_rgb: tuple[int, int, int] = (255, 255, 255)
    bullish_rgb: tuple[int, int, int] = (0, 128, 0)
    bearish_rgb: tuple[int, int, int] = (192, 0, 0)
    wick_rgb: tuple[int, int, int] = (32, 32, 32)
    version: str = RENDER_SPEC_VERSION


DEFAULT_RENDER_SPEC = RenderSpec()


@dataclass(frozen=True)
class CanonicalImage:
    version: str
    renderer_name: str
    renderer_version: str
    render_spec_id: str
    symbol: str
    timeframe: str
    n_bars: int
    width: int
    height: int
    channels: int
    color_space: str
    window_first_event_id: str
    window_last_event_id: str
    first_bar_start_at: str
    last_bar_end_at: str
    known_at: str
    price_min: float
    price_max: float
    layers: tuple[str, ...]
    missing_bar_count: int
    missing_bar_indices: tuple[int, ...]
    quality_flags: tuple[str, ...]
    bar_fingerprint: str
    image_checksum: str
    fingerprint: str
    png_bytes: bytes
    interpretation: str = "research_observation_not_trading_signal"


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(
        payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def render_spec_id(spec: RenderSpec) -> str:
    return f"sha256:{sha256(_canonical_json(asdict(spec))).hexdigest()}"


def _validate_bars(bars: tuple[MarketBar, ...]) -> None:
    if not bars:
        raise ValueError("bars must not be empty")
    symbol = bars[0].symbol
    timeframe = bars[0].timeframe
    previous_end: str | None = None
    for bar in bars:
        if bar.symbol != symbol or bar.timeframe != timeframe:
            raise ValueError("bars must share the same symbol and timeframe")
        if previous_end is not None and bar.start_at < previous_end:
            raise ValueError("bars must be sorted by start_at without overlap")
        previous_end = bar.end_at


def _validate_spec(spec: RenderSpec) -> None:
    if spec.width <= spec.padding_left + spec.padding_right:
        raise ValueError("render spec width must exceed left+right padding")
    if spec.height <= spec.padding_top + spec.padding_bottom:
        raise ValueError("render spec height must exceed top+bottom padding")


def _detect_gaps(bars: tuple[MarketBar, ...]) -> tuple[int, ...]:
    return tuple(
        index
        for index in range(1, len(bars))
        if bars[index].start_at != bars[index - 1].end_at
    )


def _column_bounds(index: int, n: int, *, plot_left: int, plot_width: int) -> tuple[int, int]:
    start = plot_left + (index * plot_width) // n
    end = plot_left + ((index + 1) * plot_width) // n
    return start, max(end, start + 1)


def _price_to_row(
    price: float, *, price_min: float, price_max: float, plot_top: int, plot_height: int
) -> int:
    if price_max <= price_min:
        return plot_top + plot_height // 2
    fraction = (price_max - price) / (price_max - price_min)
    row = plot_top + int(fraction * (plot_height - 1))
    return min(max(row, plot_top), plot_top + plot_height - 1)


def _new_canvas(width: int, height: int, rgb: tuple[int, int, int]) -> bytearray:
    return bytearray(bytes(rgb) * width * height)


def _fill_rect(
    canvas: bytearray, width: int, x0: int, x1: int, y0: int, y1: int, rgb: tuple[int, int, int]
) -> None:
    if x1 <= x0 or y1 <= y0:
        return
    row = bytes(rgb) * (x1 - x0)
    for y in range(y0, y1):
        offset = (y * width + x0) * 3
        canvas[offset : offset + len(row)] = row


def _draw_vline(
    canvas: bytearray, width: int, x: int, y0: int, y1: int, rgb: tuple[int, int, int]
) -> None:
    pixel = bytes(rgb)
    for y in range(min(y0, y1), max(y0, y1) + 1):
        offset = (y * width + x) * 3
        canvas[offset : offset + 3] = pixel


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _encode_png(pixels: bytes, *, width: int, height: int) -> bytes:
    stride = width * 3
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw.extend(pixels[y * stride : (y + 1) * stride])
    compressed = zlib.compress(bytes(raw), 9)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    signature = b"\x89PNG\r\n\x1a\n"
    return (
        signature
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )


def _fingerprint(payload: dict) -> str:
    return f"sha256:{sha256(_canonical_json(payload)).hexdigest()}"


def render_canonical_chart(
    bars: tuple[MarketBar, ...],
    *,
    bar_fingerprint: str,
    spec: RenderSpec = DEFAULT_RENDER_SPEC,
) -> CanonicalImage:
    """Render a deterministic candlestick image from Phase 4's already-closed
    bars. Only reads `bars` (never a label, outcome, or future bar) -- the
    Phase 5 contract's causality/no-lookahead boundary is satisfied by
    construction: nothing besides already-closed bars is ever accepted as
    input, and `known_at` is the last bar's own `end_at` (the earliest UTC
    instant every pixel in the image could actually exist). Gaps between
    consecutive bars (missing intervals) are recorded in `missing_bar_indices`
    and NOT silently filled with fabricated candles.
    """
    _validate_bars(bars)
    _validate_spec(spec)
    normalized_fingerprint = bar_fingerprint.strip()
    if not normalized_fingerprint:
        raise ValueError("bar_fingerprint must not be empty")

    n = len(bars)
    symbol = bars[0].symbol
    timeframe = bars[0].timeframe
    missing_bar_indices = _detect_gaps(bars)
    quality_flags = (GAP_DETECTED,) if missing_bar_indices else ()

    price_min = min(bar.low for bar in bars)
    price_max = max(bar.high for bar in bars)

    plot_left = spec.padding_left
    plot_top = spec.padding_top
    plot_width = spec.width - spec.padding_left - spec.padding_right
    plot_height = spec.height - spec.padding_top - spec.padding_bottom

    canvas = _new_canvas(spec.width, spec.height, spec.background_rgb)

    for index, bar in enumerate(bars):
        col_start, col_end = _column_bounds(index, n, plot_left=plot_left, plot_width=plot_width)
        center_x = (col_start + col_end - 1) // 2
        high_row = _price_to_row(
            bar.high, price_min=price_min, price_max=price_max, plot_top=plot_top, plot_height=plot_height
        )
        low_row = _price_to_row(
            bar.low, price_min=price_min, price_max=price_max, plot_top=plot_top, plot_height=plot_height
        )
        open_row = _price_to_row(
            bar.open, price_min=price_min, price_max=price_max, plot_top=plot_top, plot_height=plot_height
        )
        close_row = _price_to_row(
            bar.close, price_min=price_min, price_max=price_max, plot_top=plot_top, plot_height=plot_height
        )
        _draw_vline(canvas, spec.width, center_x, high_row, low_row, spec.wick_rgb)
        body_top = min(open_row, close_row)
        body_bottom = max(open_row, close_row) + 1
        color = spec.bullish_rgb if bar.close >= bar.open else spec.bearish_rgb
        _fill_rect(canvas, spec.width, col_start, col_end, body_top, body_bottom, color)

    pixels = bytes(canvas)
    image_checksum = f"sha256:{sha256(pixels).hexdigest()}"
    spec_id = render_spec_id(spec)

    metadata = {
        "bar_fingerprint": normalized_fingerprint,
        "channels": CHANNELS,
        "color_space": COLOR_SPACE,
        "first_bar_start_at": bars[0].start_at,
        "height": spec.height,
        "image_checksum": image_checksum,
        "known_at": bars[-1].end_at,
        "last_bar_end_at": bars[-1].end_at,
        "layers": ["candle_ohlc"],
        "missing_bar_count": len(missing_bar_indices),
        "missing_bar_indices": list(missing_bar_indices),
        "n_bars": n,
        "price_max": price_max,
        "price_min": price_min,
        "quality_flags": list(quality_flags),
        "render_spec_id": spec_id,
        "renderer_name": RENDERER_NAME,
        "renderer_version": RENDERER_VERSION,
        "symbol": symbol,
        "timeframe": timeframe,
        "version": RENDERER_VERSION,
        "window_first_event_id": bars[0].first_event_id,
        "window_last_event_id": bars[-1].last_event_id,
    }

    return CanonicalImage(
        version=RENDERER_VERSION,
        renderer_name=RENDERER_NAME,
        renderer_version=RENDERER_VERSION,
        render_spec_id=spec_id,
        symbol=symbol,
        timeframe=timeframe,
        n_bars=n,
        width=spec.width,
        height=spec.height,
        channels=CHANNELS,
        color_space=COLOR_SPACE,
        window_first_event_id=bars[0].first_event_id,
        window_last_event_id=bars[-1].last_event_id,
        first_bar_start_at=bars[0].start_at,
        last_bar_end_at=bars[-1].end_at,
        known_at=bars[-1].end_at,
        price_min=price_min,
        price_max=price_max,
        layers=("candle_ohlc",),
        missing_bar_count=len(missing_bar_indices),
        missing_bar_indices=missing_bar_indices,
        quality_flags=quality_flags,
        bar_fingerprint=normalized_fingerprint,
        image_checksum=image_checksum,
        fingerprint=_fingerprint(metadata),
        png_bytes=_encode_png(pixels, width=spec.width, height=spec.height),
    )
