# MorningBrief 설계서 (Spec)

> 기획문서 v0.4 기반, 브레인스토밍을 통해 빈틈을 채운 최종 설계.
> 2026-04-30 작성. 구현 시작 전 합의 문서.

---

## 0. 개요

| 항목 | 내용 |
|---|---|
| 이름 | MorningBrief |
| 도메인 | `reseeall.com` |
| 한 줄 소개 | 매일 아침 6시(KST), AI 멀티 에이전트가 분석한 미국 빅테크 10종 뉴스레터 |
| 목적 | AI Agent 엔지니어 포트폴리오 |
| 기간 | 2주 (2026-05-04 ~ 2026-05-17) |
| 운영비 | ~$13/월 (도메인 포함) |
| 운영 부담 | 주 ~15분 |

---

## 1. 합의된 결정사항

기획문서 대비 본 설계서에서 확정/변경한 사항:

| 항목 | 결정 |
|---|---|
| 종목 프리셋 | AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, AVGO, ORCL, NFLX (빅테크 10) |
| 이메일 포맷 | **Top Picks형** — 상위 3종 상세 + 나머지 7종 표 요약 |
| Top 3 선정 | **룰 기반 스코어** (Fundamental + Risk-adjusted, 결정론적) |
| 디베이트 범위 | **상위 3종만** Bull-Bear-Supervisor (비용 통제) |
| 발송 cron | `0 21 * * 0-4` → **월~금 06:00 KST** (일요일 cron은 금요일 종가로 주간 시작 브리핑) |
| Outcomes 기준 | **종가 → 종가** (1d / 7d 수익률), SPY 벤치마크 비교 |
| 이메일 인프라 | **Resend (무료 3000통/월) + 자체 구독자 관리** (Buttondown 미사용) |
| LLM | **OpenAI** 우선 (`gpt-4o-mini` 분석, `gpt-4o` 디베이트), 어댑터 추상화로 향후 Claude 전환 가능 |
| 시드 데이터 | 첫 배포 시 `scripts/backfill.py` 1회 실행 (10종 × 90일 가격 + 최근 4분기 재무) |
| 모노레포 | `apps/site` (Astro) + `apps/agent` (Python) |
| 휴장일 | NYSE 캘린더 체크 → 데이터 수집·분석 스킵, Outcomes만 갱신, 짧은 안내 메일 발송 |

---

## 2. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND (Astro hybrid + Vercel)                           │
│  reseeall.com                                               │
│  ├─ /            랜딩 (Hero, 구독 폼, FAQ, 후원, 면책)      │
│  ├─ /about       프로젝트 소개                              │
│  ├─ /privacy     개인정보처리방침                           │
│  ├─ /archive     SSR 리포트 리스트                          │
│  ├─ /archive/[date]  SSR 개별 리포트                        │
│  └─ /api/                                                   │
│     ├─ POST subscribe                                       │
│     ├─ GET  confirm?token=                                  │
│     └─ GET  unsubscribe?token=                              │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼ Supabase JS client
┌─────────────────────────────────────────────────────────────┐
│  Supabase (Postgres 무료 티어)                              │
│  prices · financials · filings · reports · signals ·        │
│  outcomes · subscribers                                     │
└─────────────────────────────────────────────────────────────┘
                          ▲
                          │ Service Role
┌─────────────────────────────────────────────────────────────┐
│  AGENT PIPELINE (Python + LangGraph)                        │
│  GitHub Actions cron `0 21 * * 0-4` (월-금 06:00 KST)       │
│                                                             │
│  [A] Ingest      yfinance / SEC EDGAR → Supabase           │
│  [B] Outcomes    1d/7d 종가 채우기                          │
│  [C] Financials  분기 재무 갱신 (90일 경과 시)              │
│  [D] Analyze     LangGraph 그래프 실행                      │
│  [E] Render      마크다운 + reports/signals insert          │
│  [F] Send        Resend API 배치 발송                       │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
                ┌─────────────────────┐
                │  Resend (발송 엔진)  │
                │  Langfuse Cloud (트레이스) │
                └─────────────────────┘
