"""
Testes end-to-end para M2-S5: Relatório Mensal de Progresso.

Cobre AC-6:
  1. Geração com dados reais (questões respondidas, acertos e erros)
  2. Período vazio (zero questões)
  3. Formatação do texto de saída
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.monthly_report_service import (
    MonthlyReport,
    MonthlyReportService,
    TopicError,
    format_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_supabase_client(rows: list[dict]) -> MagicMock:
    """Build a minimal Supabase client stub that returns `rows` on execute()."""
    response = MagicMock()
    response.data = rows

    chain = MagicMock()
    chain.execute.return_value = response
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.gte.return_value = chain

    client = MagicMock()
    client.table.return_value = chain
    return client


def _rows_fixture() -> list[dict]:
    return [
        # 2 corretas
        {"answered_correct": True,  "apkg_generated": False, "subject": "Matemática",  "topic": "Funções"},
        {"answered_correct": True,  "apkg_generated": True,  "subject": "Português",   "topic": "Interpretação"},
        # 3 erradas — 2 em Funções, 1 em Genética
        {"answered_correct": False, "apkg_generated": True,  "subject": "Matemática",  "topic": "Funções"},
        {"answered_correct": False, "apkg_generated": True,  "subject": "Matemática",  "topic": "Funções"},
        {"answered_correct": False, "apkg_generated": False, "subject": "Biologia",    "topic": "Genética"},
    ]


# ---------------------------------------------------------------------------
# 1. Geração com dados reais
# ---------------------------------------------------------------------------

class TestMonthlyReportGeneration(unittest.TestCase):
    def setUp(self) -> None:
        client = _make_supabase_client(_rows_fixture())
        service = MonthlyReportService(client)
        self.report = service.generate(telegram_id=12345, dias=30)

    def test_total_questions(self) -> None:
        self.assertEqual(self.report.total_questions, 5)

    def test_correct_count(self) -> None:
        self.assertEqual(self.report.correct_count, 2)

    def test_accuracy(self) -> None:
        self.assertEqual(self.report.accuracy_pct, 40.0)

    def test_anki_cards(self) -> None:
        self.assertEqual(self.report.anki_cards_generated, 3)

    def test_top_error_topic_is_funcoes(self) -> None:
        self.assertGreater(len(self.report.top_error_topics), 0)
        top = self.report.top_error_topics[0]
        self.assertEqual(top.topic, "Funções")
        self.assertEqual(top.error_count, 2)

    def test_top_errors_at_most_3(self) -> None:
        self.assertLessEqual(len(self.report.top_error_topics), 3)

    def test_goal_pct_uses_env_default(self) -> None:
        # sem env configurado, goal = 100 → 5/100 = 5%
        self.assertEqual(self.report.goal_questions, 100)
        self.assertEqual(self.report.goal_pct, 5.0)


# ---------------------------------------------------------------------------
# 2. Período vazio (zero questões)
# ---------------------------------------------------------------------------

class TestMonthlyReportEmpty(unittest.TestCase):
    def setUp(self) -> None:
        client = _make_supabase_client([])
        service = MonthlyReportService(client)
        self.report = service.generate(telegram_id=99, dias=30)

    def test_zero_questions(self) -> None:
        self.assertEqual(self.report.total_questions, 0)

    def test_accuracy_is_zero(self) -> None:
        self.assertEqual(self.report.accuracy_pct, 0.0)

    def test_no_error_topics(self) -> None:
        self.assertEqual(self.report.top_error_topics, [])

    def test_anki_is_zero(self) -> None:
        self.assertEqual(self.report.anki_cards_generated, 0)


# ---------------------------------------------------------------------------
# 3. Formatação do texto de saída
# ---------------------------------------------------------------------------

class TestReportFormatting(unittest.TestCase):
    def _report_with_data(self) -> MonthlyReport:
        return MonthlyReport(
            telegram_id=1,
            dias=30,
            total_questions=10,
            correct_count=7,
            accuracy_pct=70.0,
            top_error_topics=[
                TopicError(subject="Matemática", topic="Funções", error_count=2),
                TopicError(subject="Biologia",   topic="Genética", error_count=1),
            ],
            anki_cards_generated=2,
            goal_questions=100,
        )

    def _report_empty(self) -> MonthlyReport:
        return MonthlyReport(
            telegram_id=1,
            dias=30,
            total_questions=0,
            correct_count=0,
            accuracy_pct=0.0,
            top_error_topics=[],
            anki_cards_generated=0,
            goal_questions=100,
        )

    def test_format_contains_header(self) -> None:
        text = format_report(self._report_with_data())
        self.assertIn("relatório", text.lower())

    def test_format_contains_accuracy(self) -> None:
        text = format_report(self._report_with_data())
        self.assertIn("70.0%", text)

    def test_format_contains_anki_count(self) -> None:
        text = format_report(self._report_with_data())
        self.assertIn("2", text)

    def test_format_contains_top_topic(self) -> None:
        text = format_report(self._report_with_data())
        self.assertIn("Funções", text)

    def test_format_empty_period_message(self) -> None:
        text = format_report(self._report_empty())
        self.assertIn("Nenhuma questão", text)

    def test_format_no_markdown_headers(self) -> None:
        """Telegram plain-text mode: sem # ou ** duplos quebrando o layout."""
        text = format_report(self._report_with_data())
        # Sem markdown de cabeçalho (# H1, ## H2)
        self.assertNotIn("## ", text)
        self.assertNotIn("# ", text)

    def test_format_does_not_use_complex_tables(self) -> None:
        text = format_report(self._report_with_data())
        self.assertNotIn("|", text)

    def test_format_goal_reached_message(self) -> None:
        report = MonthlyReport(
            telegram_id=1,
            dias=30,
            total_questions=100,
            correct_count=80,
            accuracy_pct=80.0,
            top_error_topics=[],
            anki_cards_generated=10,
            goal_questions=100,
        )
        text = format_report(report)
        self.assertIn("Meta atingida", text)

    def test_format_below_50_pct_encouragement(self) -> None:
        report = MonthlyReport(
            telegram_id=1,
            dias=30,
            total_questions=10,
            correct_count=5,
            accuracy_pct=50.0,
            top_error_topics=[],
            anki_cards_generated=0,
            goal_questions=100,
        )
        text = format_report(report)
        # below 50% of goal → encouragement message
        self.assertIn("uma questão por dia", text)


