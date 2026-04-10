from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    from supabase import Client, create_client
except Exception:  # pragma: no cover - import safety for local bootstrap
    Client = Any  # type: ignore[assignment]
    create_client = None


@dataclass(slots=True)
class SupabaseClientFactory:
    url: str
    service_role_key: str

    def create(self) -> Client | None:
        if not self.url or not self.service_role_key or create_client is None:
            return None
        return create_client(self.url, self.service_role_key)

