"""Pure evaluation logic for approved daily cuts and manual usage pulls."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


class EvaluationError(ValueError):
    """Raised when the approval, policy, or pull envelope is invalid."""


def _parse_iso_date(value: Any, label: str) -> date:
    if not isinstance(value, str):
        raise EvaluationError(f"{label} must be an ISO date string (YYYY-MM-DD)")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise EvaluationError(f"{label} must be an ISO date string (YYYY-MM-DD)") from exc
    if parsed.isoformat() != value:
        raise EvaluationError(f"{label} must use YYYY-MM-DD format")
    return parsed


def _aware_datetime(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise EvaluationError(f"{label} must be an ISO-8601 timestamp with timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvaluationError(f"{label} must be an ISO-8601 timestamp with timezone") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise EvaluationError(f"{label} must include a timezone offset")
    return parsed


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise EvaluationError(f"{label} must be a positive integer")
    return value


def validate_approved_cut(cuts_doc: dict[str, Any], target_date: date) -> dict[str, Any]:
    """Return a valid approved cut or fail closed."""
    if not isinstance(cuts_doc, dict) or not isinstance(cuts_doc.get("daily_cuts"), dict):
        raise EvaluationError("cuts file must contain a daily_cuts object")
    cut = cuts_doc["daily_cuts"].get(target_date.isoformat())
    if not isinstance(cut, dict):
        raise EvaluationError(f"no daily cut is registered for {target_date.isoformat()}")
    if cut.get("status") != "APPROVED":
        raise EvaluationError(f"daily cut for {target_date.isoformat()} is not APPROVED")
    _positive_int(cut.get("limit_tokens"), "approved limit_tokens")
    if not isinstance(cut.get("approved_by"), str) or not cut["approved_by"].strip():
        raise EvaluationError("approved cut must include approved_by")
    _aware_datetime(cut.get("approved_at"), "approved_at")
    return cut


def evaluate(
    target_date_text: str,
    cuts_doc: dict[str, Any],
    pull_doc: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate a manual pull, counting only valid VERIFIED records for target date."""
    target_date = _parse_iso_date(target_date_text, "target date")
    cut = validate_approved_cut(cuts_doc, target_date)

    if not isinstance(policy, dict):
        raise EvaluationError("policy must be a JSON object")
    if policy.get("automation_enabled") is not False:
        raise EvaluationError("automation_enabled must be false")
    if policy.get("pull_mode_required") != "MANUAL":
        raise EvaluationError("policy must require MANUAL pulls")
    verified_label = policy.get("verification_required")
    if verified_label != "VERIFIED":
        raise EvaluationError("policy must require exact VERIFIED status")
    thresholds = policy.get("thresholds")
    if not isinstance(thresholds, list):
        raise EvaluationError("policy thresholds must be a list")
    normalized_thresholds = []
    last_percent = 0
    for item in thresholds:
        if not isinstance(item, dict):
            raise EvaluationError("each threshold must be an object")
        percent = item.get("percent")
        if isinstance(percent, bool) or not isinstance(percent, int) or not (1 <= percent <= 99):
            raise EvaluationError("threshold percent must be an integer from 1 to 99")
        if percent <= last_percent:
            raise EvaluationError("thresholds must be in strictly ascending order")
        if not isinstance(item.get("signal"), str) or not item["signal"].strip():
            raise EvaluationError("each threshold must have a signal")
        if not isinstance(item.get("action"), str):
            raise EvaluationError("each threshold must have an action")
        normalized_thresholds.append(item)
        last_percent = percent
    cap_percent = policy.get("cap_percent", 100)
    if isinstance(cap_percent, bool) or not isinstance(cap_percent, int) or cap_percent <= last_percent:
        raise EvaluationError("cap_percent must be an integer above all threshold percentages")
    cap_signal = policy.get("cap_signal", "CAP_REACHED")
    if not isinstance(cap_signal, str) or not cap_signal.strip():
        raise EvaluationError("cap_signal must be a non-empty string")

    if not isinstance(pull_doc, dict):
        raise EvaluationError("pull file must be a JSON object")
    if pull_doc.get("pull_mode") != "MANUAL":
        raise EvaluationError("pull_mode must be exactly MANUAL; automatic pulls are not accepted")
    _aware_datetime(pull_doc.get("pulled_at"), "pulled_at")
    records = pull_doc.get("records")
    if not isinstance(records, list):
        raise EvaluationError("manual pull must contain a records array")

    included = []
    excluded = []
    seen_ids: set[str] = set()
    total = 0
    for index, record in enumerate(records):
        label = f"records[{index}]"
        if not isinstance(record, dict):
            excluded.append({"index": index, "reason": "record is not an object"})
            continue
        record_id = record.get("record_id")
        if not isinstance(record_id, str) or not record_id.strip():
            excluded.append({"index": index, "reason": "missing or invalid record_id"})
            continue
        if record_id in seen_ids:
            excluded.append({"index": index, "record_id": record_id, "reason": "duplicate record_id"})
            continue
        seen_ids.add(record_id)
        try:
            row_date = _parse_iso_date(record.get("date"), f"{label}.date")
        except EvaluationError as exc:
            excluded.append({"index": index, "record_id": record_id, "reason": str(exc)})
            continue
        if row_date != target_date:
            excluded.append({"index": index, "record_id": record_id, "reason": "date does not match evaluation date"})
            continue
        if record.get("verification") != verified_label:
            excluded.append({"index": index, "record_id": record_id, "reason": "verification is not exactly VERIFIED"})
            continue
        tokens = record.get("tokens")
        if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
            excluded.append({"index": index, "record_id": record_id, "reason": "tokens must be a non-negative integer"})
            continue
        included.append({"record_id": record_id, "tokens": tokens})
        total += tokens

    limit = cut["limit_tokens"]
    percent_used = (total * 100.0) / limit
    signals = [
        {"percent": item["percent"], "signal": item["signal"], "action": item["action"]}
        for item in normalized_thresholds
        if percent_used >= item["percent"]
    ]
    if percent_used >= cap_percent:
        signals.append({"percent": cap_percent, "signal": cap_signal,
                        "action": "Approved daily cut reached or exceeded; human decision required."})

    return {
        "date": target_date.isoformat(),
        "pull_mode": "MANUAL",
        "approved_cut": {
            "limit_tokens": limit,
            "status": cut["status"],
            "approved_by": cut["approved_by"],
            "approved_at": cut["approved_at"],
        },
        "counting_rule": "Only exact VERIFIED records for the requested date are counted.",
        "verified_total_tokens": total,
        "percent_used": round(percent_used, 2),
        "remaining_tokens": limit - total,
        "signals": signals,
        "included_records": included,
        "excluded_records": excluded,
        "automated_action_taken": False,
    }
