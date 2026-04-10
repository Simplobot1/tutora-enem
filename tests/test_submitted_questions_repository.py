import unittest

from app.domain.models import QuestionAlternative, QuestionSnapshot, SessionRecord
from app.domain.session_metadata import SessionMetadata
from app.domain.states import SessionFlow, SessionState
from app.repositories.submitted_questions_repository import SupabaseSubmittedQuestionsRepository


class MissingTableClient:
    def table(self, _name: str):
        return self

    def insert(self, _payload):
        return self

    def update(self, _payload):
        return self

    def eq(self, *_args):
        return self

    def execute(self):
        raise Exception(
            "{'message': \"Could not find the table 'public.submitted_questions' in the schema cache\", 'code': 'PGRST205'}"
        )


class SubmittedQuestionsRepositoryTest(unittest.TestCase):
    def test_missing_table_disables_repository_without_raising(self) -> None:
        repository = SupabaseSubmittedQuestionsRepository(MissingTableClient())
        session = SessionRecord(
            session_id="session-1",
            telegram_id=123,
            chat_id=321,
            flow=SessionFlow.ME_TESTA,
            state=SessionState.WAITING_ANSWER,
            metadata=SessionMetadata(
                flow=SessionFlow.ME_TESTA,
                state=SessionState.WAITING_ANSWER,
                source_mode="student_submitted",
            ),
        )
        snapshot = QuestionSnapshot(
            source_mode="student_submitted",
            source_truth="student_content_only",
            content="Pergunta",
            alternatives=[QuestionAlternative(label="A", text="Opção A")],
            correct_alternative="A",
            explanation="Explicação",
            subject="Biologia",
            topic="Parasitologia",
        )

        snapshot_id = repository.create_from_snapshot(session, snapshot)

        self.assertIsNone(snapshot_id)
        self.assertTrue(repository._disabled)

        repository.sync_snapshot("snapshot-1", snapshot)
        repository.mark_result(
            "snapshot-1",
            answered_correct=True,
            retry_attempts=0,
            sent_to_anki=False,
            apkg_generated=False,
        )
