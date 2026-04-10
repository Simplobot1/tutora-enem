from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a Tutora session placeholder.")
    parser.add_argument("--telegram-id", required=True, type=int)
    args = parser.parse_args()
    print(f"inspect_session placeholder for telegram_id={args.telegram_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

