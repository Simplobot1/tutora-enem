from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LLMClient:
    api_key: str = ""
    model: str = "claude-sonnet-4-6"

    async def complete_json(self, prompt: str) -> dict:
        raise NotImplementedError("LLM integration will be implemented in a later story.")

