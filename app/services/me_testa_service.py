from __future__ import annotations

import logging

from app.clients.llm import LLMClient
from app.adapters.telegram_api import TelegramGateway
from app.domain.models import InboundEvent, ServiceResult
from app.domain.states import SessionFlow
from app.domain.states import SessionState
from app.services.me_testa_entry_service import MeTestaEntryService
from app.services.me_testa_answer_service import MeTestaAnswerService
from app.services.session_service import SessionService
from app.services.socratico_service import SocraticoService

logger = logging.getLogger(__name__)


class MeTestaService:
    def __init__(
        self,
        session_service: SessionService,
        telegram_gateway: TelegramGateway,
        llm_client: LLMClient,
        entry_service: MeTestaEntryService,
        answer_service: MeTestaAnswerService | None = None,
        socratico_service: SocraticoService | None = None,
    ) -> None:
        self.session_service = session_service
        self.telegram_gateway = telegram_gateway
        self.llm_client = llm_client
        self.entry_service = entry_service
        self.answer_service = answer_service
        self.socratico_service = socratico_service

    async def handle_event(self, event: InboundEvent) -> ServiceResult:
        session = self.session_service.get_or_create_active_session(
            telegram_id=event.telegram_id,
            chat_id=event.chat_id,
            flow=SessionFlow.ME_TESTA,
        )

        logger.info(
            f"me_testa_service: handling event for telegram_id={event.telegram_id}, "
            f"session_id={session.session_id}, state={session.state}"
        )

        # Intake: new question or fallback details
        if session.state in {SessionState.IDLE, SessionState.WAITING_FALLBACK_DETAILS, SessionState.DONE}:
            return await self.entry_service.handle_question_intake(event)

        # Answer processing
        if session.state == SessionState.WAITING_ANSWER:
            if self.answer_service is None:
                reply = "Erro: avaliador de respostas não está disponível"
                logger.error(f"answer_service is None for telegram_id={event.telegram_id}")
                return ServiceResult(state=session.state, reply_text=reply, metadata={"error": "no_answer_service"})

            return await self.answer_service.process_answer(
                telegram_id=event.telegram_id,
                student_answer=event.text or event.caption,
                session=session,
            )

        # Socratic mode: Q1 response
        if session.state == SessionState.WAITING_SOCRATIC_Q1:
            if self.socratico_service is None:
                reply = "Erro: modo socrático não está disponível"
                logger.error(f"socratico_service is None for telegram_id={event.telegram_id}")
                return ServiceResult(state=session.state, reply_text=reply, metadata={"error": "no_socratico_service"})

            result = await self.socratico_service.process_q1_response(
                session=session,
                student_response=event.text or event.caption,
            )
            self.session_service.save(session)
            return result

        # Socratic mode: Q2 response
        if session.state == SessionState.WAITING_SOCRATIC_Q2:
            if self.socratico_service is None:
                reply = "Erro: modo socrático não está disponível"
                logger.error(f"socratico_service is None for telegram_id={event.telegram_id}")
                return ServiceResult(state=session.state, reply_text=reply, metadata={"error": "no_socratico_service"})

            result = await self.socratico_service.process_q2_response(
                session=session,
                student_response=event.text or event.caption,
            )
            self.session_service.save(session)
            return result

        return ServiceResult(
            state=session.state,
            reply_text="Recebi sua mensagem, mas esse estado ainda não foi conectado no novo backend.",
            metadata={"state": session.state},
        )
