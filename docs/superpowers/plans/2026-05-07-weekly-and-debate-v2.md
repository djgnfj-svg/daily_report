# 주간 전환 + 디베이트 v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** MorningBrief를 일간→주간(월요일 06:00 KST) 발송으로 전환하고, AI 디베이트를 2라운드·근거 구조화·검토관·재토론 트리거가 포함된 v2 구조로 업그레이드한다.

**Architecture:** 발송 cron만 주간으로 변경(데이터 파이프라인은 매일 동작 그대로). LangGraph 디베이트 노드를 (1) 1라운드 → (2) 상대 발언을 본 반박 라운드 → (3) 판정관 → (4) 검토관 + (5) confidence<65이면 1회 재토론. 모든 자연어 출력에 `claims:[{claim,metric,value}]` 구조 강제. 모델은 `gpt-4.1-mini-2025-04-14` / `gpt-4.1-2025-04-14` 스냅샷 핀.

**Tech Stack:** Python 3.11, LangGraph, OpenAI SDK, Supabase Postgres, GitHub Actions cron, pytest, ruff.

**Decisions (브레인스토밍 결과):**
- 발송: 월요일 06:00 KST (`0 21 * * 0`)
- 윈도우: 일봉 365일 그대로
- Top 3 유지
- Outcomes: 7일/30일 (1d/7d 폐기)
- 디베이트: 2라운드 + 근거 구조화(claims[]) + 검토관(메모) + 재토론 트리거(judge confidence < 65, max 1회)
- 모델: 분석 `gpt-4.1-mini-2025-04-14`, 디베이트/검토 `gpt-4.1-2025-04-14`

---

## File Structure

**Modify:**
- `.github/workflows/daily.yml` → cron 주간으로 변경 (이름 그대로 유지하거나 weekly.yml로 rename)
- `apps/agent/src/morningbrief/llm/base.py` — MODEL_TIERS 스냅샷 핀
- `apps/agent/src/morningbrief/llm/prompts.py` — claims[] 구조, 반박 라운드, 검토관 시스템 프롬프트 추가
- `apps/agent/src/morningbrief/agents/debate.py` — dataclass에 claims, 함수 추가(rebuttal_round, critic), 신호 흐름
- `apps/agent/src/morningbrief/pipeline/state.py` — round2/critics 필드 추가
- `apps/agent/src/morningbrief/pipeline/graph.py` — 디베이트 노드 재구성(2라운드 + 검토관 + 재토론 분기)
- `apps/agent/src/morningbrief/pipeline/render.py` — claims, 검토관 노트 렌더
- `apps/agent/src/morningbrief/pipeline/outcomes.py` — 7d/30d
- `apps/agent/tests/agents/test_debate.py` — 신규 케이스 추가
- `apps/agent/tests/pipeline/test_outcomes.py` — 7d/30d 케이스

**Create:**
- `supabase/migrations/0003_outcomes_30d.sql` — `return_30d`, `price_30d` 컬럼 추가
- `apps/agent/tests/agents/test_critic.py` — 검토관 단위 테스트

**No change:** apps/site (about 페이지는 직전 작업에서 이미 갱신), ingest, indicators.

---

## Task 1: Outcomes 테이블에 30d 컬럼 추가 (DB 마이그레이션)

**Files:**
- Create: `supabase/migrations/0003_outcomes_30d.sql`

- [ ] **Step 1: 마이그레이션 SQL 작성**

```sql
-- 0003_outcomes_30d.sql
-- 주간 전환에 따라 1d/7d → 7d/30d 검증으로 변경. 1d/7d는 호환성 위해 nullable 유지.
ALTER TABLE outcomes
  ADD COLUMN IF NOT EXISTS price_30d NUMERIC,
  ADD COLUMN IF NOT EXISTS return_30d NUMERIC,
  ADD COLUMN IF NOT EXISTS spy_return_30d NUMERIC;
```

- [ ] **Step 2: Supabase 대시보드 SQL Editor에 붙여넣어 실행 (또는 `supabase db push`)**

확인: `\d outcomes`에 새 컬럼 3개 존재.

- [ ] **Step 3: 커밋**

```bash
git add supabase/migrations/0003_outcomes_30d.sql
git commit -m "feat(db): add 30d outcome columns for weekly verification"
```

---

## Task 2: GitHub Actions cron 주간 전환

**Files:**
- Modify: `.github/workflows/daily.yml:5-7`

- [ ] **Step 1: cron 변경 + name 갱신**

`.github/workflows/daily.yml`에서:

```yaml
name: Weekly Report

on:
  schedule:
    # 21:00 UTC Sunday = 06:00 KST Monday
    - cron: '0 21 * * 0'
  workflow_dispatch:
```