```

---

## 3. 데이터 모델 (Supabase 스키마)

### 3.1 기존 6개 테이블 (기획문서 그대로)

```sql
CREATE TABLE prices (
  ticker TEXT NOT NULL,
  date DATE NOT NULL,
  open NUMERIC, high NUMERIC, low NUMERIC, close NUMERIC,
  volume BIGINT,
  PRIMARY KEY (ticker, date)
);

CREATE TABLE financials (
  ticker TEXT NOT NULL,
  period TEXT NOT NULL,        -- '2026Q1'
  revenue NUMERIC, net_income NUMERIC,
  eps NUMERIC, fcf NUMERIC,
  total_debt NUMERIC, total_equity NUMERIC,
  source TEXT,                 -- '10-Q' | '10-K'
  filed_at DATE,
  PRIMARY KEY (ticker, period)
);

CREATE TABLE filings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker TEXT NOT NULL,
  form_type TEXT,
  filed_at TIMESTAMPTZ,
  url TEXT,
  summary TEXT
);

CREATE TABLE reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  date DATE NOT NULL UNIQUE,
  body_md TEXT,
  trace_url TEXT,
  cost_usd NUMERIC(10,4),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id UUID REFERENCES reports(id) ON DELETE CASCADE,
  ticker TEXT NOT NULL,
  signal TEXT CHECK(signal IN ('BUY','HOLD','SELL')),
  confidence INT,
  thesis TEXT,
  is_top_pick BOOLEAN DEFAULT FALSE   -- 상위 3종 여부 (디베이트 적용 대상)
);

CREATE TABLE outcomes (
  signal_id UUID PRIMARY KEY REFERENCES signals(id) ON DELETE CASCADE,
  price_at_report NUMERIC,
  price_1d NUMERIC, price_7d NUMERIC,
  return_1d NUMERIC, return_7d NUMERIC
);
```

### 3.2 신규 테이블 — `subscribers`

```sql
CREATE TABLE subscribers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending','confirmed','unsubscribed')),
  confirm_token TEXT UNIQUE,
  unsub_token TEXT UNIQUE NOT NULL,
  confirmed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON subscribers(status);
```

### 3.3 RLS

- `anon` 키: 모든 테이블 읽기/쓰기 차단
- `service_role` 키: 전체 권한 (GitHub Actions 시크릿, Astro API 라우트)
- `/archive` SSR 페이지는 server-side service_role로 reports/signals만 조회

---

## 4. 일일 워크플로우

```
21:00 UTC (06:00 KST, 월-금 트리거)
  │
  ├─ 0. NYSE 휴장일 체크
  │     휴장 → [B] Outcomes만 갱신, 안내 메일 발송, 종료
  │
  ├─ [A] Ingest (5초)
  │   ├─ 10종 어제 시세 fetch → prices upsert
  │   └─ 신규 8-K 공시 → filings insert (LLM 1줄 요약)
  │
  ├─ [B] Outcomes 갱신 (5초)
  │   ├─ 1거래일 전 BUY/SELL → return_1d 채우기
  │   └─ 7거래일 전 BUY/SELL → return_7d 채우기
  │
  ├─ [C] Financials 갱신 (조건부)
  │   └─ 마지막 fetch 90일 경과 종목만 SEC EDGAR 호출
  │
  ├─ [D] Analyze (LangGraph, ~3분)
  │   ├─ Fundamental ×10 (gpt-4o-mini, 병렬)
  │   ├─ Risk ×10 (gpt-4o-mini, 병렬)
  │   ├─ ScoreAndRank → 상위 3 선정
  │   ├─ Bull ×3 + Bear ×3 (gpt-4o, 디베이트 1라운드)
  │   └─ Supervisor (gpt-4o, 최종 종합 + 7종 요약)
  │
  ├─ [E] Render & Save (5초)
  │   ├─ 마크다운 본문 생성
  │   └─ reports + signals(10개) insert
  │
  └─ [F] Send (10초)
      ├─ subscribers WHERE status='confirmed'
      ├─ Resend 배치 (100명/배치, List-Unsubscribe 헤더)
      └─ 본문 하단 unsubscribe 링크 (per-user token)

