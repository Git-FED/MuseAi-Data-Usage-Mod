import unittest

from token_moderation.engine import EvaluationError, evaluate


DATE = "2026-10-27"


def cuts(limit=100_000, status="APPROVED"):
    return {"daily_cuts": {DATE: {
        "limit_tokens": limit,
        "status": status,
        "approved_by": "test-operator",
        "approved_at": "2026-10-27T09:00:00-04:00",
    }}}


def policy():
    return {
        "thresholds": [
            {"percent": 25, "signal": "WATCH", "action": "monitor"},
            {"percent": 50, "signal": "REVIEW", "action": "review"},
            {"percent": 75, "signal": "PAUSE_NONESSENTIAL", "action": "pause nonessential"},
        ],
        "cap_percent": 100,
        "cap_signal": "CAP_REACHED",
        "pull_mode_required": "MANUAL",
        "verification_required": "VERIFIED",
        "automation_enabled": False,
    }


def pull(records, mode="MANUAL"):
    return {"pull_mode": mode, "pulled_at": "2026-10-27T12:00:00-04:00", "records": records}


class EvaluationTests(unittest.TestCase):
    def test_only_verified_matching_date_counts(self):
        result = evaluate(DATE, cuts(), pull([
            {"record_id": "a", "date": DATE, "tokens": 30_000, "verification": "VERIFIED"},
            {"record_id": "b", "date": DATE, "tokens": 90_000, "verification": "PENDING"},
            {"record_id": "c", "date": "2026-10-26", "tokens": 40_000, "verification": "VERIFIED"},
        ]), policy())
        self.assertEqual(result["verified_total_tokens"], 30_000)
        self.assertEqual([x["signal"] for x in result["signals"]], ["WATCH"])
        self.assertEqual(len(result["excluded_records"]), 2)
        self.assertFalse(result["automated_action_taken"])

    def test_50_percent_triggers_25_and_50(self):
        result = evaluate(DATE, cuts(), pull([
            {"record_id": "a", "date": DATE, "tokens": 50_000, "verification": "VERIFIED"},
        ]), policy())
        self.assertEqual([x["signal"] for x in result["signals"]], ["WATCH", "REVIEW"])

    def test_75_percent_triggers_escalation(self):
        result = evaluate(DATE, cuts(), pull([
            {"record_id": "a", "date": DATE, "tokens": 75_000, "verification": "VERIFIED"},
        ]), policy())
        self.assertEqual([x["signal"] for x in result["signals"]], ["WATCH", "REVIEW", "PAUSE_NONESSENTIAL"])

    def test_at_or_over_cap_reports_cap_reached(self):
        result = evaluate(DATE, cuts(), pull([
            {"record_id": "a", "date": DATE, "tokens": 101_000, "verification": "VERIFIED"},
        ]), policy())
        self.assertEqual(result["signals"][-1]["signal"], "CAP_REACHED")
        self.assertEqual(result["remaining_tokens"], -1_000)

    def test_missing_or_unapproved_cut_fails_closed(self):
        with self.assertRaisesRegex(EvaluationError, "not APPROVED"):
            evaluate(DATE, cuts(status="PENDING"), pull([]), policy())
        with self.assertRaisesRegex(EvaluationError, "no daily cut"):
            evaluate("2026-10-28", cuts(), pull([]), policy())

    def test_non_manual_pull_is_rejected(self):
        with self.assertRaisesRegex(EvaluationError, "exactly MANUAL"):
            evaluate(DATE, cuts(), pull([], mode="API"), policy())

    def test_naive_timestamp_is_rejected(self):
        bad_pull = pull([])
        bad_pull["pulled_at"] = "2026-10-27T12:00:00"
        with self.assertRaisesRegex(EvaluationError, "timezone"):
            evaluate(DATE, cuts(), bad_pull, policy())

    def test_duplicate_record_id_counts_once(self):
        row = {"record_id": "same", "date": DATE, "tokens": 10_000, "verification": "VERIFIED"}
        result = evaluate(DATE, cuts(), pull([row, row]), policy())
        self.assertEqual(result["verified_total_tokens"], 10_000)
        self.assertEqual(result["excluded_records"][0]["reason"], "duplicate record_id")


if __name__ == "__main__":
    unittest.main()
