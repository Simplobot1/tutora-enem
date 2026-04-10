from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

from app.adapters.telegram_api import NullTelegramGateway
from app.clients.llm import LLMClient
from app.clients.supabase import SupabaseClientFactory
from app.config import settings
from app.repositories.questions_repository import QuestionsRepository
from app.repositories.study_sessions_repository import InMemoryStudySessionsRepository, SupabaseStudySessionsRepository
from app.services.intake_service import IntakeService
from app.services.me_testa_entry_service import MeTestaEntryService
from app.services.me_testa_answer_service import MeTestaAnswerService
from app.services.me_testa_service import MeTestaService
from app.services.question_snapshot_service import QuestionSnapshotService
from app.services.session_service import SessionService
from app.services.socratico_service import SocraticoService


@dataclass(frozen=True, slots=True)
class RuntimeServices:
    intake_service: IntakeService
    session_service: SessionService
    entry_service: MeTestaEntryService
    me_testa_service: MeTestaService


_runtime_services_override: Callable[[], RuntimeServices] | None = None


@lru_cache(maxsize=1)
def get_runtime_services() -> RuntimeServices:
    supabase_client = SupabaseClientFactory(
        url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
    ).create()
    session_repository = (
        SupabaseStudySessionsRepository(supabase_client)
        if supabase_client is not None
        else InMemoryStudySessionsRepository()
    )
    session_service = SessionService(session_repository)
    questions_repository = QuestionsRepository(supabase_client)
    question_snapshot_service = QuestionSnapshotService()
    entry_service = MeTestaEntryService(
        session_service=session_service,
        question_snapshot_service=question_snapshot_service,
        questions_repository=questions_repository,
    )
    socratico_service = SocraticoService()
    answer_service = MeTestaAnswerService(
        repository=session_repository,
        socratico_service=socratico_service,
    )
    me_testa_service = MeTestaService(
        session_service=session_service,
        telegram_gateway=NullTelegramGateway(),
        llm_client=LLMClient(api_key=settings.anthropic_api_key),
        entry_service=entry_service,
        answer_service=answer_service,
        socratico_service=socratico_service,
    )
    return RuntimeServices(
        intake_service=IntakeService(),
        session_service=session_service,
        entry_service=entry_service,
        me_testa_service=me_testa_service,
    )


def set_runtime_services_override(factory: Callable[[], RuntimeServices] | None) -> None:
    global _runtime_services_override
    _runtime_services_override = factory


def resolve_runtime_services() -> RuntimeServices:
    if _runtime_services_override is not None:
        return _runtime_services_override()
    return get_runtime_services()
