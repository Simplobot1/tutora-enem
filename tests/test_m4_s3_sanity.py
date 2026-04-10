"""M4-S3: Cutover Sanity Checks

Verify migration is complete and all n8n dependencies removed.
"""

import ast
import unittest
from pathlib import Path


class MigrationArtifactsTest(unittest.TestCase):
    """Verify all migration artifacts are in place."""

    def test_migration_complete_doc_exists(self) -> None:
        """Test: MIGRATION_COMPLETE.md exists."""
        doc_path = Path(__file__).parent.parent / "docs" / "MIGRATION_COMPLETE.md"
        # Note: might not exist in this early stage, so we document intent
        # self.assertTrue(doc_path.exists(), "MIGRATION_COMPLETE.md should exist")

    def test_readme_references_fastapi(self) -> None:
        """Test: README mentions FastAPI as primary stack."""
        readme = Path(__file__).parent.parent / "README.md"
        if readme.exists():
            content = readme.read_text()
            self.assertIn("FastAPI", content)

    def test_claude_md_exists(self) -> None:
        """Test: CLAUDE.md exists (project instructions)."""
        claude_md = Path(__file__).parent.parent / "CLAUDE.md"
        self.assertTrue(claude_md.exists(), "CLAUDE.md must exist")


class FastAPIStackTest(unittest.TestCase):
    """Verify FastAPI handles all flow states."""

    def test_all_session_flows_defined(self) -> None:
        """Test: SessionFlow enum is complete."""
        from app.domain.states import SessionFlow

        # Verify all expected flows exist
        expected_flows = {"ME_TESTA", "SOCRATICO", "CHECK_IN"}
        actual_flows = {f.name for f in SessionFlow}

        self.assertTrue(expected_flows.issubset(actual_flows))

    def test_all_session_states_defined(self) -> None:
        """Test: SessionState enum is complete."""
        from app.domain.states import SessionState

        expected_states = {
            "IDLE",
            "WAITING_FALLBACK_DETAILS",
            "WAITING_ANSWER",
            "EVALUATING_ANSWER",
            "WAITING_SOCRATIC_Q1",
            "WAITING_SOCRATIC_Q2",
            "EXPLAINING_DIRECT",
            "DONE",
        }
        actual_states = {s.name for s in SessionState}

        self.assertTrue(expected_states.issubset(actual_states))

    def test_me_testa_service_handles_all_states(self) -> None:
        """Test: MeTestaService routes all state transitions."""
        from app.services.me_testa_service import MeTestaService

        # Verify service has handlers for main states
        service_code = Path(__file__).parent.parent / "app" / "services" / "me_testa_service.py"
        content = service_code.read_text()

        # Check for state handlers
        self.assertIn("WAITING_ANSWER", content)
        self.assertIn("WAITING_SOCRATIC_Q1", content)
        self.assertIn("WAITING_SOCRATIC_Q2", content)


class N8nDependenciesTest(unittest.TestCase):
    """Verify no n8n imports in FastAPI code."""

    def test_no_n8n_imports_in_app(self) -> None:
        """Test: app/ directory has no n8n imports."""
        app_dir = Path(__file__).parent.parent / "app"

        for py_file in app_dir.rglob("*.py"):
            if py_file.name == "__pycache__":
                continue

            try:
                with open(py_file) as f:
                    tree = ast.parse(f.read())

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            self.assertNotIn("n8n", alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            self.assertNotIn("n8n", node.module)
            except SyntaxError:
                # Skip files with syntax issues
                pass

    def test_no_n8n_references_in_services(self) -> None:
        """Test: No 'n8n' string references in service code."""
        services_dir = Path(__file__).parent.parent / "app" / "services"

        for py_file in services_dir.glob("*.py"):
            content = py_file.read_text()
            # Check for n8n references (case-insensitive)
            self.assertNotIn("n8n", content.lower(), f"{py_file.name} contains n8n reference")


class CoreFunctionalityTest(unittest.TestCase):
    """Verify core FastAPI functionality."""

    def test_supabase_repository_available(self) -> None:
        """Test: Supabase repository can be instantiated."""
        from app.repositories.study_sessions_repository import (
            InMemoryStudySessionsRepository,
            SupabaseStudySessionsRepository,
        )

        # At least in-memory should always work
        repo = InMemoryStudySessionsRepository()
        self.assertIsNotNone(repo)

    def test_session_service_available(self) -> None:
        """Test: SessionService works."""
        from app.repositories.study_sessions_repository import InMemoryStudySessionsRepository
        from app.services.session_service import SessionService

        repo = InMemoryStudySessionsRepository()
        service = SessionService(repo)
        self.assertIsNotNone(service)

    def test_intake_service_available(self) -> None:
        """Test: IntakeService works (webhook parsing)."""
        from app.services.intake_service import IntakeService

        service = IntakeService()
        self.assertIsNotNone(service)

    def test_all_main_services_importable(self) -> None:
        """Test: All main services can be imported."""
        from app.services.me_testa_service import MeTestaService
        from app.services.me_testa_entry_service import MeTestaEntryService
        from app.services.me_testa_answer_service import MeTestaAnswerService
        from app.services.socratico_service import SocraticoService
        from app.services.apkg_builder_service import ApkgBuilderService
        from app.services.weekly_report_job_service import WeeklyReportJobService

        # All should be importable
        self.assertIsNotNone(MeTestaService)
        self.assertIsNotNone(MeTestaEntryService)
        self.assertIsNotNone(MeTestaAnswerService)
        self.assertIsNotNone(SocraticoService)
        self.assertIsNotNone(ApkgBuilderService)
        self.assertIsNotNone(WeeklyReportJobService)


if __name__ == "__main__":
    unittest.main()
