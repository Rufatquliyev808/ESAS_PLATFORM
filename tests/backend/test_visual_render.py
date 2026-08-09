from datetime import UTC, datetime, timedelta
import struct
import zlib

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.visual_render import (
    CHANNELS,
    COLOR_SPACE,
    GAP_DETECTED,
    RENDERER_NAME,
    RENDERER_VERSION,
    RenderSpec,
    render_canonical_chart,
    render_spec_id,
)


BASE_TIME = datetime(2026, 8, 9, 10, 0, tzinfo=UTC)
SMALL_SPEC = RenderSpec(width=40, height=20, padding_top=2, padding_bottom=2, padding_left=2, padding_right=2)


def bar(index: int, *, open_: float, high: float, low: float, close: float, gap: bool = False) -> MarketBar:
    start = BASE_TIME + timedelta(minutes=index + (10 if gap else 0))
    return MarketBar(
        symbol="GOLD", timeframe="M1",
        start_at=start.isoformat(timespec="microseconds"),
        end_at=(start + timedelta(minutes=1)).isoformat(timespec="microseconds"),
        open=open_, high=high, low=low, close=close,
        tick_count=2, tick_volume=2,
        spread_min=0.1, spread_max=0.1, spread_mean=0.1,
        first_event_id=f"event:{index}:0", last_event_id=f"event:{index}:1",
    )


def decode_png(png_bytes: bytes) -> tuple[int, int, bytes]:
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    offset = 8
    width = height = 0
    idat = b""
    while offset < len(png_bytes):
        (length,) = struct.unpack(">I", png_bytes[offset : offset + 4])
        tag = png_bytes[offset + 4 : offset + 8]
        data = png_bytes[offset + 8 : offset + 8 + length]
        if tag == b"IHDR":
            width, height = struct.unpack(">II", data[:8])
        elif tag == b"IDAT":
            idat += data
        offset += 12 + length
    raw = zlib.decompress(idat)
    stride = width * 3
    pixels = bytearray()
    for y in range(height):
        row_start = y * (stride + 1)
        pixels.extend(raw[row_start + 1 : row_start + 1 + stride])
    return width, height, bytes(pixels)


def pixel_at(pixels: bytes, width: int, x: int, y: int) -> tuple[int, int, int]:
    offset = (y * width + x) * 3
    return tuple(pixels[offset : offset + 3])


def test_rejects_empty_bars() -> None:
    with pytest.raises(ValueError):
        render_canonical_chart((), bar_fingerprint="sha256:source", spec=SMALL_SPEC)


def test_rejects_mixed_symbol_or_timeframe() -> None:
    a = bar(0, open_=1, high=2, low=0.5, close=1.5)
    b = MarketBar(**{**a.__dict__, "symbol": "SILVER"})
    with pytest.raises(ValueError):
        render_canonical_chart((a, b), bar_fingerprint="sha256:source", spec=SMALL_SPEC)


def test_rejects_empty_bar_fingerprint() -> None:
    bars = (bar(0, open_=1, high=2, low=0.5, close=1.5),)
    with pytest.raises(ValueError):
        render_canonical_chart(bars, bar_fingerprint="  ", spec=SMALL_SPEC)


def test_rejects_spec_too_small_for_padding() -> None:
    bars = (bar(0, open_=1, high=2, low=0.5, close=1.5),)
    tiny = RenderSpec(width=4, height=20, padding_left=2, padding_right=2)
    with pytest.raises(ValueError):
        render_canonical_chart(bars, bar_fingerprint="sha256:source", spec=tiny)


def test_same_input_and_spec_yield_identical_pixel_checksum_and_png_bytes() -> None:
    bars = tuple(bar(i, open_=1 + i * 0.01, high=1.5 + i * 0.01, low=0.5, close=1.2 + i * 0.01) for i in range(5))
    first = render_canonical_chart(bars, bar_fingerprint="sha256:source", spec=SMALL_SPEC)
    second = render_canonical_chart(bars, bar_fingerprint="sha256:source", spec=SMALL_SPEC)
    assert first.image_checksum == second.image_checksum
    assert first.png_bytes == second.png_bytes
    assert first.fingerprint == second.fingerprint


def test_different_spec_yields_different_render_spec_id_and_checksum() -> None:
    bars = tuple(bar(i, open_=1, high=1.5, low=0.5, close=1.2) for i in range(3))
    wide_spec = RenderSpec(width=60, height=20, padding_left=2, padding_right=2, padding_top=2, padding_bottom=2)
    first = render_canonical_chart(bars, bar_fingerprint="sha256:source", spec=SMALL_SPEC)
    second = render_canonical_chart(bars, bar_fingerprint="sha256:source", spec=wide_spec)
    assert render_spec_id(SMALL_SPEC) != render_spec_id(wide_spec)
    assert first.render_spec_id != second.render_spec_id
    assert first.image_checksum != second.image_checksum


def test_gap_between_bars_is_flagged_and_not_silently_filled() -> None:
    contiguous = bar(0, open_=1, high=1.5, low=0.5, close=1.2)
    gapped = bar(1, open_=1, high=1.5, low=0.5, close=1.2, gap=True)
    result = render_canonical_chart((contiguous, gapped), bar_fingerprint="sha256:source", spec=SMALL_SPEC)
    assert result.missing_bar_indices == (1,)
    assert result.missing_bar_count == 1
    assert result.quality_flags == (GAP_DETECTED,)
    assert result.n_bars == 2