# ---------------------------------------------------------------------------
# 4. Webhook /relatorio integration (handler fast-path)
# ---------------------------------------------------------------------------

class TestTelegramWebhookRelatorio(unittest.IsolatedAsyncioTestCase):
    async def test_relatorio_command_triggers_report(self) -> None:
        from fastapi.testclient import TestClient
        import asyncio
        from app.main import app

        payload = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "chat": {"id": 111, "type": "private"},
                "from": {"id": 111, "is_bot": False, "first_name": "Aluna"},
                "text": "/relatorio",
                "date": 0,
            },
        }

        mock_gateway = AsyncMock()
        mock_gateway.send_text = AsyncMock()

        fake_rows: list[dict] = []
        supabase_response = MagicMock()
        supabase_response.data = fake_rows
        chain = MagicMock()
        chain.execute.return_value = supabase_response
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.gte.return_value = chain
        mock_supabase = MagicMock()
        mock_supabase.table.return_value = chain

        with (
            patch("app.api.telegram_webhook.SupabaseClientFactory") as MockFactory,
            patch("app.api.telegram_webhook.resolve_runtime_services") as mock_rt,
        ):
            factory_instance = MagicMock()
            factory_instance.create.return_value = mock_supabase
            MockFactory.return_value = factory_instance

            rt = MagicMock()
            rt.telegram_gateway = mock_gateway
            mock_rt.return_value = rt

            client = TestClient(app)
            response = client.post(
                "/webhooks/telegram",
                json=payload,
            )

        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertEqual(data.get("action"), "relatorio_sent")
        mock_gateway.send_text.assert_called_once()
        call_args = mock_gateway.send_text.call_args
        self.assertEqual(call_args[0][0], 111)  # chat_id
        self.assertIn("relatório", call_args[0][1].lower())

    async def test_relatorio_dias_param(self) -> None:
        """--dias 15 deve ser passado corretamente para o service."""
        from app.api.telegram_webhook import _parse_relatorio_dias
        self.assertEqual(_parse_relatorio_dias("/relatorio --dias 15"), 15)
        self.assertEqual(_parse_relatorio_dias("/relatorio"), 30)
        self.assertEqual(_parse_relatorio_dias("/relatorio --dias abc"), 30)


if __name__ == "__main__":
    unittest.main()