총 소요 ~5분 / 월 ~110분 (GitHub 무료 한도 5.5%)
```

---

## 5. LangGraph 그래프

### 5.1 노드 구성

```
                  [10종 입력]
                       │
        ┌──────────────┴──────────────┐
        ▼                              ▼
   FundamentalAgent              RiskAgent
   (gpt-4o-mini × 10 병렬)       (gpt-4o-mini × 10 병렬)
        │                              │
        └──────────────┬──────────────┘
                       ▼
              ScoreAndRank (룰 기반)
              상위 3종 → is_top_pick=TRUE
                       │
           ┌───────────┴───────────┐
           ▼                       ▼
      BullAgent ◄── 디베이트 ────► BearAgent
      (gpt-4o × 3)                 (gpt-4o × 3)
           │                       │
           └───────────┬───────────┘
                       ▼
                  Supervisor
                  (gpt-4o, 최종 시그널 + 7종 요약)
                       │
                       ▼
              Markdown Report
```

### 5.2 그래프 상태 (TypedDict)

```python
class State(TypedDict):
    date: str
    tickers: list[str]
    fundamentals: dict[str, FundamentalResult]
    risks: dict[str, RiskResult]
    scores: dict[str, float]
    top3: list[str]
    bull: dict[str, BullCase]   # top3만
    bear: dict[str, BearCase]   # top3만
    signals: list[Signal]       # 10개 (top3는 디베이트 결과 반영, 나머지는 fund+risk만)
    report_md: str
```

### 5.3 체크포인터

LangGraph SQLite checkpointer (`/tmp/checkpoint.db`) — 실패 시 재실행 가능.

### 5.4 Top Picks 스코어링 룰

```python
# scoring/top_picks.py 의사코드
def score(fund: FundamentalResult, risk: RiskResult) -> float:
    # Fundamental: 0~100, 저평가·성장·재무건전성 종합
    # Risk: Sharpe-like (변동성 페널티), 0~100
    return 0.6 * fund.score + 0.4 * risk.score

top3 = sorted(tickers, key=lambda t: score(...), reverse=True)[:3]
```

---

## 6. 이메일 (Top Picks 형식)

### 6.1 본문 구조 (마크다운)

```
# MorningBrief — 2026-05-04 (월)

> 어제 SPY 종가: $XXX (전일 대비 ±X.X%)

## 🎯 오늘의 Top 3

### 1. NVDA — BUY (Confidence 78)
**Bull Case**: ...
**Bear Case**: ...
**Supervisor 결정**: ...
What would change my mind: ...

### 2. ... (동일)
### 3. ... (동일)

## 📊 나머지 7종 요약

| 종목 | 시그널 | 신뢰도 | 한 줄 |
|---|---|---|---|
| AAPL | HOLD | 55 | ... |
| ...

## 📈 어제 시그널 결과 (자동 검증)

| 종목 | 시그널 | 1일 수익률 | vs SPY |
|---|---|---|---|
| ... |

---
[Buy Me a Coffee] · [공개 trace] · [수신거부]
```

### 6.2 발송

- Resend API: `POST /emails`, 배치 100명
- HTML 변환: `marked` (Astro 빌드 시 동일 라이브러리 재사용으로 일관성)
- 헤더: `List-Unsubscribe: <https://reseeall.com/api/unsubscribe?token=...>`, `List-Unsubscribe-Post: List-Unsubscribe=One-Click`

---

## 7. 구독 플로우

