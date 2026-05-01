from morningbrief.pipeline.state import PipelineState


def _format_top_section(state: PipelineState, ticker: str, idx: int) -> str:
    r = state["risks"][ticker]
    bull = state["bulls"][ticker]
    bear = state["bears"][ticker]
    v = state["verdicts"][ticker]
    last_close = state["universe"][ticker]["prices"][-1]["close"] if state["universe"][ticker]["prices"] else 0.0

    return (
        f"### {idx}. {ticker} — **{v.signal}** (Confidence {v.confidence})\n\n"
        f"> 어제 종가 ${last_close:.2f} · 변동성 {r.metrics.get('volatility_pct', 0):.1f}% · "
        f"MDD {r.metrics.get('max_drawdown_pct', 0):.1f}%\n\n"
        f"**🐂 Bull Researcher**\n> {bull.thesis}\n>\n> {bull.rebuttal}\n\n"
        f"**🐻 Bear Researcher**\n> {bear.thesis}\n>\n> {bear.rebuttal}\n\n"
        f"**🎯 Supervisor 결정 — {v.signal} (Confidence {v.confidence})**\n\n"
        f"{v.thesis}\n\n"
        f"> **What would change my mind**: {v.what_would_change_my_mind}\n\n"
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
    rows = ["| 종목 | 시그널 | 1일 수익률 | vs SPY |", "|---|---|---|---|"]
    for o in outcomes:
        r1 = o.get("return_1d")
        rspy = o.get("spy_return_1d", 0.0)
        if r1 is None:
            continue
        excess = r1 - rspy
        sign = "+" if r1 >= 0 else ""
        rows.append(
            f"| {o['ticker']} | {o['signal']} | **{sign}{r1:.1f}%** | "
            f"{'+' if excess >= 0 else ''}{excess:.1f}%p |"
        )
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
    parts.append("> 본 메일은 정보 제공 목적이며 투자 자문이 아닙니다. 데이터: SEC EDGAR, Yahoo Finance.\n")
    return "\n".join(parts)
