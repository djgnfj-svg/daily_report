# MorningBrief

매일 아침 6시(KST) AI 멀티 에이전트가 미국 빅테크 10종을 분석해 보내는 뉴스레터.

- Spec: `docs/superpowers/specs/2026-04-30-morningbrief-design.md`
- Sample: `docs/superpowers/specs/sample-report.md`

## 모노레포 구조

| Path | Purpose |
|---|---|
| `apps/agent` | Python LangGraph 파이프라인 (수집→분석→발송) |
| `apps/site` | Astro 5 + Vercel adapter v8 프런트/API |
| `scripts/` | `run_today.py`, `backfill.py` 등 일회성 스크립트 |
| `supabase/migrations/` | DB 스키마 (`0001_init.sql`) |
| `.github/workflows/` | 데일리 cron |

## apps/agent (Python ≥3.10)

- 패키지: `src/morningbrief/{agents,data,llm,pipeline}`
- 주요 deps: `langgraph`, `openai`, `supabase`, `yfinance`, `pandas-market-calendars`, `resend`, `langfuse`
- 테스트: `pytest` (`testpaths=tests`, `pythonpath=["src","../.."]`)
- 린트: `ruff` (line-length 100)
- 실행: `python scripts/run_today.py`

```bash
cd apps/agent
pip install -e ".[dev]"
pytest
```

## apps/site (Astro 5 / Node 22)

- Vercel adapter v8 SSR
- Supabase JS, Resend, marked, Tailwind 3
- 테스트: `vitest`

```bash
cd apps/site
npm install
npm run dev      # 개발
npm run build    # 빌드
npm test         # vitest
```

## 환경변수 / 시크릿

- `.env`에 보관 — 셸에 export하거나 로그에 노출하지 말 것
- `load_dotenv`가 찾을 수 있도록 위치 조정 (루트 `.env` 권장)
- Supabase, OpenAI, Resend, Langfuse 키 필요

## 데이터베이스

- Supabase Postgres
- 마이그레이션: `supabase/migrations/*.sql` 순서대로 적용

## 운영

- GitHub Actions cron이 매일 새벽 파이프라인 실행 → 리포트 생성 → Resend 발송 → Supabase 기록
- 사이트는 Vercel 배포, 아카이브 페이지에서 과거 리포트 조회

## 개발 메모

- 현재 main이 origin/main보다 1커밋 앞서있음 (push 필요 시 확인)
- `.gitignore`, `apps/site/package-lock.json` 변경분 커밋 보류 중
- Python pyproject `pythonpath`에 `../..`이 들어있어 루트 모듈 import 가능