def test_no_gap_yields_empty_quality_flags() -> None:
    bars = tuple(bar(i, open_=1, high=1.5, low=0.5, close=1.2) for i in range(3))
    result = render_canonical_chart(bars, bar_fingerprint="sha256:source", spec=SMALL_SPEC)
    assert result.missing_bar_indices == ()
    assert result.missing_bar_count == 0
    assert result.quality_flags == ()


def test_causality_known_at_is_the_last_bars_end_at() -> None:
    bars = tuple(bar(i, open_=1, high=1.5, low=0.5, close=1.2) for i in range(4))
    result = render_canonical_chart(bars, bar_fingerprint="sha256:source", spec=SMALL_SPEC)
    assert result.known_at == bars[-1].end_at
    assert result.first_bar_start_at == bars[0].start_at
    assert result.last_bar_end_at == bars[-1].end_at


def test_lineage_uses_first_and_last_bars_event_ids() -> None:
    bars = tuple(bar(i, open_=1, high=1.5, low=0.5, close=1.2) for i in range(4))
    result = render_canonical_chart(bars, bar_fingerprint="sha256:source", spec=SMALL_SPEC)
    assert result.window_first_event_id == bars[0].first_event_id
    assert result.window_last_event_id == bars[-1].last_event_id


def test_metadata_records_renderer_identity_and_layers() -> None:
    bars = (bar(0, open_=1, high=1.5, low=0.5, close=1.2),)
    result = render_canonical_chart(bars, bar_fingerprint="sha256:source", spec=SMALL_SPEC)
    assert result.renderer_name == RENDERER_NAME
    assert result.renderer_version == RENDERER_VERSION
    assert result.channels == CHANNELS
    assert result.color_space == COLOR_SPACE
    assert result.layers == ("candle_ohlc",)
    assert result.interpretation == "research_observation_not_trading_signal"


def test_png_bytes_decode_to_declared_width_and_height() -> None:
    bars = (bar(0, open_=1, high=1.5, low=0.5, close=1.2),)
    result = render_canonical_chart(bars, bar_fingerprint="sha256:source", spec=SMALL_SPEC)
    width, height, pixels = decode_png(result.png_bytes)
    assert width == SMALL_SPEC.width
    assert height == SMALL_SPEC.height
    assert len(pixels) == width * height * 3


def test_single_bullish_bar_body_uses_bullish_colour() -> None:
    bars = (bar(0, open_=1.0, high=1.5, low=0.5, close=1.4),)
    result = render_canonical_chart(bars, bar_fingerprint="sha256:source", spec=SMALL_SPEC)
    width, height, pixels = decode_png(result.png_bytes)
    plot_top = SMALL_SPEC.padding_top
    plot_height = SMALL_SPEC.height - SMALL_SPEC.padding_top - SMALL_SPEC.padding_bottom
    close_fraction = (1.5 - 1.4) / (1.5 - 0.5)
    close_row = plot_top + int(close_fraction * (plot_height - 1))
    center_x = SMALL_SPEC.padding_left + (SMALL_SPEC.width - SMALL_SPEC.padding_left - SMALL_SPEC.padding_right) // 2
    assert pixel_at(pixels, width, center_x, close_row) == SMALL_SPEC.bullish_rgb


def test_single_bearish_bar_body_uses_bearish_colour() -> None:
    bars = (bar(0, open_=1.4, high=1.5, low=0.5, close=1.0),)
    result = render_canonical_chart(bars, bar_fingerprint="sha256:source", spec=SMALL_SPEC)
    width, height, pixels = decode_png(result.png_bytes)
    plot_top = SMALL_SPEC.padding_top
    plot_height = SMALL_SPEC.height - SMALL_SPEC.padding_top - SMALL_SPEC.padding_bottom
    open_fraction = (1.5 - 1.4) / (1.5 - 0.5)
    open_row = plot_top + int(open_fraction * (plot_height - 1))
    center_x = SMALL_SPEC.padding_left + (SMALL_SPEC.width - SMALL_SPEC.padding_left - SMALL_SPEC.padding_right) // 2
    assert pixel_at(pixels, width, center_x, open_row) == SMALL_SPEC.bearish_rgb


def test_background_pixel_stays_background_colour() -> None:
    bars = (bar(0, open_=1.0, high=1.5, low=0.5, close=1.4),)
    result = render_canonical_chart(bars, bar_fingerprint="sha256:source", spec=SMALL_SPEC)
    width, _height, pixels = decode_png(result.png_bytes)
    assert pixel_at(pixels, width, 0, 0) == SMALL_SPEC.background_rgb


def test_flat_price_range_does_not_divide_by_zero() -> None:
    bars = (bar(0, open_=1.0, high=1.0, low=1.0, close=1.0),)
    result = render_canonical_chart(bars, bar_fingerprint="sha256:source", spec=SMALL_SPEC)
    assert result.price_min == 1.0
    assert result.price_max == 1.0