```
1. 사용자 / 페이지에서 이메일 입력 → POST /api/subscribe
2. subscribers insert (status='pending', confirm_token, unsub_token)
3. Resend로 confirm 메일 발송 (https://reseeall.com/api/confirm?token=...)
4. 사용자 클릭 → status='confirmed', confirmed_at=NOW()
5. 다음 일일 발송부터 수신
6. 메일 하단 unsubscribe 링크 → status='unsubscribed' (1-click)
```

---

## 8. 디렉토리 구조

```
daily_report/
├── apps/
│   ├── site/                      # Astro 4 + Tailwind
│   │   ├── src/
│   │   │   ├── pages/
│   │   │   │   ├── index.astro
│   │   │   │   ├── about.astro
│   │   │   │   ├── privacy.astro
│   │   │   │   ├── archive/
│   │   │   │   │   ├── index.astro
│   │   │   │   │   └── [date].astro
│   │   │   │   └── api/
│   │   │   │       ├── subscribe.ts
│   │   │   │       ├── confirm.ts
│   │   │   │       └── unsubscribe.ts
│   │   │   └── lib/{supabase,resend}.ts
│   │   └── astro.config.mjs       # output:'hybrid', @astrojs/vercel/serverless
│   │
│   └── agent/                     # Python 3.11 + LangGraph 0.2
│       ├── pyproject.toml
│       ├── main.py
│       ├── pipeline/
│       │   ├── ingest.py
│       │   ├── outcomes.py
│       │   ├── financials.py
│       │   ├── analyze.py
│       │   ├── render.py
│       │   └── send.py
│       ├── agents/
│       │   ├── fundamental.py
│       │   ├── risk.py
│       │   ├── debate.py
│       │   ├── llm.py             # OpenAI 어댑터 (Claude 전환 지점)
│       │   └── prompts/
│       ├── scoring/top_picks.py
│       ├── data/{tickers,yf,edgar,calendar}.py
│       └── tests/
│
├── scripts/
│   ├── backfill.py                # 90일 가격 + 최근 4분기 재무
│   └── backtest.ipynb
│
├── supabase/migrations/0001_init.sql
├── .github/workflows/daily.yml
├── docs/superpowers/specs/
└── README.md
```

---

## 9. LLM 어댑터 (전환 지점)

`apps/agent/agents/llm.py` 는 OpenAI / Claude 전환을 위한 단일 인터페이스.

```python
class LLM(Protocol):
    def complete(self, system: str, user: str, model: str) -> str: ...

# 초기 구현
class OpenAILLM:
    MODELS = {"cheap": "gpt-4o-mini", "premium": "gpt-4o"}
    ...

# 향후 전환 시 1줄 추가
class AnthropicLLM:
    MODELS = {"cheap": "claude-haiku-4-5", "premium": "claude-sonnet-4-6"}
    ...
```

---

## 10. 비용 (월)

| 항목 | 비용 |
|---|---|
| Vercel Hobby | $0 |
| Supabase 무료 | $0 |
| GitHub Actions (~110분/월) | $0 |
| Resend (3,000통/월 무료) | $0 |
| Langfuse Cloud 무료 | $0 |
| OpenAI API | ~$12 |
| 도메인 (`reseeall.com`) | ~$1 |
| **합계** | **~$13/월** |

---

## 11. 평가 프레임워크

### 11.1 백테스트 (`scripts/backtest.ipynb`)
- 30일 룩백, BUY 시그널의 7일 수익률
- vs SPY 벤치마크 (동일 종가→종가 기준)
- Hit Rate, Sharpe, Max Drawdown
- GitHub Public Repo로 공개

### 11.2 LLM-as-Judge
- 별도 Judge 모델 (`gpt-4o`)이 리포트를 5점 척도로 채점
- 평가 축: 근거 구체성 / 일관성 / 환각 없음
- 일일 trace에 점수 기록 → Langfuse 대시보드

---

## 12. 운영 / 장애 / 법적

기획문서 §13, §15, §16 그대로 유지. 추가 사항만:

