"""Generate a ready-to-post social snippet from the latest feed."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    feed = json.loads((ROOT / "out" / "congress_trades.json").read_text(encoding="utf-8"))
    d = feed["data"]
    lines = [f"Congress trades — last {d.get('lookback_days')}d ({d.get('as_of')})"]
    top = d.get("most_traded", [])[:5]
    if top:
        lines.append("Most-traded by members:")
        for x in top:
            lines.append(f"  {x['ticker']}  {x['trades']} trades  ({x['buys']}B/{x['sells']}S)")
    else:
        lines.append("No recent disclosures.")
    lines.append("Public disclosures · not investment advice · arkenlabs.eu")
    text = "\n".join(lines)
    (ROOT / "out" / "post.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
