from morningbrief.agents.debate import (
    CriticNote,
    OptimistCase,
    PessimistCase,
    Verdict,
    _coerce_claims,
    critic_note,
    judge,
    optimist_opening,
    optimist_rebuttal,
    pessimist_opening,
    pessimist_rebuttal,
)
from morningbrief.agents.fundamental import FundamentalResult
from morningbrief.agents.risk import RiskResult


class FakeLLM:
    def __init__(self, by_system_substr: dict):
        self.by = by_system_substr
        self.calls: list = []

    def complete_json(self, system, user, tier):
        self.calls.append((system[:30], tier))
        for key, payload in self.by.items():
            if key in system:
                return payload
        raise KeyError(f"no fake matched: {system[:60]!r}")


def _f():
    return FundamentalResult("NVDA", 80, "fund summary", {"pe": 65, "rev_yoy": 22, "FCF": 80})


def _r():
    return RiskResult(
        "NVDA",
        60,
        "risk summary",
        {"volatility_pct": 38.0, "max_drawdown_pct": -12.0, "sharpe_naive": 1.2},
    )


def test_optimist_opening_parses_claims():
    llm = FakeLLM(
        {
            "긍정론자": {
                "thesis": "성장세 강함",
                "confidence": 75,
                "claims": [{"claim": "FCF 강함", "metric": "FCF", "value": 80}],
            }
        }
    )
    o = optimist_opening(llm, "NVDA", _f(), _r())
    assert isinstance(o, OptimistCase)
    assert o.confidence == 75
    assert o.claims[0]["metric"] == "FCF"
    assert llm.calls[0][1] == "premium"


def test_pessimist_opening_parses_claims():
    llm = FakeLLM(
        {
            "비관론자": {
                "thesis": "밸류에이션 부담",
                "confidence": 55,
                "claims": [{"claim": "PE 높음", "metric": "pe", "value": 65}],
            }
        }
    )
    p = pessimist_opening(llm, "NVDA", _f(), _r())
    assert isinstance(p, PessimistCase)
    assert p.confidence == 55
    assert p.claims[0]["metric"] == "pe"


def test_rebuttal_preserves_opening_claims_and_updates_confidence():
    opening_claims = [{"claim": "FCF 강함", "metric": "FCF", "value": 80}]
    opening = OptimistCase("NVDA", "thesis-A", opening_claims, 70)
    opponent = PessimistCase("NVDA", "thesis-B", [], 50)
    llm = FakeLLM(
        {
            "긍정론자": {
                "rebuttal": "r",
                "counter_claims": [{"claim": "y", "metric": "FCF", "value": 50}],
                "updated_confidence": 55,
            }
        }
    )
    out = optimist_rebuttal(llm, "NVDA", _f(), _r(), opening, opponent)
    assert out.confidence == 55
    assert out.claims == opening_claims
    assert out.thesis == "thesis-A"
    assert out.rebuttal == "r"
    assert len(out.counter_claims) == 1
    assert out.counter_claims[0]["metric"] == "FCF"


def test_pessimist_rebuttal_symmetric():
    opening = PessimistCase("NVDA", "p-thesis", [{"claim": "a", "metric": "pe", "value": 65}], 60)
    opponent = OptimistCase("NVDA", "o-thesis", [], 70)
    llm = FakeLLM(
        {
            "비관론자": {
                "rebuttal": "rb",
                "counter_claims": [],
                "updated_confidence": 65,
            }
        }
    )
    out = pessimist_rebuttal(llm, "NVDA", _f(), _r(), opening, opponent)
    assert out.confidence == 65
    assert out.thesis == "p-thesis"
    assert out.rebuttal == "rb"


def test_judge_returns_HOLD_when_confidence_under_60():
    llm = FakeLLM(
        {
            "판정관": {
                "signal": "BUY",
                "confidence": 45,
                "thesis": "...",
                "what_would_change_my_mind": "...",
            }
        }
    )
    optimist = OptimistCase("NVDA", "t", [], 50)
    pessimist = PessimistCase("NVDA", "t", [], 50)
    v = judge(llm, "NVDA", _f(), _r(), optimist, pessimist)
    assert v.signal == "HOLD"
    assert v.confidence == 45


def test_judge_returns_BUY_when_signal_BUY_and_confidence_high():
    llm = FakeLLM(
        {
            "판정관": {
                "signal": "BUY",
                "confidence": 78,
                "thesis": "t",
                "what_would_change_my_mind": "X",
                "winning_claims": [{"claim": "c", "metric": "FCF", "value": 80}],
            }
        }
    )
    optimist = OptimistCase("NVDA", "t", [], 78)
    pessimist = PessimistCase("NVDA", "t", [], 50)
    v = judge(llm, "NVDA", _f(), _r(), optimist, pessimist)
    assert v.signal == "BUY"
    assert v.confidence == 78
    assert v.what_would_change_my_mind == "X"
    assert v.winning_claims[0]["metric"] == "FCF"


def test_critic_note_parses_and_clips():
    long_note = "가" * 500
    llm = FakeLLM(
        {
            "검토관": {
                "note": long_note,
                "missing_factors": ["금리", "환율"],
            }
        }
    )
    optimist = OptimistCase("NVDA", "t", [], 70)
    pessimist = PessimistCase("NVDA", "t", [], 70)
    verdict = Verdict("NVDA", "BUY", 72, "결정", "...")
    c = critic_note(llm, "NVDA", _f(), _r(), optimist, pessimist, verdict)
    assert isinstance(c, CriticNote)
    assert len(c.note) == 240
    assert "금리" in c.missing_factors
    assert "환율" in c.missing_factors


def test_coerce_claims_drops_malformed():
    raw = [
        {"claim": "a", "metric": "b", "value": 1},
        {"claim": "only-claim"},
        "not-a-dict",
        {"metric": "x", "value": 2},
    ]
    out = _coerce_claims(raw)
    assert len(out) == 1
    assert out[0]["claim"] == "a"
    assert out[0]["metric"] == "b"
    assert out[0]["value"] == 1
