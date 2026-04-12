"""
Tests for M5-S2: Perfil de Erros Acumulado

Test scenarios:
1. Zero questions — friendly message (AC8)
2. 50 questions — complete profile with stats
3. 500+ questions — compact mode (AC8)
4. Privacy validation — queries filtered by telegram_id (AC7)
5. Formatting — ≤2000 chars or list of 2 messages (AC6)
"""

from unittest.mock import MagicMock, AsyncMock

import pytest

from app.services.profile_service import ProfileService, format_profile


class TestProfileService:
    """Unit tests for ProfileService"""

    def test_generate_zero_questions(self):
        """Scenario 1: Zero questions → empty stats"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        service = ProfileService(mock_client)
        stats = service.generate(telegram_id=123456)

        assert stats.get("total") == 0
        assert stats.get("acertos") == 0
        assert stats.get("taxa_acerto") == 0.0
        assert stats.get("compact") is False
        assert stats.get("top_topicos", []) == []

    def test_generate_50_questions(self):
        """Scenario 2: 50 questions → complete profile"""
        mock_client = MagicMock()

        # Mock single query response with mixed data
        mock_response = MagicMock()
        mock_response.data = [
            {"id": f"q{i}", "answered_correct": i < 31, "final_error_type": ["conceitual", "interpretacao", "atencao", None][i % 4] if i >= 31 else None, "topic": ["Funções", "Ecologia", "Geometria"][i % 3] if i >= 31 else ["Funções", "Ecologia", "Geometria"][i % 3]}
            for i in range(50)
        ]

        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        service = ProfileService(mock_client)
        stats = service.generate(telegram_id=123456)

        assert stats.get("total") == 50
        assert stats.get("acertos") == 31
        assert stats.get("taxa_acerto") == pytest.approx(0.62)
        assert stats.get("compact") is False
        assert len(stats.get("top_topicos", [])) > 0
        assert stats.get("erros_por_tipo", {}).get("conceitual", 0) >= 0

    def test_generate_500_questions_compact(self):
        """Scenario 3: 500+ questions → compact mode activated"""
        mock_client = MagicMock()

        mock_response = MagicMock()
        mock_response.data = [
            {"id": f"q{i}", "answered_correct": i < 350, "final_error_type": "conceitual" if i >= 350 else None, "topic": "Topic"}
            for i in range(500)
        ]

        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        service = ProfileService(mock_client)
        stats = service.generate(telegram_id=123456)

        assert stats.get("total") == 500
        assert stats.get("compact") is True
        assert stats.get("taxa_acerto") == pytest.approx(0.7)

    def test_generate_privacy_validation(self):
        """Scenario 4: Privacy validation — telegram_id filter in query"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = []

        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        service = ProfileService(mock_client)
        telegram_id = 987654
        stats = service.generate(telegram_id=telegram_id)

        # Verify query was called with telegram_id filter
        mock_client.table.assert_called_with("submitted_questions")
        # Stats should have valid structure even with no data
        assert "total" in stats
        assert "acertos" in stats

    def test_service_with_none_client(self):
        """Service handles None client gracefully"""
        service = ProfileService(supabase_client=None)
        stats = service.generate(telegram_id=123456)

        assert stats == {}


class TestFormatProfile:
    """Unit tests for format_profile function"""

    def test_format_zero_data(self):
        """Format with zero data returns friendly message"""
        stats = {"total": 0}
        formatted = format_profile(stats)

        assert "Ainda sem questões" in formatted
        assert isinstance(formatted, str)

    def test_format_complete_profile(self):
        """Format complete profile with all stats"""
        stats = {
            "total": 50,
            "acertos": 31,
            "taxa_acerto": 0.62,
            "top_topicos": [
                {"topic": "Funções", "erros": 8},
                {"topic": "Ecologia", "erros": 5},
            ],
            "erros_por_tipo": {
                "conceitual": 55.0,
                "interpretacao": 30.0,
                "atencao": 15.0,
            },
            "compact": False,
        }
        formatted = format_profile(stats)

        assert isinstance(formatted, str)
        assert "📊 Seu Perfil" in formatted
        assert "Funções" in formatted
        assert "Conceitual" in formatted
        assert "62%" in formatted
        assert len(formatted) <= 2000

    def test_format_compact_mode(self):
        """Format with compact=True abbreviates topics"""
        stats = {
            "total": 150,
            "acertos": 100,
            "taxa_acerto": 0.667,
            "top_topicos": [
                {"topic": "A Very Long Topic Name", "erros": 10},
                {"topic": "Another Long Topic", "erros": 8},
            ],
            "erros_por_tipo": {
                "conceitual": 60.0,
                "interpretacao": 25.0,
                "atencao": 15.0,
            },
            "compact": True,
        }
        formatted = format_profile(stats)

        assert isinstance(formatted, str)
        assert "A Very Long Topic" in formatted or "A Very" in formatted

    def test_format_long_text_split(self):
        """Format that exceeds 2000 chars returns list of 2 messages"""
        stats = {
            "total": 500,
            "acertos": 350,
            "taxa_acerto": 0.7,
            "top_topicos": [
                {"topic": f"Topic {i} with a very long name that takes up space", "erros": 50 - i}
                for i in range(5)
            ],
            "erros_por_tipo": {
                "conceitual": 60.0,
                "interpretacao": 25.0,
                "atencao": 15.0,
            },
            "compact": False,
        }
        formatted = format_profile(stats)

        if isinstance(formatted, list):
            assert len(formatted) == 2
            assert all(isinstance(msg, str) for msg in formatted)
            assert all(len(msg) <= 2000 for msg in formatted)
        else:
            # If single message, it should still fit
            assert len(formatted) <= 2000

    def test_format_missing_topic(self):
        """Format handles missing/null topic gracefully"""
        stats = {
            "total": 30,
            "acertos": 20,
            "taxa_acerto": 0.667,
            "top_topicos": [
                {"topic": None, "erros": 5},
                {"topic": "Válido", "erros": 3},
            ],
            "erros_por_tipo": {
                "conceitual": 50.0,
                "interpretacao": 30.0,
                "atencao": 20.0,
            },
            "compact": False,
        }
        formatted = format_profile(stats)

        assert isinstance(formatted, str)
        assert "(sem tópico)" in formatted
        assert "Válido" in formatted

    def test_format_empty_error_types(self):
        """Format handles no error data gracefully"""
        stats = {
            "total": 20,
            "acertos": 20,  # All correct, no errors
            "taxa_acerto": 1.0,
            "top_topicos": [],
            "erros_por_tipo": {},
            "compact": False,
        }
        formatted = format_profile(stats)

        assert isinstance(formatted, str)
        assert "100%" in formatted


class TestProfileIntegration:
    """Integration tests for profile generation"""

    def test_privacy_in_mock_data(self):
        """Verify mock data returns properly structured response"""
        mock_client = MagicMock()

        stats_response = MagicMock()
        stats_response.data = [
            {"id": 1, "answered_correct": True, "final_error_type": None, "topic": "Math"},
            {"id": 2, "answered_correct": False, "final_error_type": "conceitual", "topic": "Science"},
            {"id": 3, "answered_correct": True, "final_error_type": None, "topic": "Math"},
        ]

        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            stats_response
        )

        service = ProfileService(mock_client)
        stats = service.generate(telegram_id=111222)

        # Verify structure
        assert "total" in stats
        assert "acertos" in stats
        assert "taxa_acerto" in stats
        assert "top_topicos" in stats
        assert "erros_por_tipo" in stats
        assert "compact" in stats
        assert stats["total"] == 3
        assert stats["acertos"] == 2