- **Resend 바운스 모니터링**: 3회 hard bounce → status='unsubscribed' 자동 전환 (v1.1)
- **Vercel API 라우트 rate limit**: `/api/subscribe`에 IP당 분당 5회 제한 (Upstash Redis 무료 티어 또는 단순 Supabase counter)
- **휴장일 메일**: "오늘은 미국장 휴장일입니다. 어제 결과만 업데이트했어요." 짧은 본문

---

## 13. 2주 로드맵

### Week 1 — Foundation (5/4 ~ 5/10)

| 일 | 작업 |
|---|---|
| 5/4 (월) | 모노레포·Astro·Vercel 배포·도메인 연결 |
| 5/5 (화) | Supabase 7 테이블 + RLS, yf/edgar 래퍼 |
| 5/6 (수) | `backfill.py` 작성·실행 (90일 가격 + 최근 4분기 재무) |
| 5/7 (목) | Fundamental + Risk + ScoreAndRank, OpenAI 어댑터, Langfuse |
| 5/8 (금) | Bull / Bear / Supervisor + LangGraph 조립 + 체크포인터 |
| 5/9 (토) | 마크다운 렌더 + 본인 메일로 Resend 1회 수동 발송 |
| 5/10 (일) | 랜딩 + `/api/subscribe`·`/confirm`·`/unsubscribe` + 본인 double opt-in 테스트 |

**마일스톤 1**: `reseeall.com` 라이브, 구독 플로우 동작, 1회 정상 발송.

### Week 2 — Automation + Polish (5/11 ~ 5/17)

| 일 | 작업 |
|---|---|
| 5/11 (월) | GitHub Actions cron, EMERGENCY_PAUSE, 실패 알림 |
| 5/12 (화) | Outcomes 자동 갱신, NYSE 휴장일 처리 (`pandas_market_calendars`) |
| 5/13 (수) | Archive SSR (`/archive`, `/archive/[date]`) |
| 5/14 (목) | 30일 백테스트 노트북, GitHub 공개 |
| 5/15 (금) | LLM-as-Judge, 비용·바운스 모니터링 |
| 5/16 (토) | README, 아키텍처 다이어그램, 3분 데모(Loom), 기술 블로그 |
| 5/17 (일) | 3일 연속 자동 발송 검증 → 공개 런칭, BMC 임베드 |

**마일스톤 2**: 공개 런칭, 자동 운영 검증, 포폴 자료 완비.

---

## 14. 리스크 추가 항목 (Resend 자체 구현분)

| 리스크 | 가능성 | 영향 | 대응 |
|---|---|---|---|
| Resend 무료 한도 초과 (3,000통) | 저 | 중 | 100명 × 22일 = 2,200통, 여유. 초과 시 유료 전환 ($20/월) |
| 자체 unsubscribe 플로우 버그 → 법적 노출 | 중 | 고 | 토큰 기반 1-click + List-Unsubscribe 헤더, 통합 테스트 필수 |
| 가입 폼 스팸·봇 | 중 | 저 | rate limit + 이메일 검증, 필요시 hCaptcha |
| 도메인 발신 신뢰도 | 중 | 중 | Resend SPF/DKIM/DMARC 설정 필수 (DNS Cloudflare) |

---

## 15. 산출물 체크리스트

- [ ] GitHub 모노레포 (public)
- [ ] `reseeall.com` 라이브
- [ ] `/archive` 공개 아카이브
- [ ] Langfuse 공개 trace
- [ ] 본인 메일함 스크린샷
- [ ] 3분 데모 영상
- [ ] 기술 블로그 1편
- [ ] 백테스트 노트북

---

## 16. v2 백로그

- News/Sentiment 에이전트 (Finnhub, Alpha Vantage)
- 추가 프리셋 (반도체, 배당주)
- LLM-as-Judge 결과를 다음날 프롬프트에 self-reflection으로 주입
- 종목 커스텀 (구독 시 선택)
- 리포트 PDF 첨부
- RAG 과거 리포트 자가참조
- Claude / Gemini 어댑터 추가하여 모델 비교
