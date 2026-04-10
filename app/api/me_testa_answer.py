"""HTTP API for me-testa answer processing (M2-S3).

Handles student answer submissions, error classification, and review preparation.
"""

from __future__ import annotations

from app.api.runtime import get_runtime
from app.domain.models import InboundEvent
from app.domain.states import SessionFlow
from app.services.me_testa_answer_service import MeTestaAnswerService
from fastapi import HTTPException, Router

router = Router(prefix="/api/me-testa", tags=["me-testa"])


@router.post("/answer")
async def submit_answer(
    telegram_id: int,
    chat_id: int,
    answer: str,
) -> dict:
    """Submit student answer to an active question.

    M2-S3: Process answer, classify error if wrong, prepare review card.

    Args:
        telegram_id: Student's telegram ID
        chat_id: Chat ID for context
        answer: Student's selected alternative (A-E)

    Returns:
        Response with feedback, error type, and review card info
    """
    try:
        runtime = get_runtime()
        session_service = runtime.session_service
        answer_service = MeTestaAnswerService(runtime.study_sessions_repository)

        # Get active session
        session = session_service.get_or_create_active_session(
            telegram_id=telegram_id,
            chat_id=chat_id,
            flow=SessionFlow.ME_TESTA,
        )

        if session is None:
            raise HTTPException(status_code=404, detail="No active session")

        # Process answer
        result = await answer_service.process_answer(
            telegram_id=telegram_id,
            student_answer=answer,
            session=session,
        )

        return {
            "status": "success",
            "state": result.state.value,
            "reply": result.reply_text,
            "metadata": result.metadata,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
