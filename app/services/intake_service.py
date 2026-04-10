from __future__ import annotations

from app.domain.models import Attachment, InboundEvent


class IntakeService:
    def normalize_update(self, payload: dict) -> InboundEvent:
        body = payload if any(key in payload for key in ("message", "callback_query")) else payload.get("body", payload)
        message = body.get("message") or {}
        callback = body.get("callback_query") or {}

        source_message = callback.get("message") or message
        source_user = callback.get("from") or message.get("from") or {}
        chat = source_message.get("chat") or {}

        attachment = self._extract_attachment(message)
        input_mode = self._infer_input_mode(message, callback, attachment)

        return InboundEvent(
            update_id=body.get("update_id") or payload.get("update_id"),
            telegram_id=int(source_user.get("id") or chat.get("id")),
            chat_id=int(chat.get("id") or source_user.get("id")),
            message_id=source_message.get("message_id"),
            input_mode=input_mode,
            text=(message.get("text") or "").strip(),
            caption=(message.get("caption") or "").strip(),
            callback_data=(callback.get("data") or "").strip(),
            attachment=attachment,
            raw_payload=payload,
        )

    def _extract_attachment(self, message: dict) -> Attachment:
        photo = message.get("photo") or []
        if photo:
            largest = photo[-1]
            return Attachment(file_id=largest.get("file_id", ""), mime_type="image/jpeg")

        document = message.get("document") or {}
        if document:
            return Attachment(
                file_id=document.get("file_id", ""),
                mime_type=document.get("mime_type", ""),
                file_name=document.get("file_name", ""),
            )

        voice = message.get("voice") or {}
        if voice:
            return Attachment(file_id=voice.get("file_id", ""), mime_type=voice.get("mime_type", "audio/ogg"))

        video = message.get("video") or {}
        if video:
            return Attachment(file_id=video.get("file_id", ""), mime_type=video.get("mime_type", "video/mp4"))

        return Attachment()

    def _infer_input_mode(self, message: dict, callback: dict, attachment: Attachment) -> str:
        if callback:
            return "callback"
        if message.get("text"):
            return "text"
        if attachment.file_id and attachment.mime_type.startswith("image/"):
            return "image"
        if attachment.file_id and attachment.mime_type.startswith("audio/"):
            return "audio"
        if attachment.file_id and attachment.mime_type.startswith("video/"):
            return "video"
        if attachment.file_id:
            return "document"
        return "unknown"

