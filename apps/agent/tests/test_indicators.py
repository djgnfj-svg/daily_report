import pytest

from morningbrief.indicators import (
    compute_52w_position,
    compute_indicators,
    compute_ma,
    compute_rsi,
    compute_volume_ratio,
)


# ── MA ─────────────────────────────────────────────────────────────
def test_ma_uses_only_last_window():
    closes = [float(i) for i in range(1, 201)]
    out = compute_ma(closes)
    assert out["ma20"] == pytest.approx(190.5)
    assert out["ma60"] == pytest.approx(170.5)
    assert out["ma200"] == pytest.approx(100.5)


def test_ma_returns_none_when_short():
    out = compute_ma([10.0] * 50)
    assert out["ma20"] == 10.0
    assert out["ma60"] is None
    assert out["ma200"] is None


def test_ma_empty():
    assert compute_ma([]) == {"ma20": None, "ma60": None, "ma200": None}


# ── RSI ────────────────────────────────────────────────────────────
def test_rsi_all_gains_is_100():
    closes = [float(i) for i in range(1, 30)]
    assert compute_rsi(closes, 14) == 100.0


def test_rsi_all_losses_is_0():
    closes = [float(i) for i in range(30, 0, -1)]
    assert compute_rsi(closes, 14) == 0.0


def test_rsi_short_data_returns_none():
    assert compute_rsi([1.0, 2.0, 3.0], 14) is None


def test_rsi_in_range():
    closes = [10.0, 11.0, 10.5, 11.2, 10.8, 11.5, 11.0,
              11.8, 12.0, 11.5, 12.3, 12.0, 12.5, 13.0, 12.7]
    rsi = compute_rsi(closes, 14)
    assert rsi is not None
    assert 0 <= rsi <= 100


# ── 52주 위치 ──────────────────────────────────────────────────────
def test_52w_at_high():
    closes = [float(i) for i in range(1, 100)]  # 최신=99=고점
    assert compute_52w_position(closes) == 100.0


def test_52w_at_low():
    closes = [float(i) for i in range(99, 0, -1)]  # 최신=1=저점
    assert compute_52w_position(closes) == 0.0


def test_52w_flat():
    assert compute_52w_position([5.0] * 30) == 50.0


def test_52w_empty():
    assert compute_52w_position([]) is None


# ── 거래량 비율 ────────────────────────────────────────────────────
def test_volume_ratio_double():
    vols = [100] * 20 + [200]  # 평균 100, 오늘 200
    assert compute_volume_ratio(vols, 20) == 2.0


def test_volume_ratio_short_data():
    assert compute_volume_ratio([100] * 10, 20) is None


def test_volume_ratio_zero_avg():
    assert compute_volume_ratio([0] * 20 + [100], 20) is None


# ── 통합 ───────────────────────────────────────────────────────────
def test_compute_indicators_full():
    prices = [{"close": float(i), "volume": 1000} for i in range(1, 201)]
    prices.append({"close": 201.0, "volume": 5000})
    out = compute_indicators(prices)
    assert out["ma20"] is not None
    assert out["ma60"] is not None
    assert out["ma200"] is not None
    assert out["rsi14"] == 100.0
    assert out["pos_52w_pct"] == 100.0
    assert out["volume_ratio_20d"] == 5.0


def test_compute_indicators_handles_missing_fields():
    prices = [{"close": 10.0, "volume": None} for _ in range(30)]
    out = compute_indicators(prices)
    assert out["ma20"] == 10.0
    assert out["volume_ratio_20d"] is None
