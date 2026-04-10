from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.intake_service import IntakeService


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay a Telegram update fixture.")
    parser.add_argument("--file", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
    event = IntakeService().normalize_update(payload)
    print(json.dumps(event.raw_payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

