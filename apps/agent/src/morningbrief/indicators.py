"""기술적 지표 계산. 결정적 함수만 모아둔다 — LLM 미사용.

모든 입력은 시간 오름차순(과거 → 최신). 데이터 부족 시 None 반환.
"""
from __future__ import annotations


def _sma(values: list[float], window: int) -> float | None:
    if window <= 0 or len(values) < window:
        return None
    return sum(values[-window:]) / window


def compute_ma(closes: list[float]) -> dict[str, float | None]:
    """이동평균 MA20 / MA60 / MA200."""
    return {
        "ma20": _sma(closes, 20),
        "ma60": _sma(closes, 60),
        "ma200": _sma(closes, 200),
    }


def compute_rsi(closes: list[float], period: int = 14) -> float | None:
    """Wilder RSI. closes는 period+1개 이상 필요."""
    if period <= 0 or len(closes) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    for i in range(period + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gain = diff if diff > 0 else 0.0
        loss = -diff if diff < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def compute_52w_position(closes: list[float]) -> float | None:
    """52주(최근 252거래일) 범위에서 현재가 위치 % (0=저점, 100=고점)."""
    if not closes:
        return None
    window = closes[-252:]
    hi = max(window)
    lo = min(window)
    if hi == lo:
        return 50.0
    return round((closes[-1] - lo) / (hi - lo) * 100, 2)


def compute_volume_ratio(volumes: list[int], window: int = 20) -> float | None:
    """오늘 거래량 / 최근 window일 평균 거래량."""
    if len(volumes) < window + 1 or window <= 0:
        return None
    avg = sum(volumes[-(window + 1):-1]) / window  # 오늘 제외한 직전 N일
    if avg == 0:
        return None
    return round(volumes[-1] / avg, 2)


def compute_indicators(prices: list[dict]) -> dict:
    """단일 진입점. prices는 시간 오름차순, 각 행에 close/volume 키 필요."""
    closes = [float(p["close"]) for p in prices if p.get("close") is not None]
    volumes = [int(p["volume"]) for p in prices if p.get("volume") is not None]
    out: dict = {}
    out.update(compute_ma(closes))
    out["rsi14"] = compute_rsi(closes, 14)
    out["pos_52w_pct"] = compute_52w_position(closes)
    out["volume_ratio_20d"] = compute_volume_ratio(volumes, 20)
    return out
