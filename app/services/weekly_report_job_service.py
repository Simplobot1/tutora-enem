"""Weekly Report Job Service for Progress Aggregation.

M4-S1: Generate weekly progress reports aggregating student stats
without exposing telegram_id (privacy-first).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.domain.states import SessionFlow, SessionState
from app.repositories.study_sessions_repository import StudySessionsRepository

logger = logging.getLogger(__name__)


@dataclass
class WeeklyStats:
    """Aggregated statistics for a weekly report."""

    period_start: str  # ISO 8601
    period_end: str  # ISO 8601
    total_sessions: int = 0
    total_questions: int = 0
    questions_correct: int = 0
    accuracy_percentage: float = 0.0
    subjects_covered: set[str] = None
    topics_covered: set[str] = None
    mood_distribution: dict[str, int] = None
    learning_paths_used: dict[str, int] = None

    def __post_init__(self) -> None:
        if self.subjects_covered is None:
            self.subjects_covered = set()
        if self.topics_covered is None:
            self.topics_covered = set()
        if self.mood_distribution is None:
            self.mood_distribution = {}
        if self.learning_paths_used is None:
            self.learning_paths_used = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for export (telegram_id NOT included)."""
        return {
            "period": {
                "start": self.period_start,
                "end": self.period_end,
            },
            "sessions": {
                "total": self.total_sessions,
            },
            "questions": {
                "total": self.total_questions,
                "correct": self.questions_correct,
                "accuracy_percentage": round(self.accuracy_percentage, 2),
            },
            "coverage": {
                "subjects": sorted(self.subjects_covered),
                "topics": sorted(self.topics_covered),
            },
            "mood": self.mood_distribution,
            "learning_paths": self.learning_paths_used,
            "generated_at": datetime.now().isoformat(),
        }


class WeeklyReportJobService:
    """Generate weekly progress reports for students."""

    def __init__(self, repository: StudySessionsRepository) -> None:
        self.repository = repository

    def generate_weekly_report(self, days_back: int = 7) -> WeeklyStats:
        """Generate aggregated report for last N days.

        Args:
            days_back: Number of days to include in report (default 7)

        Returns:
            WeeklyStats with aggregated metrics (NO telegram_id exposure)
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        stats = WeeklyStats(
            period_start=start_date.isoformat(),
            period_end=end_date.isoformat(),
        )

        # Note: In a real scenario, we'd query the repository
        # For now, we document the interface and test with mock data
        logger.info(f"generating weekly report for {days_back} days")

        return stats

    def aggregate_session_stats(self, sessions: list) -> dict[str, Any]:
        """Aggregate statistics from session list.

        Args:
            sessions: List of SessionRecord objects

        Returns:
            Dictionary with aggregated stats (NO telegram_id)
        """
        stats = {
            "total_sessions": len(sessions),
            "total_questions_attempted": 0,
            "correct_answers": 0,
            "accuracy": 0.0,
            "subjects": set(),
            "topics": set(),
            "moods": {},
            "learning_paths": {},
        }

        for session in sessions:
            # Count questions
            if session.question_snapshot is not None:
                stats["total_questions_attempted"] += 1

            # Track mood (aggregated, not linked to telegram_id)
            mood = session.mood or "unknown"
            stats["moods"][mood] = stats["moods"].get(mood, 0) + 1

            # Track subject/topic
            if session.question_snapshot:
                subject = session.question_snapshot.subject or "unknown"
                topic = session.question_snapshot.topic or "unknown"
                stats["subjects"].add(subject)
                stats["topics"].add(topic)

            # Track learning path (socrático vs direto)
            if session.state == SessionState.DONE:
                if hasattr(session.metadata, "llm_trace") and session.metadata.llm_trace:
                    path = session.metadata.llm_trace.get("learning_path", "unknown")
                else:
                    path = "unknown"
                stats["learning_paths"][path] = stats["learning_paths"].get(path, 0) + 1

        # Calculate accuracy (placeholder for now)
        if stats["total_questions_attempted"] > 0:
            # In real scenario, would count correct answers from anki status
            stats["accuracy"] = 0.0

        return stats


class ReportExporter:
    """Export weekly reports in various formats."""

    @staticmethod
    def export_json(stats: WeeklyStats) -> str:
        """Export stats as JSON string."""
        import json

        return json.dumps(stats.to_dict(), indent=2)

    @staticmethod
    def export_text(stats: WeeklyStats) -> str:
        """Export stats as human-readable text."""
        data = stats.to_dict()
        lines = [
            "📊 Relatório Semanal - Tutora ENEM",
            "=" * 40,
            f"Período: {data['period']['start']} a {data['period']['end']}",
            "",
            "📚 Questões",
            f"  Total: {data['questions']['total']}",
            f"  Acertos: {data['questions']['correct']}",
            f"  Acurácia: {data['questions']['accuracy_percentage']}%",
            "",
            "📖 Cobertura",
            f"  Disciplinas: {', '.join(data['coverage']['subjects']) or 'nenhuma'}",
            f"  Tópicos: {len(data['coverage']['topics'])} cobertos",
            "",
            "😊 Disposição",
        ]

        for mood, count in data["mood"].items():
            lines.append(f"  {mood}: {count}x")

        lines.append("")
        lines.append("🎯 Caminhos de Aprendizagem")
        for path, count in data["learning_paths"].items():
            lines.append(f"  {path}: {count}x")

        lines.append("")
        lines.append(f"Gerado em: {data['generated_at']}")

        return "\n".join(lines)
