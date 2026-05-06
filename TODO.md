# TODO

## 법적 컴플라이언스 (한국법 — 정보통신망법 / 개인정보보호법)

론칭 전 필수.

- [ ] **구독 폼 동의 체크박스** (`apps/site/src/components/SubscribeForm.astro`)
  - `[필수] 개인정보 수집·이용 동의` 체크박스
  - `[필수] 이메일 수신 동의` 체크박스 (또는 통합 1개)
  - `/privacy` 링크 노출, 미체크 시 submit 비활성

- [ ] **메일 제목에 `(광고)` 표시** (`apps/agent/src/morningbrief/pipeline/orchestrator.py` L149)
  - 정통망법 제50조 제4항. 정보성으로 분류해도 안전상 권장
  - 변경: `f"MorningBrief — {report_date}"` → `f"(광고) MorningBrief — {report_date}"`

- [ ] **메일 푸터에 사업자 정보** (`apps/agent/src/morningbrief/pipeline/send.py`)
  - 상호 / 대표 / 사업장 주소 / 연락처 추가
  - unsubscribe 링크와 같은 블록에

- [ ] **처리방침에 국외이전 항목** (`apps/site/src/pages/privacy.astro`)
  - Resend(미국), Supabase(미국) 국외이전 사실 + 항목/시점/방법/보유기간 별도 명시
  - 개인정보보호법 제28조의8

- [ ] **이용약관 페이지 추가** (`apps/site/src/pages/terms.astro`)
  - 서비스 내용 / 면책 / 분쟁 해결

- [ ] **DB에 동의 이력 기록** (선택, 분쟁 대비)
  - `subscribers` 테이블에 `consent_version`, `consent_at` 컬럼 추가
  - 마이그레이션: `supabase/migrations/0003_consent.sql`

## 운영/품질 (우선순위 순)

### 1. Archive 사이트 점검 (지금 바로, ~10분, 검증만)
- [ ] `https://reseeall.com/archive` 와 `/archive/2026-05-01` 정상 렌더링 확인
- [ ] 안 떠 있으면 `cd apps/site && npm run dev`로 로컬 확인
- 왜: 메일은 검증됐지만 Vercel 배포·SSR 동작 미확인

### 2. GitHub Actions workflow dispatch 1회 (~5분, 검증만)
- [ ] GitHub repo → Actions → "Daily Report" → Run workflow 수동 트리거
- [ ] 시크릿 5개 (OPENAI_API_KEY / SUPABASE_URL / SUPABASE_SERVICE_KEY / RESEND_API_KEY / SITE_URL) 등록 확인
- 왜: 첫 cron이 새벽에 터지면 이슈만 남음. 미리 1번 돌려보면 안전
- 리스크: `--all-subscribers` 모드라 confirmed 구독자 전원에게 메일 감

### 3. 컴플라이언스 (외부 공개 직전, ~2-3시간)
- 위 "법적 컴플라이언스" 섹션 6개 항목 일괄 처리

### 4. Langfuse 트레이싱 연동 (LLM 품질 튜닝 시작 시, ~30분)
- [ ] `pyproject.toml`에 의존성 있으나 코드 미연동
- [ ] LangGraph `config={"callbacks": [langfuse_handler]}`로 invoke
- [ ] `reports.trace_url`에 트레이스 URL 저장
- 왜: 메일 결과만 보고 "왜 X가 top3에 안 들어갔지?" 답하기 어려움. 트레이스 있으면 노드별 프롬프트/응답/토큰/지연 시각화
- 비용: Langfuse Cloud 무료 tier (월 50k events 무료)

### 기타
- [ ] **render/send 통합 테스트** — Markdown 회귀, Resend payload 형태 검증

## 알려진 이슈

- ingest 시드 기준이 "데이터 존재 여부"라 일부만 들어있어도 incremental만 돔. 거래일 수 < 200이면 reseed로 강화 검토.
