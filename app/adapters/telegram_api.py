from __future__ import annotations

from dataclasses import dataclass
import mimetypes
from pathlib import Path
from typing import Protocol

import httpx

TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_SAFE_MESSAGE_LIMIT = 3900


@dataclass(slots=True)
class OutboundMessage:
    chat_id: int
    text: str
    reply_markup: dict | None = None


@dataclass(slots=True)
class OutboundDocument:
    chat_id: int
    file_path: str
    caption: str | None = None


class TelegramGateway(Protocol):
    async def send_text(self, chat_id: int, text: str, reply_markup: dict | None = None) -> None:
        ...

    async def send_document(self, chat_id: int, file_path: str, caption: str | None = None) -> None:
        ...


class NullTelegramGateway:
    def __init__(self) -> None:
        self.messages: list[OutboundMessage] = []
        self.documents: list[OutboundDocument] = []

    async def send_text(self, chat_id: int, text: str, reply_markup: dict | None = None) -> None:
        self.messages.append(OutboundMessage(chat_id=chat_id, text=text, reply_markup=reply_markup))

    async def send_document(self, chat_id: int, file_path: str, caption: str | None = None) -> None:
        self.documents.append(OutboundDocument(chat_id=chat_id, file_path=file_path, caption=caption))


class HttpTelegramGateway:
    def __init__(self, bot_token: str, base_url: str = "https://api.telegram.org") -> None:
        self.bot_token = bot_token
        self.base_url = base_url.rstrip("/")

    async def send_text(self, chat_id: int, text: str, reply_markup: dict | None = None) -> None:
        if not self.bot_token:
            raise ValueError("telegram bot token is required")

        async with httpx.AsyncClient(base_url=self.base_url, timeout=15.0) as client:
            for index, chunk in enumerate(split_telegram_message(text)):
                payload: dict[str, object] = {
                    "chat_id": chat_id,
                    "text": chunk,
                }
                if reply_markup is not None and index == 0:
                    payload["reply_markup"] = reply_markup

                response = await client.post(
                    f"/bot{self.bot_token}/sendMessage",
                    json=payload,
                )
                if response.is_error:
                    raise httpx.HTTPStatusError(
                        f"Telegram sendMessage failed: {response.text}",
                        request=response.request,
                        response=response,
                    )

    async def send_document(self, chat_id: int, file_path: str, caption: str | None = None) -> None:
        if not self.bot_token:
            raise ValueError("telegram bot token is required")

        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"telegram document not found: {file_path}")

        data: dict[str, object] = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption

        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            with path.open("rb") as handle:
                response = await client.post(
                    f"/bot{self.bot_token}/sendDocument",
                    data=data,
                    files={"document": (path.name, handle, self._document_mime_type(path))},
                )
            if response.is_error:
                raise httpx.HTTPStatusError(
                    f"Telegram sendDocument failed: {response.text}",
                    request=response.request,
                    response=response,
                )

    def _document_mime_type(self, path: Path) -> str:
        if path.suffix.lower() == ".apkg":
            return "application/vnd.anki"
        return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def split_telegram_message(text: str, limit: int = TELEGRAM_SAFE_MESSAGE_LIMIT) -> list[str]:
    if limit <= 0 or limit > TELEGRAM_MESSAGE_LIMIT:
        raise ValueError("limit must be between 1 and Telegram's message limit")
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        split_at = _find_split_point(remaining, limit)
        chunk = remaining[:split_at].rstrip()
        if not chunk:
            chunk = remaining[:limit]
            split_at = limit
        chunks.append(chunk)
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


def _find_split_point(text: str, limit: int) -> int:
    min_useful_split = max(1, limit // 2)
    for separator in ("\n\n", "\n", " "):
        split_at = text.rfind(separator, 0, limit + 1)
        if split_at >= min_useful_split:
            return split_at + (len(separator) if separator == "\n\n" else 0)
    return limit