(파일명은 그대로 `daily.yml`로 두어도 무관 — 운영 부담 최소화. workflow name만 변경)

- [ ] **Step 2: failure 알림 메시지 갱신**

```yaml
title: `Weekly report failed: ${new Date().toISOString().slice(0, 10)}`,
```

- [ ] **Step 3: 커밋**

```bash
git add .github/workflows/daily.yml
git commit -m "chore(ci): switch to weekly cron (Mon 06:00 KST)"
```

---

## Task 3: 모델 스냅샷 핀

**Files:**
- Modify: `apps/agent/src/morningbrief/llm/base.py:8-11`

- [ ] **Step 1: MODEL_TIERS 스냅샷 ID로 변경**

```python
MODEL_TIERS: dict[str, str] = {
    "cheap": "gpt-4.1-mini-2025-04-14",
    "premium": "gpt-4.1-2025-04-14",
}
```

- [ ] **Step 2: 임포트 smoke 확인**

```bash
cd apps/agent && python -c "from morningbrief.llm.base import MODEL_TIERS; print(MODEL_TIERS)"
```

기대: 두 키 모두 `2025-04-14` 접미사로 출력.

- [ ] **Step 3: 커밋**

```bash
git add apps/agent/src/morningbrief/llm/base.py
git commit -m "chore(agent): pin gpt-4.1 snapshots for reproducibility"
```

---

## Task 4: outcomes.py — 7d/30d 검증 로직

**Files:**
- Modify: `apps/agent/src/morningbrief/pipeline/outcomes.py`
- Test: `apps/agent/tests/pipeline/test_outcomes.py` (기존 파일 — 7d/30d 케이스로 갱신)

- [ ] **Step 1: 실패하는 테스트 작성**

`apps/agent/tests/pipeline/test_outcomes.py` 에 추가:

```python
from datetime import date
from morningbrief.pipeline.outcomes import update_outcomes

class _FakeTable:
    def __init__(self, prices):
        self._prices = prices  # {(ticker, date_iso): close}
        self.upserts = []
    def select(self, *_): return self
    def eq(self, k, v):
        self._filter = getattr(self, "_filter", {}); self._filter[k] = v; return self
    def execute(self):
        f = self._filter; key = (f["ticker"], f["date"])
        rows = [{"close": self._prices[key]}] if key in self._prices else []
        self._filter = {}
        class R: data = rows
        return R()
    def upsert(self, payloads):
        self.upserts.extend(payloads); return self


class _FakeClient:
    def __init__(self, prices): self._t = _FakeTable(prices)
    def table(self, _name): return self._t


def test_fills_return_7d_and_30d_when_sessions_passed():
    # 5/1 신호 → 5/12(7세션 후)·6/12(30세션 후) 가격 모두 존재
    prices = {
        ("AAPL", "2026-05-01"): 100.0,
        ("AAPL", "2026-05-12"): 110.0,
        ("AAPL", "2026-06-12"): 130.0,
    }
    client = _FakeClient(prices)
    update_outcomes(
        client,
        signals_with_dates=[("sig-1", "AAPL", date(2026, 5, 1))],
        today=date(2026, 6, 13),
    )
    upserts = client._t.upserts
    assert len(upserts) == 1
    row = upserts[0]
    assert row["return_7d"] == 10.0
    assert row["return_30d"] == 30.0
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

```bash
cd apps/agent && pytest tests/pipeline/test_outcomes.py -v
```

기대: `return_30d` 키 없음으로 KeyError/Assertion 실패.

- [ ] **Step 3: outcomes.py 구현 변경**

`apps/agent/src/morningbrief/pipeline/outcomes.py` 의 `update_outcomes`:

```python
def update_outcomes(
    client,
    signals_with_dates: list[tuple[str, str, date]],
    today: date,
) -> int:
    """For each signal, fill price_7d/return_7d (7 sessions) and price_30d/return_30d (30 sessions)."""
    payloads = []
    for signal_id, ticker, signal_date in signals_with_dates:
        p0 = _load_close(client, ticker, signal_date)
        if p0 is None:
            continue
        row: dict = {"signal_id": signal_id, "price_at_report": p0}

        d7 = signal_date
        for _ in range(7):
            d7 = _step_to_next_session(d7)
        if d7 < today:
            p7 = _load_close(client, ticker, d7)
            if p7 is not None:
                row["price_7d"] = p7
                row["return_7d"] = round((p7 / p0 - 1.0) * 100.0, 4)

        d30 = signal_date
        for _ in range(30):
            d30 = _step_to_next_session(d30)
        if d30 < today:
            p30 = _load_close(client, ticker, d30)
            if p30 is not None:
                row["price_30d"] = p30
                row["return_30d"] = round((p30 / p0 - 1.0) * 100.0, 4)

        if "return_7d" in row or "return_30d" in row:
            payloads.append(row)

    if payloads:
        client.table("outcomes").upsert(payloads).execute()
    return len(payloads)
