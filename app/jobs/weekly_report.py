from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description="Weekly report job placeholder for Tutora.")
    parser.add_argument("--dry-run", action="store_true")
    parser.parse_args()
    print("weekly_report job placeholder")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

