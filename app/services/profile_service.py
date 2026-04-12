"""
Profile Service — Generate user error profile and stats from submitted questions.

Handles aggregation queries for:
- Top 5 topics with most errors
- Error type distribution (conceitual, interpretacao, atencao)
- Overall accuracy stats
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def format_profile(stats: dict[str, Any]) -> str | list[str]:
    """
    Format profile stats into Telegram-friendly text.

    Returns:
        str if <= 2000 chars, or list[str] with 2 messages if longer
    """
    if stats.get("total", 0) == 0:
        return "Ainda sem questões respondidas! Manda uma pra eu te ajudar 😊"

    lines = [
        "📊 Seu Perfil de Estudos",
        "",
    ]

    # Top 5 topics with errors
    top_topicos = stats.get("top_topicos", [])
    if top_topicos:
        lines.append("📉 Top 5 tópicos com mais erros:")
        for idx, item in enumerate(top_topicos, 1):
            topic = item.get("topic") or "(sem tópico)"
            erros = item.get("erros", 0)
            if stats.get("compact"):
                # Compact mode: abbreviate
                lines.append(f"{idx}. {topic[:20]} — {erros}x")
            else:
                lines.append(f"{idx}. {topic} — {erros} erros")
        lines.append("")

    # Error type distribution
    erros_por_tipo = stats.get("erros_por_tipo", {})
    if erros_por_tipo:
        lines.append("🔍 Tipo de erro:")
        for tipo, percentual in [("conceitual", "Conceitual"), ("interpretacao", "Interpretação"), ("atencao", "Atenção")]:
            pct = erros_por_tipo.get(tipo, 0.0)
            lines.append(f"• {percentual}: {pct:.0f}%")
        lines.append("")

    # Accuracy stats
    total = stats.get("total", 0)
    acertos = stats.get("acertos", 0)
    taxa = stats.get("taxa_acerto", 0.0)
    lines.append(f"✅ Taxa geral de acerto: {taxa*100:.0f}% ({acertos} de {total} questões)")

    full_text = "\n".join(lines)

    # Check length and split if necessary
    if len(full_text) <= 2000:
        return full_text

    # Split into 2 messages: stats + detailed breakdown
    message1 = "\n".join([
        "📊 Seu Perfil de Estudos",
        "",
        f"✅ Taxa geral de acerto: {taxa*100:.0f}%",
        f"📝 Total: {acertos}/{total} questões",
    ])

    message2_lines = [
        "📊 Detalhes",
        "",
    ]

    if top_topicos:
        message2_lines.append("📉 Top tópicos com erros:")
        for idx, item in enumerate(top_topicos[:3], 1):  # Show only top 3 in second message
            topic = item.get("topic") or "(sem tópico)"
            erros = item.get("erros", 0)
            message2_lines.append(f"{idx}. {topic} — {erros}x")
        message2_lines.append("")

    if erros_por_tipo:
        message2_lines.append("🔍 Distribuição de erros:")
        for tipo, percentual in [("conceitual", "Conceitual"), ("interpretacao", "Interpretação"), ("atencao", "Atenção")]:
            pct = erros_por_tipo.get(tipo, 0.0)
            if pct > 0:
                message2_lines.append(f"• {percentual}: {pct:.0f}%")

    message2 = "\n".join(message2_lines)

    return [message1, message2]


class ProfileService:
    """Generate user profile stats from submitted questions."""

    def __init__(self, supabase_client: Any | None) -> None:
        self.client = supabase_client

    def generate(self, telegram_id: int) -> dict[str, Any]:
        """
        Generate profile stats for a user.

        Args:
            telegram_id: Telegram user ID

        Returns:
            Dict with keys: total, acertos, taxa_acerto, top_topicos, erros_por_tipo, compact
        """
        if self.client is None:
            logger.warning("ProfileService: no supabase client available")
            return {}

        try:
            # Single query: fetch all submitted questions for user
            response = self.client.table("submitted_questions").select(
                "id, answered_correct, final_error_type, topic"
            ).eq("telegram_id", telegram_id).execute()

            rows = getattr(response, "data", None) or []

            # Calculate totals
            total = len(rows)
            acertos = sum(1 for row in rows if row.get("answered_correct") is True)
            taxa_acerto = acertos / total if total > 0 else 0.0

            # Calculate top 5 topics with errors
            topic_errors: dict[str, int] = {}
            for row in rows:
                if row.get("answered_correct") is False:
                    topic = row.get("topic")
                    if topic:  # Skip null/empty topics
                        topic_errors[topic] = topic_errors.get(topic, 0) + 1

            top_topicos = [
                {"topic": topic, "erros": count}
                for topic, count in sorted(topic_errors.items(), key=lambda x: x[1], reverse=True)[:5]
            ]

            # Calculate error type distribution (only for errors)
            error_type_counts: dict[str, int] = {}
            for row in rows:
                if row.get("answered_correct") is False:
                    error_type = row.get("final_error_type")
                    if error_type:
                        error_type_counts[error_type] = error_type_counts.get(error_type, 0) + 1

            total_com_erro = sum(error_type_counts.values())
            erros_por_tipo = {}
            if total_com_erro > 0:
                for tipo in ["conceitual", "interpretacao", "atencao"]:
                    count = error_type_counts.get(tipo, 0)
                    erros_por_tipo[tipo] = (count / total_com_erro) * 100.0
            else:
                erros_por_tipo = {"conceitual": 0.0, "interpretacao": 0.0, "atencao": 0.0}

            compact = total > 100

            return {
                "total": total,
                "acertos": acertos,
                "taxa_acerto": taxa_acerto,
                "top_topicos": top_topicos,
                "erros_por_tipo": erros_por_tipo,
                "compact": compact,
            }

        except Exception as e:
            logger.warning("ProfileService.generate failed for telegram_id %d: %s", telegram_id, str(e))
            return {}
