# Token Usage Moderation

<img width="1328" height="727" alt="Screenshot 2026-10-27 205824" src="https://github.com/user-attachments/assets/a71b8c1f-b8a4-4281-94d2-c4c6152a2c44" />

A small, offline Python tool for evaluating manually supplied token-usage pulls against explicitly approved daily token cuts.

The static landing page is in `site/`. See [DEPLOYMENT.md](DEPLOYMENT.md) for Cloudflare Workers, Cloudflare Pages, and GitHub Pages publishing options.

## Protocol

Only records for the requested date with `verification` set exactly to `VERIFIED` are counted, and only from a pull document whose `pull_mode` is exactly `MANUAL`. Unverified, malformed, and out-of-date records are excluded and reported. Automatic/API pulls are rejected.

Thresholds are percentages of the approved daily cut:

| Usage reached | Signal | Suggested response |
| ---: | --- | --- |
| 25% | `WATCH` | Log and monitor; no automatic change. |
| 50% | `REVIEW` | Review the remaining allowance. |
| 75% | `PAUSE_NONESSENTIAL` | Pause non-essential work pending a human decision. |
| 100% | `CAP_REACHED` | The approved daily cut has been reached; do not authorize usage beyond it without a human decision. |

These are reporting signals, not automated controls. The program does not connect to services, fetch usage, change quotas, block requests, or approve cuts.

## Requirements

Python 3.10 or newer; no third-party packages.

## Add an approved daily cut

Edit `config/daily_cuts.json` to add a date entry. Replace the example values below with values actually approved through your process:

```json
{
  "daily_cuts": {
    "2026-10-27": {
      "limit_tokens": 100000,
      "status": "APPROVED",
      "approved_by": "operator@example.com",
      "approved_at": "2026-10-27T09:00:00-04:00",
      "note": "Illustrative only; replace before use"
    }
  }
}
```

The starter `config/daily_cuts.json` is intentionally empty: no limit or approval has been invented. A day without a valid `APPROVED` entry cannot be evaluated.

## Prepare a manual pull

Create a JSON file like `examples/manual-pull.example.json`:

```json
{
  "pull_mode": "MANUAL",
  "pulled_at": "2026-10-27T12:00:00-04:00",
  "records": [
    {
      "record_id": "pull-001",
      "date": "2026-10-27",
      "tokens": 12000,
      "verification": "VERIFIED",
      "source_note": "Copied from the approved usage report"
    }
  ]
}
```

Unverified rows can be included for review but are excluded from the total. Keep `record_id` unique within each pull. Nothing is fetched automatically.

## Run an evaluation

From the project directory:

```bash
PYTHONPATH=src python -m token_moderation.cli evaluate \
  --date 2026-10-27 \
  --cuts config/daily_cuts.json \
  --pull examples/manual-pull.example.json \
  --policy config/policy.json
```

The result is JSON printed to the terminal with the verified total, percentage, triggered signals, and excluded-row reasons. The checked-in cuts file has no approved dates, so add an approved entry before evaluation.

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Project files

- `config/policy.json` — thresholds and the manual/verified-only rules.
- `config/daily_cuts.json` — approved daily cut registry (empty starter).
- `examples/manual-pull.example.json` — sample pull with one verified and one unverified row.
- `src/token_moderation/` — evaluation engine and CLI.
- `tests/` — standard-library unit tests.
