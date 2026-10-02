"""Orchestration: ingest -> compute -> validate(schema) -> write out/."""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from providers import gather
from compute import build_boards


def load_config() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def load_schema() -> dict:
    return json.loads((ROOT / "schema.json").read_text(encoding="utf-8"))


def build(cfg: dict) -> dict:
    raw = gather(cfg)
    boards = build_boards(raw.get("txns", []), cfg, dt.datetime.now(dt.timezone.utc).date())
    status = boards.pop("_status")
    notes = boards.pop("_notes", None)
    if raw.get("coverage"):
        boards["source_coverage"] = raw["coverage"]
        boards["source_errors"] = raw.get("source_errors", [])
        coverage = raw["coverage"]
        notes = (
            f"Partial House-only sample: {coverage['reports_with_supported_stock_rows']}/"
            f"{coverage['reports_attempted']} reports contained supported stock rows; "
            "Senate/scanned or unsupported rows excluded. Amendments may repeat transactions."
        )
        status = "partial" if raw.get("txns") else "unavailable"
    boards["disclaimer"] = (
        "Congressional financial disclosures (public record). Informational only, not investment advice."
    )

    feed = {
        "service": cfg["service"],
        "schema_version": str(cfg["schema_version"]),
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "ttl_hours": cfg["ttl_hours"],
        "data": boards,
    }
    if notes:
        feed["notes"] = notes
    return feed


def main() -> None:
    cfg = load_config()
    feed = build(cfg)
    jsonschema.validate(feed, load_schema())
    out = ROOT / "out"
    (out / "history").mkdir(parents=True, exist_ok=True)
    payload = json.dumps(feed, indent=2, allow_nan=False)
    (out / "congress_trades.json").write_text(payload, encoding="utf-8")
    (out / "history" / f"{feed['data']['as_of']}.json").write_text(payload, encoding="utf-8")
    print(f"[congress_trades] status={feed['status']} recent={feed['data']['recent_count']}")


if __name__ == "__main__":
    main()