```

- [ ] **Step 4: 호출부 점검 — 1d 참조 제거**

```bash
cd apps/agent && grep -rn "return_1d\|price_1d\|spy_return_1d" src/ tests/
```

발견되는 모든 참조를 `return_7d` / `return_30d`로 교체하거나 제거. `pipeline/render.py:_format_outcomes`도 30d 컬럼으로 변경:

`pipeline/render.py`:
```python
def _format_outcomes(outcomes: list[dict]) -> str:
    rows = ["| 종목 | 시그널 | 7일 수익률 | 30일 수익률 | vs SPY (30d) |", "|---|---|---|---|---|"]
    for o in outcomes:
        r7 = o.get("return_7d")
        r30 = o.get("return_30d")
        rspy = o.get("spy_return_30d", 0.0)
        if r30 is None and r7 is None:
            continue
        excess = (r30 - rspy) if r30 is not None else None
        def fmt(x): return f"{'+' if x >= 0 else ''}{x:.1f}%" if x is not None else "—"
        excess_s = f"{'+' if (excess or 0) >= 0 else ''}{excess:.1f}%p" if excess is not None else "—"
        rows.append(f"| {o['ticker']} | {o['signal']} | {fmt(r7)} | **{fmt(r30)}** | {excess_s} |")
    return "\n".join(rows)
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
cd apps/agent && pytest tests/pipeline/test_outcomes.py -v
```

기대: PASS.

- [ ] **Step 6: 커밋**

```bash
git add apps/agent/src/morningbrief/pipeline/outcomes.py apps/agent/src/morningbrief/pipeline/render.py apps/agent/tests/pipeline/test_outcomes.py
git commit -m "feat(agent): outcomes 7d/30d for weekly verification"
```

---

## Task 5: 프롬프트 v2 — claims[] 구조 + 반박 라운드 + 검토관

**Files:**
- Modify: `apps/agent/src/morningbrief/llm/prompts.py`

- [ ] **Step 1: 프롬프트 파일 전면 갱신**

`apps/agent/src/morningbrief/llm/prompts.py` 전체 교체:

```python
_KOREAN_RULE = (
    "언어 규칙(반드시 준수): 모든 자연어 문자열 필드는 **한국어로만** 작성합니다. "
    "티커(AAPL 등), 시그널 코드(BUY/HOLD/SELL), 숫자, 표준 영문 약어(EPS, FCF, MA, RSI, MDD, "
    "Sharpe 등)는 그대로 두되, 그 외 영어 문장은 한국어로 번역하세요. "
    "입력이 영어여도 출력 자연어는 한국어입니다."
)

_CLAIMS_RULE = (
    "근거 규칙(반드시 준수): 'claims' 배열의 각 원소는 "
    "{\"claim\": str, \"metric\": str, \"value\": str|number} 형식이며 "
    "metric/value는 입력에 등장한 지표명/수치를 그대로 인용해야 합니다. "
    "입력에 없는 metric은 사용 금지. 인용 가능한 metric이 없으면 claims는 빈 배열."
)


FUNDAMENTAL_SYSTEM = f"""당신은 바이사이드(Buy-side) 주식 펀더멘털 분석가입니다.
주어진 입력: 최근 분기 재무제표, 현재 주가, 사전 계산된 기술적 지표
(MA20/60/200, RSI14, 52주 위치, 20일 거래량비).
strict JSON 출력:
  {{"score": int 0-100, "summary": str (180자 이내), "key_metrics": {{<3-6개 지표명>: number}}}}
점수는 펀더멘털 + 밸류에이션 중심, 기술적 지표는 보조.
100=강력 매수, 0=회피, 50=중립.
입력 숫자만 인용. 새 수치 금지. null은 데이터 부족으로 무시.
{_KOREAN_RULE}
"""

RISK_SYSTEM = f"""당신은 바이사이드(Buy-side) 리스크 분석가입니다.
주어진 입력: 사전 계산된 리스크 지표(변동성, MDD, Sharpe)와 기술적 지표.
strict JSON 출력:
  {{"score": int 0-100, "summary": str (180자 이내), "metrics": {{"volatility_pct": float, "max_drawdown_pct": float, "sharpe_naive": float}}}}
점수가 높을수록 리스크 대비 양호한 프로파일.
입력 숫자만 인용. 새 수치 금지.
{_KOREAN_RULE}
"""

