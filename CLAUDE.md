# MorningBrief

매일 아침 6시(KST) AI 멀티 에이전트가 미국 빅테크 10종을 분석해 보내는 뉴스레터.

- Spec: `docs/superpowers/specs/2026-04-30-morningbrief-design.md`
- Sample: `docs/superpowers/specs/sample-report.md`

## 모노레포 구조

| Path | Purpose |
|---|---|
| `apps/agent` | Python LangGraph 파이프라인 (수집→분석→발송) |
| `apps/site` | Astro 5 + Vercel adapter v8 프런트/API |
| `scripts/` | `run_today.py`, `backfill.py` 등 일회성 진입점 |
| `supabase/migrations/` | DB 스키마 (`0001_init.sql`) |
| `.github/workflows/` | 데일리 cron |

## apps/agent (Python ≥3.10)

### 구조
- 패키지: `src/morningbrief/{agents,data,llm,pipeline}` + 단일 모듈 `indicators.py`, `utils.py`
- 진입점: `scripts/run_today.py` → `pipeline.orchestrator.run_for_date(today)`
- 주요 deps: `langgraph`, `openai`, `supabase`, `yfinance`, `pandas-market-calendars`, `resend`, `langfuse`
- `pyproject.toml`의 `pythonpath = ["src", "../.."]` — `src/morningbrief`와 루트의 `scripts/`를 동시에 import 경로에 올림

### 일일 파이프라인 (`run_for_date`)
1. **수집**(`pipeline/ingest.py`) — 휴장일이면 skip(NYSE 캘린더). DB 최신일 기준 누락분 yfinance 증분 upsert. 400일치 미달이면 자동 시드. 재무는 7일+ stale일 때만 EDGAR 재조회. 멱등.
2. **로드** — `load_recent_prices(days=365)` + `load_latest_financials(n=4)`
3. **가공**(`indicators.py`) — `compute_indicators(prices)` 결정적 계산: MA20/60/200, RSI14, 52주 위치%, 거래량비(20일). DB 미저장, 메모리 dict로만 LLM에 전달
4. **분석**(LangGraph: `pipeline/graph.py`) — `analyze_universe`(종목별 fundamental+risk LLM, 지표 dict 주입) → `select_top3`(가중합 결정적) → `debate_top3`(bull/bear/supervisor) → `assemble_signals`
5. **렌더 + 저장 + 발송** — Markdown → `reports`/`signals` 테이블 → Resend

### 가격 윈도우
- backfill: 400 캘린더일 (수동 시드용 `scripts/backfill.py`, 보통은 ingest가 자동 처리)
- 일일 로드: 365 캘린더일 (252 거래일 = 52주 지표 커버)

```bash
cd apps/agent
pip install -e ".[dev]"
pytest                    # 테스트 (testpaths=tests)
ruff check .              # 린트 (line-length 100)
ruff format .             # 포맷
```

루트에서 파이프라인 직접 실행:

```bash
PYTHONPATH=apps/agent/src apps/agent/.venv/Scripts/python.exe -m scripts.run_today
```

## apps/site (Astro 5 / Node 22)

- Vercel adapter v8 SSR
- Supabase JS, Resend, marked, Tailwind 3

```bash
cd apps/site
npm install
npm run dev      # 개발 서버
npm run build    # 빌드
npm test         # vitest run
```

> 현재 `package.json`에 별도 lint script 없음 — 필요 시 `astro check` 또는 `tsc --noEmit` 직접 호출.

## 환경변수 / 시크릿

- 루트 `.env`에 보관 — 셸에 `export`하거나 로그에 노출 금지
- `load_dotenv()`가 루트에서 찾도록, 스크립트는 repo 루트에서 실행
- 필수 키: Supabase (URL/SERVICE_ROLE), OpenAI, Resend, Langfuse

## 데이터베이스

- Supabase Postgres
- 마이그레이션은 `supabase/migrations/` 파일명 순서대로 적용
  - 로컬: `supabase db push` (Supabase CLI 연결 필요)
  - 또는 SQL 파일을 Supabase 대시보드 SQL Editor에 붙여넣어 실행

## 운영

- GitHub Actions cron(`.github/workflows/`)이 매일 새벽 파이프라인 실행 → 리포트 생성 → Resend 발송 → Supabase 기록
- 사이트는 Vercel 배포, 아카이브 페이지에서 과거 리포트 조회
