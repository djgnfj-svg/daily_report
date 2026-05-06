from morningbrief.pipeline.state import PipelineState


def _format_claims(claims: list[dict]) -> str:
    if not claims:
        return ""
    lines = []
    for c in claims[:4]:
        lines.append(f"  - {c.get('claim', '')} ({c.get('metric', '')}: {c.get('value', '')})")
    return "\n".join(lines)


def _format_top_section(state: PipelineState, ticker: str, idx: int) -> str:
    r = state["risks"][ticker]
    optimist = state["optimists"][ticker]
    pessimist = state["pessimists"][ticker]
    v = state["verdicts"][ticker]
    last_close = (
        state["universe"][ticker]["prices"][-1]["close"]
        if state["universe"][ticker]["prices"]
        else 0.0
    )

    opt_claims = _format_claims(optimist.claims)
    pes_claims = _format_claims(pessimist.claims)

    opt_block = f"**🟢 긍정론자 (conf {optimist.confidence})**\n> {optimist.thesis}\n"
    if opt_claims:
        opt_block += opt_claims + "\n"
    if optimist.rebuttal:
        opt_block += f"\n> 반박: {optimist.rebuttal}\n"

    pes_block = f"**🔴 비관론자 (conf {pessimist.confidence})**\n> {pessimist.thesis}\n"
    if pes_claims:
        pes_block += pes_claims + "\n"
    if pessimist.rebuttal:
        pes_block += f"\n> 반박: {pessimist.rebuttal}\n"

    judge_block = (
        f"**🎯 판정관 결정 — {v.signal} (Confidence {v.confidence})**\n\n"
        f"{v.thesis}\n\n"
        f"> **결과를 뒤집을 조건**: {v.what_would_change_my_mind}\n"
    )

    return (
        f"### {idx}. {ticker} — **{v.signal}** (Confidence {v.confidence})\n\n"
        f"> 어제 종가 ${last_close:.2f} · 변동성 {r.metrics.get('volatility_pct', 0):.1f}% · "
        f"MDD {r.metrics.get('max_drawdown_pct', 0):.1f}%\n\n"
        f"{opt_block}\n"
        f"{pes_block}\n"
        f"{judge_block}\n"
        f"---\n"
    )


def _format_remaining_table(state: PipelineState) -> str:
    rows = ["| 종목 | 시그널 | 신뢰도 | 한 줄 |", "|---|---|---|---|"]
    for s in state["signals"]:
        if s["is_top_pick"]:
            continue
        thesis = s["thesis"][:60].replace("|", " ")
        rows.append(f"| {s['ticker']} | {s['signal']} | {s['confidence']} | {thesis} |")
    return "\n".join(rows)


def _format_outcomes(outcomes: list[dict]) -> str:
    rows = [
        "| 종목 | 시그널 | 7일 수익률 | 30일 수익률 | vs SPY (30d) |",
        "|---|---|---|---|---|",
    ]

    def _fmt(x: float | None) -> str:
        if x is None:
            return "—"
        return f"{'+' if x >= 0 else ''}{x:.1f}%"

    for o in outcomes:
        r7 = o.get("return_7d")
        r30 = o.get("return_30d")
        if r7 is None and r30 is None:
            continue
        rspy = o.get("spy_return_30d")
        if r30 is not None and rspy is not None:
            excess = r30 - rspy
            excess_s = f"{'+' if excess >= 0 else ''}{excess:.1f}%p"
        else:
            excess_s = "—"
        r30_cell = f"**{_fmt(r30)}**" if r30 is not None else "—"
        rows.append(f"| {o['ticker']} | {o['signal']} | {_fmt(r7)} | {r30_cell} | {excess_s} |")
    return "\n".join(rows)


def render_report(state: PipelineState, prior_outcomes: list[dict]) -> str:
    parts: list[str] = []
    d = state["report_date"]
    parts.append(f"# 📈 MorningBrief — {d.isoformat()}\n")
    parts.append("## 🎯 오늘의 Top 3\n")
    for i, t in enumerate(state["top3"], start=1):
        parts.append(_format_top_section(state, t, i))
    parts.append("## 📊 나머지 7종 요약\n")
    parts.append(_format_remaining_table(state))
    parts.append("\n")
    if prior_outcomes:
        parts.append("## 📈 어제 시그널 결과\n")
        parts.append(_format_outcomes(prior_outcomes))
        parts.append("\n")
    parts.append("---\n")
    retried = state.get("retried_tickers") or []
    if retried:
        parts.append(f"> ℹ️ 재토론 적용 종목 (판정관 confidence < 65): {', '.join(retried)}\n")
    parts.append(
        "> 본 메일은 정보 제공 목적이며 투자 자문이 아닙니다. 데이터: SEC EDGAR, Yahoo Finance.\n"
    )
    return "\n".join(parts)
