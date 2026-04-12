from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from app.clients.llm import LLMClient
from app.domain.models import QuestionAlternative

logger = logging.getLogger(__name__)


@dataclass
class OcrResult:
    content: str
    alternatives: list[QuestionAlternative]
    ocr_raw_text: str
    ocr_confidence: float


class OcrService:
    def __init__(self, llm_client: LLMClient, telegram_bot_token: str) -> None:
        self.llm_client = llm_client
        self.telegram_bot_token = telegram_bot_token

    async def extract_question_as_text(self, file_id: str) -> str | None:
        """
        Extract question text from image using Claude Vision API.

        Args:
            file_id: Telegram file_id for the image

        Returns:
            Question text string (enunciado + alternativas formatted as "A) ...", "B) ...", etc.)
            None if extraction fails
        """
        result = await self.extract_question(file_id)
        if result is None:
            return None

        # Format as text: enunciado + alternatives
        alternatives_text = "\n".join(f"{alt.label}) {alt.text}" for alt in result.alternatives)
        return f"{result.content}\n{alternatives_text}"

    async def extract_question(self, file_id: str) -> OcrResult | None:
        """
        Extract question from image using Claude Vision API.

        Args:
            file_id: Telegram file_id for the image

        Returns:
            OcrResult with extracted question, alternatives, raw text, and confidence
            None if extraction fails (invalid image, API error, malformed JSON)
        """
        # Step 1: Download image from Telegram
        image_data = await self._download_telegram_image(file_id)
        if image_data is None:
            logger.warning("Failed to download image for file_id: %s", file_id)
            return None

        # Step 2: Call Claude Vision with image
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        raw_response = await self._call_claude_vision(image_base64)
        if raw_response is None:
            logger.warning("Claude Vision API call failed for file_id: %s", file_id)
            return None

        # Step 3: Parse JSON response
        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse Claude Vision response as JSON for file_id %s: %s", file_id, str(e))
            return None

        # Step 4: Validate and construct OcrResult
        try:
            content = parsed.get("enunciado", "").strip()
            alternatives_dict = parsed.get("alternativas", {})
            confidence = float(parsed.get("confianca", 0.5))

            if not content or not alternatives_dict:
                logger.warning("Incomplete OCR result: missing content or alternatives for file_id %s", file_id)
                return None

            # Build QuestionAlternative objects for A-E
            alternatives: list[QuestionAlternative] = []
            for label in ["A", "B", "C", "D", "E"]:
                alt_text = alternatives_dict.get(label, "").strip()
                if alt_text:
                    alternatives.append(QuestionAlternative(label=label, text=alt_text))

            if len(alternatives) < 5:
                logger.warning(
                    "Incomplete alternatives: got %d/5 for file_id %s",
                    len(alternatives),
                    file_id,
                )
                # Still acceptable if we have at least 4 alternatives
                if len(alternatives) < 4:
                    return None

            return OcrResult(
                content=content,
                alternatives=alternatives,
                ocr_raw_text=raw_response,
                ocr_confidence=confidence,
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("Error constructing OcrResult for file_id %s: %s", file_id, str(e))
            return None

    async def _download_telegram_image(self, file_id: str) -> bytes | None:
        """
        Download image bytes from Telegram Bot API.

        Args:
            file_id: Telegram file_id

        Returns:
            Image bytes, or None if download fails
        """
        try:
            # Get file path
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/getFile"
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params={"file_id": file_id})
                response.raise_for_status()
                result = response.json()

            if not result.get("ok"):
                logger.warning("Telegram getFile failed: %s", result.get("description", "unknown error"))
                return None

            file_path = result.get("result", {}).get("file_path")
            if not file_path:
                logger.warning("No file_path in Telegram response for file_id %s", file_id)
                return None

            # Download file
            download_url = f"https://api.telegram.org/file/bot{self.telegram_bot_token}/{file_path}"
            async with httpx.AsyncClient() as client:
                response = await client.get(download_url)
                response.raise_for_status()
                return response.content

        except httpx.HTTPError as e:
            logger.warning("Failed to download image from Telegram: %s", str(e))
            return None
        except Exception as e:
            logger.warning("Unexpected error downloading Telegram image: %s", str(e))
            return None

    async def _call_claude_vision(self, image_base64: str) -> str | None:
        """
        Call Claude Vision API with image.

        Args:
            image_base64: Base64-encoded image data

        Returns:
            JSON string response, or None if API call fails
        """
        prompt = (
            "Você é um parser de questões do ENEM. Extraia da imagem:\n"
            '{"enunciado": "<texto do enunciado>", "alternativas": {"A":"...","B":"...","C":"...","D":"...","E":"..."}, "confianca": 0.0-1.0}\n'
            "Responda APENAS com JSON válido, sem markdown."
        )

        try:
            response = await self.llm_client.create_message(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_base64,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
            )
            # Extract text content from response
            if response.content and len(response.content) > 0:
                return response.content[0].text
            logger.warning("Empty response from Claude Vision API")
            return None
        except Exception as e:
            logger.warning("Claude Vision API call failed: %s", str(e))
            return None
