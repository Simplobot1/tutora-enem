"""APKG Builder Service for Anki Deck Generation.

M4-S1: Generate .apkg files from review cards queued for local build.
Uses genanki to create Anki-compatible decks.
"""

from __future__ import annotations

import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import genanki

from app.domain.models import SessionRecord
from app.domain.session_metadata import ReviewCard

logger = logging.getLogger(__name__)


class ApkgBuilderService:
    """Generate .apkg files from review cards."""

    def __init__(self, output_dir: str | None = None) -> None:
        """Initialize builder with optional output directory.

        Args:
            output_dir: Directory to save .apkg files. If None, uses /tmp.
        """
        self.output_dir = output_dir or tempfile.gettempdir()
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def build_apkg_from_session(self, session: SessionRecord) -> str | None:
        """Build .apkg file from session's review_card.

        Args:
            session: SessionRecord with review_card

        Returns:
            Path to generated .apkg file, or None if no review_card
        """
        if session.metadata is None or not hasattr(session.metadata, "review_card"):
            logger.warning(f"session={session.session_id} has no review_card")
            return None

        review_card = session.metadata.review_card
        if not review_card or not review_card.review_card_id:
            logger.warning(f"session={session.session_id} has empty review_card")
            return None

        return self._build_deck(session, review_card)

    def _build_deck(self, session: SessionRecord, review_card: ReviewCard) -> str:
        """Build and save an Anki deck (.apkg file).

        Args:
            session: SessionRecord for metadata
            review_card: ReviewCard with front/back content

        Returns:
            Path to saved .apkg file
        """
        # Create deck with stable ID (deterministic from session_id)
        deck_id = self._hash_to_deck_id(session.session_id or "default")
        deck = genanki.Deck(deck_id, "Tutora ENEM - Revisão")

        # Create note model
        model = genanki.Model(
            deck_id + 1,  # Model ID must be unique
            "Tutora ENEM Model",
            fields=[
                {"name": "Front"},
                {"name": "Back"},
                {"name": "Subject"},
                {"name": "Topic"},
            ],
            templates=[
                {
                    "name": "Card",
                    "qfmt": "{{Front}}",
                    "afmt": "{{FrontSide}}<hr id=answer>{{Back}}<br><small>{{Subject}} - {{Topic}}</small>",
                }
            ],
        )

        # Extract subject/topic from review card front (if available)
        subject = self._extract_subject(review_card.front)
        topic = self._extract_topic(review_card.front)

        # Create note
        note = genanki.Note(
            model=model,
            fields=[
                review_card.front,
                review_card.back,
                subject,
                topic,
            ],
        )
        deck.add_note(note)

        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tutora_{session.session_id}_{timestamp}.apkg"
        filepath = str(Path(self.output_dir) / filename)

        deck.write_to_file(filepath)
        logger.info(f"built apkg={filepath} for session={session.session_id}")

        return filepath

    def _hash_to_deck_id(self, session_id: str) -> int:
        """Convert session_id to stable deck ID (positive integer).

        Uses simple hash to ensure same session always gets same ID.
        """
        return abs(hash(session_id)) % (2**31 - 1) + 1

    def _extract_subject(self, front: str) -> str:
        """Extract subject from review card front (e.g. '📝 Biologia - ...')."""
        if " - " in front:
            parts = front.split(" - ")
            if len(parts) >= 2:
                subject = parts[0].replace("📝", "").strip()
                return subject
        return "Tutora ENEM"

    def _extract_topic(self, front: str) -> str:
        """Extract topic from review card front."""
        if " - " in front:
            parts = front.split(" - ")
            if len(parts) >= 2:
                # Extract only the topic part (before newline)
                topic = parts[1].split("\n")[0].strip()
                return topic[:100]  # Limit to 100 chars
        return "Revisão"


class ApkgBuildResult:
    """Result of apkg build operation."""

    def __init__(
        self,
        session_id: str,
        success: bool,
        apkg_path: str | None = None,
        error: str | None = None,
    ) -> None:
        self.session_id = session_id
        self.success = success
        self.apkg_path = apkg_path
        self.error = error

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/storage."""
        return {
            "session_id": self.session_id,
            "success": self.success,
            "apkg_path": self.apkg_path,
            "error": self.error,
        }
