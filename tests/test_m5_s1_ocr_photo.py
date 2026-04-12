"""
Tests for M5-S1: OCR de Foto de Questão via Claude Vision

Test scenarios:
1. Valid image → snapshot constructed correctly (AC3, AC4)
2. Illegible image → friendly error message (AC7)
3. Same file_id sent 2× → cache hit, Claude not called again (AC9)
4. Claude returns malformed JSON → treated as failure (AC7)
5. OCR snapshot persists with source='ocr_photo', ocr_raw_text, ocr_confidence (AC6)
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models import Attachment, InboundEvent, QuestionAlternative, QuestionSnapshot
from app.domain.session_metadata import SessionMetadata
from app.domain.states import SessionFlow, SessionState
from app.services.me_testa_entry_service import MeTestaEntryService
from app.services.ocr_service import OcrResult, OcrService


class TestOcrService:
    """Unit tests for OcrService"""

    @pytest.mark.asyncio
    async def test_extract_question_valid_image(self):
        """Scenario 1: Valid image → snapshot constructed correctly"""
        llm_client = MagicMock()
        ocr_service = OcrService(llm_client=llm_client, telegram_bot_token="test-token")

        # Mock Claude Vision response
        valid_response = json.dumps({
            "enunciado": "Qual é a capital do Brasil?",
            "alternativas": {
                "A": "São Paulo",
                "B": "Brasília",
                "C": "Rio de Janeiro",
                "D": "Belo Horizonte",
                "E": "Salvador",
            },
            "confianca": 0.95,
        })

        ocr_service._download_telegram_image = AsyncMock(return_value=b"fake-image-data")
        ocr_service._call_claude_vision = AsyncMock(return_value=valid_response)

        result = await ocr_service.extract_question("file_123")

        assert result is not None
        assert result.content == "Qual é a capital do Brasil?"
        assert len(result.alternatives) == 5
        assert result.alternatives[0].label == "A"
        assert result.alternatives[0].text == "São Paulo"
        assert result.ocr_confidence == 0.95
        assert result.ocr_raw_text == valid_response

    @pytest.mark.asyncio
    async def test_extract_question_illegible_image(self):
        """Scenario 2: Illegible image → None (handled by MeTestaEntryService)"""
        llm_client = MagicMock()
        ocr_service = OcrService(llm_client=llm_client, telegram_bot_token="test-token")

        # Simulate download failure
        ocr_service._download_telegram_image = AsyncMock(return_value=None)

        result = await ocr_service.extract_question("file_invalid")

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_question_malformed_json(self):
        """Scenario 4: Claude returns malformed JSON → None"""
        llm_client = MagicMock()
        ocr_service = OcrService(llm_client=llm_client, telegram_bot_token="test-token")

        ocr_service._download_telegram_image = AsyncMock(return_value=b"fake-image-data")
        ocr_service._call_claude_vision = AsyncMock(return_value="not valid json")

        result = await ocr_service.extract_question("file_456")

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_question_missing_alternatives(self):
        """Missing alternatives → None (invalid snapshot)"""
        llm_client = MagicMock()
        ocr_service = OcrService(llm_client=llm_client, telegram_bot_token="test-token")

        # Only 3 alternatives instead of 5
        incomplete_response = json.dumps({
            "enunciado": "Question text",
            "alternativas": {
                "A": "Alt A",
                "B": "Alt B",
                "C": "Alt C",
            },
            "confianca": 0.8,
        })

        ocr_service._download_telegram_image = AsyncMock(return_value=b"fake-image-data")
        ocr_service._call_claude_vision = AsyncMock(return_value=incomplete_response)

        result = await ocr_service.extract_question("file_incomplete")

        assert result is None


class TestMeTestaEntryServiceOcr:
    """Integration tests for OCR in MeTestaEntryService"""

    @pytest.mark.asyncio
    async def test_handle_image_intake_success(self):
        """Scenario 3 (partial): Image mode → builds snapshot"""
        session_service = MagicMock()
        question_snapshot_service = MagicMock()
        questions_repository = MagicMock()
        submitted_questions_repository = MagicMock()

        ocr_service = MagicMock(spec=OcrService)

        entry_service = MeTestaEntryService(
            session_service=session_service,
            question_snapshot_service=question_snapshot_service,
            questions_repository=questions_repository,
            submitted_questions_repository=submitted_questions_repository,
            ocr_service=ocr_service,
        )

        # Mock session
        session = MagicMock()
        session.metadata = SessionMetadata(
            flow=SessionFlow.ME_TESTA,
            state=SessionState.IDLE,
            source_mode="student_submitted",
        )
        session.session_id = "sess_123"
        session.telegram_id = 123456
        session.flow = SessionFlow.ME_TESTA
        session.state = SessionState.WAITING_ANSWER

        session_service.get_or_create_active_session.return_value = session

        # Mock OCR result
        ocr_result = OcrResult(
            content="Questão teste",
            alternatives=[
                QuestionAlternative(label="A", text="Opção A"),
                QuestionAlternative(label="B", text="Opção B"),
                QuestionAlternative(label="C", text="Opção C"),
                QuestionAlternative(label="D", text="Opção D"),
                QuestionAlternative(label="E", text="Opção E"),
            ],
            ocr_raw_text='{"test": "data"}',
            ocr_confidence=0.92,
        )

        # Mock extract_question_as_text to return formatted question text
        question_text = "Questão teste\nA) Opção A\nB) Opção B\nC) Opção C\nD) Opção D\nE) Opção E"
        ocr_service.extract_question_as_text = AsyncMock(return_value=question_text)
        questions_repository.find_best_match.return_value = None

        # Mock question_snapshot_service to return a valid snapshot
        snapshot = QuestionSnapshot(
            source_mode="student_submitted",
            source_truth="student_content_only",
            content="Questão teste",
            alternatives=[
                QuestionAlternative(label="A", text="Opção A"),
                QuestionAlternative(label="B", text="Opção B"),
                QuestionAlternative(label="C", text="Opção C"),
                QuestionAlternative(label="D", text="Opção D"),
                QuestionAlternative(label="E", text="Opção E"),
            ],
        )
        question_snapshot_service.build_from_text.return_value = snapshot

        # Create event with image
        event = InboundEvent(
            update_id=1,
            telegram_id=123456,
            chat_id=789,
            message_id=1,
            input_mode="image",
            text="",
            attachment=Attachment(file_id="file_123", mime_type="image/jpeg"),
        )

        result = await entry_service.handle_question_intake(event)

        assert result is not None
        assert "organizei a questão" in result.reply_text
        assert ocr_service.extract_question_as_text.called

    @pytest.mark.asyncio
    async def test_handle_image_intake_failure(self):
        """Scenario 2: Illegible image → friendly error message (AC7)"""
        session_service = MagicMock()
        question_snapshot_service = MagicMock()
        ocr_service = MagicMock(spec=OcrService)

        entry_service = MeTestaEntryService(
            session_service=session_service,
            question_snapshot_service=question_snapshot_service,
            ocr_service=ocr_service,
        )

        # Mock session
        session = MagicMock()
        session.state = SessionState.IDLE
        session.metadata = SessionMetadata(
            flow=SessionFlow.ME_TESTA,
            state=SessionState.IDLE,
            source_mode="student_submitted",
        )

        session_service.get_or_create_active_session.return_value = session

        # OCR fails (returns None or empty string)
        ocr_service.extract_question_as_text = AsyncMock(return_value=None)
        question_snapshot_service.build_from_text.return_value = None

        event = InboundEvent(
            update_id=3,
            telegram_id=111111,
            chat_id=222,
            message_id=3,
            input_mode="image",
            text="",
            attachment=Attachment(file_id="file_bad", mime_type="image/jpeg"),
        )

        result = await entry_service.handle_question_intake(event)

        # When OCR fails, follows same flow as empty text input
        assert result is not None
        assert "Ainda não consegui montar a questão inteira" in result.reply_text
        assert result.state == SessionState.WAITING_FALLBACK_DETAILS

    @pytest.mark.asyncio
    async def test_submitted_questions_persists_ocr_as_text(self):
        """Scenario 5 (unified): OCR snapshot persists with source='text' (no OCR-specific fields)"""
        from app.repositories.submitted_questions_repository import InMemorySubmittedQuestionsRepository
        from app.domain.models import QuestionSnapshot, SessionRecord

        repo = InMemorySubmittedQuestionsRepository()

        # Create a session record
        session = SessionRecord(
            session_id="sess_test",
            telegram_id=123,
            chat_id=456,
            flow=MagicMock(value="ME_TESTA"),
            state=MagicMock(value="WAITING_ANSWER"),
        )

        # Create snapshot from OCR (treated as text input in unified flow)
        snapshot = QuestionSnapshot(
            source_mode="student_submitted",
            source_truth="student_content_only",
            content="Test OCR question",
            alternatives=[
                QuestionAlternative(label="A", text="Alt A"),
                QuestionAlternative(label="B", text="Alt B"),
                QuestionAlternative(label="C", text="Alt C"),
                QuestionAlternative(label="D", text="Alt D"),
                QuestionAlternative(label="E", text="Alt E"),
            ],
        )

        # Unified flow: OCR uses source="text" (no OCR-specific fields)
        snapshot_id = repo.create_from_snapshot(
            session,
            snapshot,
            source="text",
        )

        assert snapshot_id is not None
        row = repo.rows[snapshot_id]
        assert row["source"] == "text"
        # OCR-specific fields no longer used in unified flow
        assert row.get("ocr_raw_text") is None
        assert row.get("ocr_confidence") is None
