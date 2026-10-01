"""Offline publication gate. Vendor this file into each service's scripts/ directory."""

from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

import jsonschema


def reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number: {value}")


def validate_feed(feed: dict, schema: dict, service: str, now: dt.datetime | None = None) -> None:
    """Check the stable envelope, not signal economics or point-in-time certification."""
    json.dumps(feed, allow_nan=False)
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(feed)
    if feed["service"] != service:
        raise ValueError("Feed service does not match repository identity")
    ttl = feed["ttl_hours"]
    if isinstance(ttl, bool) or not math.isfinite(ttl) or ttl <= 0:
        raise ValueError("ttl_hours must be finite and positive")
    stamp = dt.datetime.fromisoformat(feed["generated_at"].replace("Z", "+00:00"))
    current = now or dt.datetime.now(dt.timezone.utc)
    if stamp.tzinfo is None or stamp.year < 2000:
        raise ValueError("generated_at must be an aware, non-epoch timestamp")
    age = (current - stamp).total_seconds()
    if age < -300 or age > ttl * 3600:
        raise ValueError("Feed generation time is future-dated or stale")
    if feed["status"] != "active" and not str(feed.get("notes", "")).strip():
        raise ValueError("Partial/unavailable feeds must explain their status")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    feed = json.loads((root / "out" / f"{root.name}.json").read_text(encoding="utf-8"), parse_constant=reject_constant)
    schema = json.loads((root / "schema.json").read_text(encoding="utf-8"))
    validate_feed(feed, schema, root.name)
    print(f"[{root.name}] feed contract passed; status={feed['status']}")


if __name__ == "__main__":
    main()
