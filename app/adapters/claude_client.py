from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ClaudeClient:
    api_key: str = ""

    async def complete_json(self, prompt: str) -> dict:
        raise NotImplementedError("Claude integration will be implemented in the next cut.")

