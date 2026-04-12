from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import anthropic

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LLMClient:
    api_key: str = ""
    model: str = "claude-sonnet-4-6"

    async def complete_json(self, prompt: str) -> dict:
        raise NotImplementedError("LLM integration will be implemented in a later story.")

    async def create_message(self, model: str, max_tokens: int, messages: list[dict[str, Any]]) -> Any:
        """
        Call Claude API with messages (supports vision).

        Args:
            model: Model ID (e.g., "claude-sonnet-4-6")
            max_tokens: Max output tokens
            messages: Message list with role/content

        Returns:
            Anthropic response object with .content[0].text
        """
        try:
            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
            )
            return response
        except anthropic.APIError as e:
            logger.error("Claude API error: %s", str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error calling Claude API: %s", str(e))
            raise

