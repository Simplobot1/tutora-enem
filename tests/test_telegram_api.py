import pytest

from app.adapters import telegram_api
from app.adapters.telegram_api import HttpTelegramGateway, TELEGRAM_MESSAGE_LIMIT, split_telegram_message


def test_split_telegram_message_keeps_chunks_under_telegram_limit() -> None:
    text = "\n\n".join(f"Alternativa {index}: {'explicacao ' * 80}" for index in range(20))

    chunks = split_telegram_message(text, limit=900)

    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 900 for chunk in chunks)
    assert all(len(chunk) <= TELEGRAM_MESSAGE_LIMIT for chunk in chunks)
    assert chunks[0].startswith("Alternativa 0")
    assert chunks[-1].startswith("Alternativa")


@pytest.mark.asyncio
async def test_http_gateway_splits_long_messages_before_sending(monkeypatch) -> None:
    sent_payloads: list[dict[str, object]] = []

    class FakeResponse:
        is_error = False

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, json: dict[str, object]) -> FakeResponse:
            sent_payloads.append(json)
            return FakeResponse()

    monkeypatch.setattr(telegram_api.httpx, "AsyncClient", FakeClient)
    gateway = HttpTelegramGateway(bot_token="token")
    text = "Intro\n\n" + ("comentario longo " * 700)

    await gateway.send_text(123, text, reply_markup={"inline_keyboard": []})

    assert len(sent_payloads) > 1
    assert all(len(str(payload["text"])) <= TELEGRAM_MESSAGE_LIMIT for payload in sent_payloads)
    assert sent_payloads[0]["reply_markup"] == {"inline_keyboard": []}
    assert all("reply_markup" not in payload for payload in sent_payloads[1:])
