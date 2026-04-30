import json
import os
from typing import Any, Literal, Protocol

from openai import OpenAI


MODEL_TIERS: dict[str, str] = {
    "cheap": "gpt-4o-mini",
    "premium": "gpt-4o",
}


class LLM(Protocol):
    def complete_json(self, system: str, user: str, tier: Literal["cheap", "premium"]) -> dict[str, Any]: ...


class OpenAILLM:
    def __init__(self, client: OpenAI | None = None) -> None:
        self._client = client or OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def complete_json(self, system: str, user: str, tier: Literal["cheap", "premium"]) -> dict[str, Any]:
        resp = self._client.chat.completions.create(
            model=MODEL_TIERS[tier],
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = resp.choices[0].message.content
        return json.loads(content)
