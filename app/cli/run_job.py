from __future__ import annotations

import argparse

from app.jobs import weekly_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a named Tutora job.")
    parser.add_argument("job", choices=["weekly_report"])
    args = parser.parse_args()

    if args.job == "weekly_report":
        return weekly_report.main()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

