import unittest

from app.domain.models import QuestionAlternative, QuestionSnapshot
from app.domain.session_metadata import AnkiMetadata, QuestionRef, ReviewCard, SessionMetadata
from app.domain.states import SessionFlow, SessionState


class SessionMetadataTest(unittest.TestCase):
    def test_to_dict_preserves_canonical_contract(self) -> None:
        metadata = SessionMetadata(
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            source_mode="student_submitted",
            question_snapshot=QuestionSnapshot(
                source_mode="student_submitted",
                source_truth="student_content_only",
                content="Enunciado",
                alternatives=[QuestionAlternative(label="A", text="Opção A", explanation="Por que A está errada")],
                correct_alternative="B",
                explanation="Explicação curta",
            ),
            question_id=None,
            question_ref=QuestionRef(question_id=None, snapshot_id=None, bank_match_confidence=None),
            review_card=ReviewCard(review_card_id="rev-1", front="Frente", back="Verso"),
            anki=AnkiMetadata(status="queued_local_build", builder_mode="review_card", apkg_path=None),
            last_user_message={"text": "Pergunta"},
            llm_trace={"provider": "claude"},
        )

        data = metadata.to_dict()
        self.assertEqual(data["flow"], "me_testa")
        self.assertEqual(data["state"], "WAITING_ANSWER")
        self.assertEqual(data["question_snapshot"]["alternatives"][0]["label"], "A")
        self.assertEqual(data["question_snapshot"]["alternatives"][0]["explanation"], "Por que A está errada")
        self.assertEqual(data["question_snapshot"]["correct_alternative"], "B")
        self.assertEqual(data["question_snapshot"]["explanation"], "Explicação curta")
        self.assertEqual(data["review_card"]["review_card_id"], "rev-1")
        self.assertEqual(data["anki"]["builder_mode"], "review_card")
