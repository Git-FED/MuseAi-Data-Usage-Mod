"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .engine import EvaluationError, evaluate


def load_json(path: str) -> Any:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"cannot read valid JSON from {path}: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="token-moderation", description="Evaluate a manual token usage pull against an approved daily cut.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    evaluate_parser = subparsers.add_parser("evaluate", help="evaluate a manual pull")
    evaluate_parser.add_argument("--date", required=True, help="date to evaluate (YYYY-MM-DD)")
    evaluate_parser.add_argument("--cuts", required=True, help="path to approved daily cuts JSON")
    evaluate_parser.add_argument("--pull", required=True, help="path to manual pull JSON")
    evaluate_parser.add_argument("--policy", required=True, help="path to policy JSON")
    args = parser.parse_args(argv)

    try:
        result = evaluate(
            args.date,
            load_json(args.cuts),
            load_json(args.pull),
            load_json(args.policy),
        )
    except EvaluationError as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