OPTIMIST_OPENING_SYSTEM = f"""당신은 토론에 참여한 '긍정론자(Optimist)'입니다. — 1라운드(개시 발언)
펀더멘털 + 리스크 분석 결과만 보고 가능한 가장 강력한 매수(BUY) 논거를 구성하세요.
strict JSON 출력:
  {{"thesis": str, "claims": [...], "confidence": int 0-100}}
{_CLAIMS_RULE}
{_KOREAN_RULE}
"""

PESSIMIST_OPENING_SYSTEM = f"""당신은 토론에 참여한 '비관론자(Pessimist)'입니다. — 1라운드(개시 발언)
펀더멘털 + 리스크 분석 결과만 보고 가능한 가장 강력한 매도(SELL) 논거를 구성하세요.
strict JSON 출력:
  {{"thesis": str, "claims": [...], "confidence": int 0-100}}
{_CLAIMS_RULE}
{_KOREAN_RULE}
"""

OPTIMIST_REBUTTAL_SYSTEM = f"""당신은 '긍정론자' — 2라운드(반박).
비관론자의 논거를 보고, 가장 약한 주장 1~2개를 골라 입력 수치로 반박하세요.
새 매수 논거를 추가하기보다 상대 약점을 정확히 찌르는 데 집중.
strict JSON 출력:
  {{"rebuttal": str, "counter_claims": [...], "updated_confidence": int 0-100}}
counter_claims는 claims와 동일 형식.
{_CLAIMS_RULE}
{_KOREAN_RULE}
"""

PESSIMIST_REBUTTAL_SYSTEM = f"""당신은 '비관론자' — 2라운드(반박).
긍정론자의 논거를 보고, 가장 약한 주장 1~2개를 골라 입력 수치로 반박하세요.
strict JSON 출력:
  {{"rebuttal": str, "counter_claims": [...], "updated_confidence": int 0-100}}
{_CLAIMS_RULE}
{_KOREAN_RULE}
"""

JUDGE_SYSTEM = f"""당신은 '판정관(Judge)'입니다.
양측의 1라운드 발언과 2라운드 반박을 모두 읽고 BUY/HOLD/SELL을 결정하세요.
규칙:
- 어느 쪽도 confidence가 60 이상에 도달하지 못하면 HOLD.
- 양측이 강하게 충돌하고 당신도 확신이 부족하면 HOLD.
- 'what would change my mind' 항상 명시.
strict JSON 출력:
  {{"signal": "BUY"|"HOLD"|"SELL", "confidence": int 0-100, "thesis": str,
    "what_would_change_my_mind": str, "winning_claims": [...]}}
winning_claims = 결정에 가장 큰 영향을 준 claims (양측 어디서든 인용 가능, claims와 동일 형식).
{_CLAIMS_RULE}
{_KOREAN_RULE}
"""

CRITIC_SYSTEM = f"""당신은 '검토관(Critic)'입니다.
완성된 토론(긍정/비관 1·2라운드 + 판정관 결정)을 객관적으로 검토하고
독자에게 도움이 될 약점·놓친 리스크를 1~2줄로 지적하세요.
규칙:
- 새 매수/매도 권고를 하지 마세요. 분석의 한계만 짚으세요.
- 입력에 등장하지 않은 사실을 만들어내지 마세요.
strict JSON 출력:
  {{"note": str (120자 이내), "missing_factors": [str]}}
{_KOREAN_RULE}
"""
```

- [ ] **Step 2: 임포트 smoke**

```bash
cd apps/agent && python -c "from morningbrief.llm import prompts as p; \
print(all(hasattr(p, n) for n in ['FUNDAMENTAL_SYSTEM','RISK_SYSTEM','OPTIMIST_OPENING_SYSTEM','PESSIMIST_OPENING_SYSTEM','OPTIMIST_REBUTTAL_SYSTEM','PESSIMIST_REBUTTAL_SYSTEM','JUDGE_SYSTEM','CRITIC_SYSTEM']))"
```

기대: `True`.

- [ ] **Step 3: 커밋**

```bash
git add apps/agent/src/morningbrief/llm/prompts.py
git commit -m "feat(agent): debate v2 prompts (claims[], rebuttal round, critic)"
```

---

## Task 6: debate.py — dataclass + 함수 v2

**Files:**
- Modify: `apps/agent/src/morningbrief/agents/debate.py`
- Test: `apps/agent/tests/agents/test_debate.py`

- [ ] **Step 1: 실패하는 테스트 추가**

`apps/agent/tests/agents/test_debate.py`에 추가 (기존 fake LLM 패턴 재사용):

```python
from morningbrief.agents.debate import (
    OptimistCase, PessimistCase, Verdict, CriticNote,
    optimist_opening, pessimist_opening,
    optimist_rebuttal, pessimist_rebuttal,
    judge, critic_note,
)
from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult


