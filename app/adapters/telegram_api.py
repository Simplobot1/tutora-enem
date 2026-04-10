from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class OutboundMessage:
    chat_id: int
    text: str


class TelegramGateway(Protocol):
    async def send_text(self, chat_id: int, text: str) -> None:
        ...


class NullTelegramGateway:
    def __init__(self) -> None:
        self.messages: list[OutboundMessage] = []

    async def send_text(self, chat_id: int, text: str) -> None:
        self.messages.append(OutboundMessage(chat_id=chat_id, text=text))

