# MorningBrief

매일 아침 6시(KST), AI 멀티 에이전트가 분석한 미국 빅테크 10종 뉴스레터.

- Spec: [docs/superpowers/specs/2026-04-30-morningbrief-design.md](docs/superpowers/specs/2026-04-30-morningbrief-design.md)
- Sample report: [docs/superpowers/specs/sample-report.md](docs/superpowers/specs/sample-report.md)

## Monorepo

| Path | Purpose |
|---|---|
| `apps/agent` | Python LangGraph pipeline (Plan 2) |
| `apps/site` | Astro frontend + API routes (Plan 3) |
| `scripts/` | One-off scripts (backfill, backtest) |
| `supabase/migrations/` | DB schema |

Status: **Plan 1 in progress** (Foundation).