class FakeLLM:
    def __init__(self, by_system):
        self.by_system = by_system
    def complete_json(self, system, user, tier):
        for key, payload in self.by_system.items():
            if key in system:
                return payload
        raise KeyError(system[:40])


def _f(): return FundamentalResult(ticker="X", score=72, summary="강함", key_metrics={"FCF": 80})
def _r(): return RiskResult(ticker="X", score=65, summary="안정", metrics={"volatility_pct": 22.0, "max_drawdown_pct": -15.0, "sharpe_naive": 1.1})


def test_optimist_opening_parses_claims():
    llm = FakeLLM({"긍정론자": {
        "thesis": "성장세 강함", "confidence": 75,
        "claims": [{"claim": "FCF 강함", "metric": "FCF", "value": 80}],
    }})
    o = optimist_opening(llm, "X", _f(), _r())
    assert o.confidence == 75
    assert o.claims[0]["metric"] == "FCF"


def test_critic_note_parses():
    llm = FakeLLM({"검토관": {
        "note": "거시 환경 가정이 약함",
        "missing_factors": ["금리", "환율"],
    }})
    c = critic_note(llm, "X", _f(), _r(),
                    optimist=OptimistCase(ticker="X", thesis="t", claims=[], confidence=70, rebuttal="", counter_claims=[]),
                    pessimist=PessimistCase(ticker="X", thesis="t", claims=[], confidence=70, rebuttal="", counter_claims=[]),
                    verdict=Verdict(ticker="X", signal="BUY", confidence=72, thesis="결정", what_would_change_my_mind="...", winning_claims=[]))
    assert c.note.startswith("거시")
    assert "금리" in c.missing_factors
```

- [ ] **Step 2: 실패 확인**

```bash
cd apps/agent && pytest tests/agents/test_debate.py -v
```

기대: ImportError 또는 타입 에러로 실패.

- [ ] **Step 3: debate.py 전면 재작성**

`apps/agent/src/morningbrief/agents/debate.py`:

```python
import json
from dataclasses import dataclass, field
from typing import Literal

from morningbrief.llm.base import LLM
from morningbrief.llm.prompts import (
    OPTIMIST_OPENING_SYSTEM, PESSIMIST_OPENING_SYSTEM,
    OPTIMIST_REBUTTAL_SYSTEM, PESSIMIST_REBUTTAL_SYSTEM,
    JUDGE_SYSTEM, CRITIC_SYSTEM,
)
from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult
from morningbrief.utils import clamp


Signal = Literal["BUY", "HOLD", "SELL"]


@dataclass(frozen=True)
class OptimistCase:
    ticker: str
    thesis: str
    claims: list[dict]
    confidence: int
    rebuttal: str = ""
    counter_claims: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class PessimistCase:
    ticker: str
    thesis: str
    claims: list[dict]
    confidence: int
    rebuttal: str = ""
    counter_claims: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class Verdict:
    ticker: str
    signal: Signal
    confidence: int
    thesis: str
    what_would_change_my_mind: str
    winning_claims: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class CriticNote:
    ticker: str
    note: str
    missing_factors: list[str]


def _user_inputs(ticker: str, f: FundamentalResult, r: RiskResult) -> str:
    return (
        f"Ticker: {ticker}\n"
        f"Fundamental analysis: score={f.score}, summary={f.summary!r}, key_metrics={json.dumps(f.key_metrics)}\n"
        f"Risk analysis: score={r.score}, summary={r.summary!r}, metrics={json.dumps(r.metrics)}\n"
    )


def _coerce_claims(raw) -> list[dict]:
    out = []
    for c in (raw or []):
        if isinstance(c, dict) and "claim" in c and "metric" in c and "value" in c:
            out.append({"claim": str(c["claim"]), "metric": str(c["metric"]), "value": c["value"]})
    return out


def optimist_opening(llm: LLM, ticker: str, f: FundamentalResult, r: RiskResult) -> OptimistCase:
    out = llm.complete_json(system=OPTIMIST_OPENING_SYSTEM, user=_user_inputs(ticker, f, r), tier="premium")
    return OptimistCase(
        ticker=ticker,
        thesis=str(out.get("thesis", "")),
        claims=_coerce_claims(out.get("claims")),
        confidence=clamp(int(out.get("confidence", 50)), 0, 100),
    )


def pessimist_opening(llm: LLM, ticker: str, f: FundamentalResult, r: RiskResult) -> PessimistCase:
    out = llm.complete_json(system=PESSIMIST_OPENING_SYSTEM, user=_user_inputs(ticker, f, r), tier="premium")
    return PessimistCase(
        ticker=ticker,
        thesis=str(out.get("thesis", "")),
        claims=_coerce_claims(out.get("claims")),
        confidence=clamp(int(out.get("confidence", 50)), 0, 100),
    )


