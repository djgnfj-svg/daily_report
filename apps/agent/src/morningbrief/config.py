"""파이프라인 튜닝 파라미터. 시크릿이 아닌, 운영 중 손볼 만한 숫자들."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # ingest
    price_backfill_days: int = 400        # 자동 시드 윈도우 (252 거래일+버퍼)
    financials_stale_days: int = 7        # 재무 갱신 쿨다운

    # load (분석 입력)
    price_load_days: int = 365            # 52주 지표 커버용
    financials_load_n: int = 4            # 최근 N분기

    # outcomes
    outcomes_lookback_days: int = 10


CONFIG = Config()
