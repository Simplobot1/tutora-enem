from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class TopicError:
    subject: str
    topic: str
    error_count: int


@dataclass(frozen=True)
class MonthlyReport:
    telegram_id: int
    dias: int
    total_questions: int
    correct_count: int
    accuracy_pct: float
    top_error_topics: list[TopicError]
    anki_cards_generated: int
    goal_questions: int

    @property
    def goal_pct(self) -> float:
        if self.goal_questions <= 0:
            return 0.0
        return min(100.0, round(self.total_questions / self.goal_questions * 100, 1))


def _default_goal() -> int:
    try:
        return int(os.getenv("MONTHLY_GOAL_QUESTIONS", "100"))
    except ValueError:
        return 100


class MonthlyReportService:
    def __init__(self, client: Any | None) -> None:
        self.client = client

    def generate(self, telegram_id: int, dias: int = 30) -> MonthlyReport:
        since = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()

        rows = self._fetch_submitted_questions(telegram_id, since)

        total = len(rows)
        correct_count = sum(1 for r in rows if r.get("answered_correct") is True)
        accuracy = round(correct_count / total * 100, 1) if total > 0 else 0.0
        anki_cards = sum(1 for r in rows if r.get("apkg_generated") is True)
        top_errors = self._top_error_topics(rows)
        goal = _default_goal()

        return MonthlyReport(
            telegram_id=telegram_id,
            dias=dias,
            total_questions=total,
            correct_count=correct_count,
            accuracy_pct=accuracy,
            top_error_topics=top_errors,
            anki_cards_generated=anki_cards,
            goal_questions=goal,
        )

    def _fetch_submitted_questions(self, telegram_id: int, since: str) -> list[dict[str, Any]]:
        if self.client is None:
            return []
        try:
            response = (
                self.client.table("submitted_questions")
                .select("answered_correct,apkg_generated,subject,topic")
                .eq("telegram_id", telegram_id)
                .gte("created_at", since)
                .execute()
            )
            return getattr(response, "data", None) or []
        except Exception:
            return []

    def _top_error_topics(self, rows: list[dict[str, Any]], top_n: int = 3) -> list[TopicError]:
        counts: dict[tuple[str, str], int] = {}
        for r in rows:
            if r.get("answered_correct") is False:
                subject = r.get("subject") or "Sem matéria"
                topic = r.get("topic") or "Sem tópico"
                key = (subject, topic)
                counts[key] = counts.get(key, 0) + 1

        sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [
            TopicError(subject=k[0], topic=k[1], error_count=v)
            for k, v in sorted_items[:top_n]
        ]


def format_report(report: MonthlyReport) -> str:
    lines: list[str] = []
    lines.append("📊 *Seu relatório de progresso*")
    lines.append(f"_(últimos {report.dias} dias)_")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("")

    if report.total_questions == 0:
        lines.append("Nenhuma questão respondida nesse período. 😅")
        lines.append("Que tal começar hoje? Manda uma questão pra mim! 💪")
        return "\n".join(lines)

    lines.append(f"✅ Questões respondidas: *{report.total_questions}*")
    lines.append(f"🎯 Taxa de acerto: *{report.accuracy_pct}%*")
    lines.append(f"   ({report.correct_count} de {report.total_questions} corretas)")
    lines.append("")

    if report.top_error_topics:
        lines.append("❌ Top erros por tópico:")
        for i, te in enumerate(report.top_error_topics, start=1):
            label = te.topic if te.topic != "Sem tópico" else te.subject
            lines.append(f"   {i}. {label} ({te.error_count}x)")
    else:
        lines.append("❌ Nenhum erro registrado — incrível! 🌟")
    lines.append("")

    lines.append(f"🃏 Flashcards Anki gerados: *{report.anki_cards_generated}*")
    lines.append("")

    lines.append(f"📈 Meta do período: *{report.goal_pct}%*")
    lines.append(f"   ({report.total_questions}/{report.goal_questions} questões)")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━")

    if report.goal_pct >= 100:
        lines.append("Meta atingida! 🏆 Você arrasoou demais!")
    elif report.goal_pct >= 50:
        lines.append("Tá indo bem! Continua assim que você chega lá. 💪")
    else:
        lines.append("Ainda dá tempo — uma questão por dia já faz diferença! 🌱")

    return "\n".join(lines)