def optimist_rebuttal(llm: LLM, ticker: str, f: FundamentalResult, r: RiskResult,
                     opening: OptimistCase, opponent: PessimistCase) -> OptimistCase:
    user = (
        _user_inputs(ticker, f, r)
        + f"\n[자기 1라운드 발언] thesis={opening.thesis!r}, claims={json.dumps(opening.claims, ensure_ascii=False)}\n"
        + f"[비관론자 1라운드 발언] thesis={opponent.thesis!r}, claims={json.dumps(opponent.claims, ensure_ascii=False)}\n"
    )
    out = llm.complete_json(system=OPTIMIST_REBUTTAL_SYSTEM, user=user, tier="premium")
    return OptimistCase(
        ticker=ticker, thesis=opening.thesis, claims=opening.claims,
        confidence=clamp(int(out.get("updated_confidence", opening.confidence)), 0, 100),
        rebuttal=str(out.get("rebuttal", "")),
        counter_claims=_coerce_claims(out.get("counter_claims")),
    )


def pessimist_rebuttal(llm: LLM, ticker: str, f: FundamentalResult, r: RiskResult,
                      opening: PessimistCase, opponent: OptimistCase) -> PessimistCase:
    user = (
        _user_inputs(ticker, f, r)
        + f"\n[자기 1라운드 발언] thesis={opening.thesis!r}, claims={json.dumps(opening.claims, ensure_ascii=False)}\n"
        + f"[긍정론자 1라운드 발언] thesis={opponent.thesis!r}, claims={json.dumps(opponent.claims, ensure_ascii=False)}\n"
    )
    out = llm.complete_json(system=PESSIMIST_REBUTTAL_SYSTEM, user=user, tier="premium")
    return PessimistCase(
        ticker=ticker, thesis=opening.thesis, claims=opening.claims,
        confidence=clamp(int(out.get("updated_confidence", opening.confidence)), 0, 100),
        rebuttal=str(out.get("rebuttal", "")),
        counter_claims=_coerce_claims(out.get("counter_claims")),
    )


def judge(llm: LLM, ticker: str, f: FundamentalResult, r: RiskResult,
          optimist: OptimistCase, pessimist: PessimistCase) -> Verdict:
    user = (
        _user_inputs(ticker, f, r)
        + f"\n[긍정론자 1라운드] {optimist.thesis!r} claims={json.dumps(optimist.claims, ensure_ascii=False)}\n"
        + f"[긍정론자 2라운드 반박] {optimist.rebuttal!r} counter={json.dumps(optimist.counter_claims, ensure_ascii=False)}\n"
        + f"[비관론자 1라운드] {pessimist.thesis!r} claims={json.dumps(pessimist.claims, ensure_ascii=False)}\n"
        + f"[비관론자 2라운드 반박] {pessimist.rebuttal!r} counter={json.dumps(pessimist.counter_claims, ensure_ascii=False)}\n"
        + f"final confidences: optimist={optimist.confidence}, pessimist={pessimist.confidence}\n"
    )
    out = llm.complete_json(system=JUDGE_SYSTEM, user=user, tier="premium")
    raw_signal = str(out.get("signal", "HOLD")).upper()
    if raw_signal not in ("BUY", "HOLD", "SELL"):
        raw_signal = "HOLD"
    confidence = clamp(int(out.get("confidence", 50)), 0, 100)
    final_signal: Signal = "HOLD" if confidence < 60 else raw_signal  # type: ignore[assignment]
    return Verdict(
        ticker=ticker, signal=final_signal, confidence=confidence,
        thesis=str(out.get("thesis", "")),
        what_would_change_my_mind=str(out.get("what_would_change_my_mind", "")),
        winning_claims=_coerce_claims(out.get("winning_claims")),
    )


