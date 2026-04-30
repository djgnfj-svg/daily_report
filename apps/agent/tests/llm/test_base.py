import json
from unittest.mock import MagicMock

from morningbrief.llm.base import OpenAILLM, MODEL_TIERS


def test_openai_llm_calls_correct_model_for_cheap_tier():
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value.choices[0].message.content = json.dumps({"score": 80})

    llm = OpenAILLM(client=fake_client)
    result = llm.complete_json(system="sys", user="usr", tier="cheap")

    fake_client.chat.completions.create.assert_called_once()
    call = fake_client.chat.completions.create.call_args.kwargs
    assert call["model"] == MODEL_TIERS["cheap"]
    assert call["response_format"] == {"type": "json_object"}
    assert call["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]
    assert result == {"score": 80}


def test_openai_llm_premium_tier_uses_premium_model():
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value.choices[0].message.content = '{"x":1}'
    OpenAILLM(client=fake_client).complete_json(system="s", user="u", tier="premium")
    assert fake_client.chat.completions.create.call_args.kwargs["model"] == MODEL_TIERS["premium"]


def test_model_tiers_has_cheap_and_premium():
    assert MODEL_TIERS == {"cheap": "gpt-4o-mini", "premium": "gpt-4o"}