def critic_note(llm: LLM, ticker: str, f: FundamentalResult, r: RiskResult,
                optimist: OptimistCase, pessimist: PessimistCase, verdict: Verdict) -> CriticNote:
    user = (
        _user_inputs(ticker, f, r)
        + f"\n[긍정 thesis] {optimist.thesis!r}\n[긍정 rebuttal] {optimist.rebuttal!r}\n"
        + f"[비관 thesis] {pessimist.thesis!r}\n[비관 rebuttal] {pessimist.rebuttal!r}\n"
        + f"[판정관] {verdict.signal} conf={verdict.confidence} thesis={verdict.thesis!r}\n"
    )
    out = llm.complete_json(system=CRITIC_SYSTEM, user=user, tier="premium")
    return CriticNote(
        ticker=ticker,
        note=str(out.get("note", ""))[:240],
        missing_factors=[str(x) for x in (out.get("missing_factors") or [])],
    )
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd apps/agent && pytest tests/agents/test_debate.py -v
```

기대: 신규 케이스 PASS, 기존 케이스도 PASS (기존 케이스가 옛 함수명을 참조하면 함께 갱신 — `optimist_case` → `optimist_opening`).

- [ ] **Step 5: 커밋**

```bash
git add apps/agent/src/morningbrief/agents/debate.py apps/agent/tests/agents/test_debate.py
git commit -m "feat(agent): debate v2 dataclasses (claims, rebuttal, critic)"
```

---

## Task 7: state.py + graph.py — 2라운드 + 검토관 + 재토론 트리거

**Files:**
- Modify: `apps/agent/src/morningbrief/pipeline/state.py`
- Modify: `apps/agent/src/morningbrief/pipeline/graph.py`

- [ ] **Step 1: state.py에 critics 필드 추가**

```python
from datetime import date
from typing import TypedDict

from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult
from morningbrief.agents.debate import OptimistCase, PessimistCase, Verdict, CriticNote


class TickerInputs(TypedDict):
    financials: list[dict]
    prices: list[dict]


class PipelineState(TypedDict, total=False):
    report_date: date
    universe: dict[str, TickerInputs]
    indicators: dict[str, dict]
    fundamentals: dict[str, FundamentalResult]
    risks: dict[str, RiskResult]
    top3: list[str]
    optimists: dict[str, OptimistCase]
    pessimists: dict[str, PessimistCase]
    verdicts: dict[str, Verdict]
    critics: dict[str, CriticNote]
    retried_tickers: list[str]
    signals: list[dict]
```

- [ ] **Step 2: graph.py 디베이트 노드 재구성**

`apps/agent/src/morningbrief/pipeline/graph.py`의 `_node_debate_top3` 교체 + 검토관 노드 추가:

```python
from morningbrief.agents.debate import (
    optimist_opening, pessimist_opening,
    optimist_rebuttal, pessimist_rebuttal,
    judge, critic_note,
)


_RETRY_THRESHOLD = 65


def _run_full_debate(llm, ticker, f, r):
    o1 = optimist_opening(llm, ticker, f, r)
    p1 = pessimist_opening(llm, ticker, f, r)
    o2 = optimist_rebuttal(llm, ticker, f, r, o1, p1)
    p2 = pessimist_rebuttal(llm, ticker, f, r, p1, o1)
    v = judge(llm, ticker, f, r, o2, p2)
    return o2, p2, v


def _node_debate_top3(state, llm):
    optimists, pessimists, verdicts, critics, retried = {}, {}, {}, {}, []
    for ticker in state["top3"]:
        f = state["fundamentals"][ticker]
        r = state["risks"][ticker]
        o, p, v = _run_full_debate(llm, ticker, f, r)
        if v.confidence < _RETRY_THRESHOLD:
            # 재토론 1회
            o, p, v = _run_full_debate(llm, ticker, f, r)
            retried.append(ticker)
        c = critic_note(llm, ticker, f, r, o, p, v)
        optimists[ticker] = o
        pessimists[ticker] = p
        verdicts[ticker] = v
        critics[ticker] = c
    return {
        "optimists": optimists, "pessimists": pessimists,
        "verdicts": verdicts, "critics": critics,
        "retried_tickers": retried,
    }
```

(기존 build_graph는 노드 이름을 그대로 사용하므로 추가 변경 불필요. critics는 같은 노드에서 함께 채워짐.)

- [ ] **Step 3: smoke import**

```bash
cd apps/agent && python -c "from morningbrief.pipeline.graph import build_graph; from morningbrief.pipeline.state import PipelineState; print('OK')"
```

기대: `OK`.

- [ ] **Step 4: 커밋**

```bash
git add apps/agent/src/morningbrief/pipeline/state.py apps/agent/src/morningbrief/pipeline/graph.py
git commit -m "feat(agent): wire 2-round debate, critic, retry trigger (conf<65)"
```

---

## Task 8: render.py — claims + 검토관 노트 표시

**Files:**
- Modify: `apps/agent/src/morningbrief/pipeline/render.py`

- [ ] **Step 1: `_format_top_section` 갱신**

```python
def _format_claims(claims: list[dict]) -> str:
    if not claims:
        return ""
    lines = []
    for c in claims[:4]:
        lines.append(f"  - {c['claim']} ({c['metric']}: {c['value']})")
    return "\n".join(lines)


def _format_top_section(state, ticker, idx):
    r = state["risks"][ticker]
    optimist = state["optimists"][ticker]
    pessimist = state["pessimists"][ticker]
    v = state["verdicts"][ticker]
    critic = state.get("critics", {}).get(ticker)
    last_close = state["universe"][ticker]["prices"][-1]["close"] if state["universe"][ticker]["prices"] else 0.0

    parts = [
        f"### {idx}. {ticker} — **{v.signal}** (Confidence {v.confidence})\n",
        f"> 어제 종가 ${last_close:.2f} · 변동성 {r.metrics.get('volatility_pct', 0):.1f}% · "
        f"MDD {r.metrics.get('max_drawdown_pct', 0):.1f}%\n",
        f"**🟢 긍정론자** (conf {optimist.confidence})\n> {optimist.thesis}\n",
        _format_claims(optimist.claims),
        f"\n> 반박: {optimist.rebuttal}" if optimist.rebuttal else "",
        f"\n\n**🔴 비관론자** (conf {pessimist.confidence})\n> {pessimist.thesis}\n",
        _format_claims(pessimist.claims),
        f"\n> 반박: {pessimist.rebuttal}" if pessimist.rebuttal else "",
        f"\n\n**🎯 판정관 — {v.signal} (Confidence {v.confidence})**\n\n{v.thesis}\n",
        f"\n> **결과를 뒤집을 조건**: {v.what_would_change_my_mind}\n",
    ]
    if critic and critic.note:
        parts.append(f"\n**🔍 검토관 노트**: {critic.note}\n")
    parts.append("\n---\n")
    return "".join(parts)
```

- [ ] **Step 2: 재토론 표시(선택, 투명성)**

`render_report` 본문 끝부분, 면책 직전에:

```python
    retried = state.get("retried_tickers") or []
    if retried:
        parts.append(f"> ℹ️ 재토론 적용 종목 (판정관 confidence < 65): {', '.join(retried)}\n")
```

- [ ] **Step 3: smoke**

```bash
cd apps/agent && python -c "from morningbrief.pipeline.render import render_report; print('OK')"
```

기대: `OK`.

- [ ] **Step 4: 커밋**

```bash
git add apps/agent/src/morningbrief/pipeline/render.py
git commit -m "feat(agent): render claims, critic note, retry transparency"
```

---

## Task 9: 통합 smoke + 린트 + 전체 테스트

- [ ] **Step 1: ruff 통과**

```bash
cd apps/agent && ruff check . && ruff format --check .
```

기대: All checks passed.

- [ ] **Step 2: 전체 pytest**

```bash
cd apps/agent && pytest -q
```

기대: 전부 PASS.

- [ ] **Step 3: smoke 실행 (LLM 호출 — `.env`의 OPENAI_API_KEY 필요)**

```bash
PYTHONPATH=apps/agent/src apps/agent/.venv/Scripts/python.exe scripts/smoke_e2e.py
```

기대: 종목 1~2개에 대해 1라운드/2라운드/판정/검토 모두 한국어로 출력. claims 배열에 입력 metric만 등장.

- [ ] **Step 4: 커밋 (필요시 fix-up만)**

```bash
git add -A && git commit -m "chore(agent): lint + format pass for debate v2"
```

---

## Task 10: 운영 검증 (수동 1회)

- [ ] **Step 1: workflow_dispatch 수동 트리거**

GitHub Actions UI → Weekly Report → Run workflow.

- [ ] **Step 2: 결과 확인 체크리스트**

- 본인 메일함에 한국어 리포트 도착
- Top 3 각 종목에 🟢 / 🔴 / 🎯 / 🔍 모두 존재
- claims 4줄 이하 표시
- DB `outcomes` 테이블 30d 컬럼 존재 확인 (Supabase 대시보드)
- `retried_tickers`가 비어있지 않으면 메일 하단에 안내 노출

이슈 없으면 다음 일요일 21 UTC 자동 cron 대기.

---

## Self-Review

- [x] **Spec coverage:** 9개 결정사항 모두 태스크에 매핑됨 (cron→T2, 윈도우→변경 없음, Top3→변경 없음, outcomes→T1·T4, 2라운드→T5·T6·T7, claims→T5·T6·T8, 검토관→T5·T6·T7·T8, 재토론→T7, 모델→T3)
- [x] **Placeholder scan:** 코드/명령 모두 구체적. "TBD" 없음
- [x] **Type consistency:** OptimistCase/PessimistCase가 1라운드와 2라운드 후 동일 dataclass 재활용 (rebuttal/counter_claims를 default로 두고 _rebuttal 함수가 채움). CriticNote는 새로 정의. 함수명 `optimist_opening`/`optimist_rebuttal` 일관 유지
