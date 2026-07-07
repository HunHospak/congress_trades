"""Pure computation for congress_trades. No I/O, unit-testable."""
from __future__ import annotations

import datetime as dt
from collections import Counter
from typing import Any, Dict, List, Optional


def _parse_date(s: Any) -> Optional[dt.date]:
    if not s:
        return None
    txt = str(s).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return dt.datetime.strptime(txt, fmt).date()
        except ValueError:
            continue
    return None


def build_boards(txns: List[Dict[str, Any]], cfg: Dict[str, Any], today: dt.date) -> Dict[str, Any]:
    lookback = int(cfg.get("lookback_days", 45))
    top_n = int(cfg.get("top_n", 30))
    cutoff = today - dt.timedelta(days=lookback)

    recent: List[Dict[str, Any]] = []
    for t in txns:
        d = _parse_date(t.get("disclosed_at")) or _parse_date(t.get("traded_at"))
        if d is None or d < cutoff or d > today:
            continue
        row = dict(t)
        row["_sort"] = d.isoformat()
        recent.append(row)

    recent.sort(key=lambda r: r["_sort"], reverse=True)

    counts = Counter(r["ticker"] for r in recent)
    most_traded = [
        {"ticker": tk, "trades": n,
         "buys": sum(1 for r in recent if r["ticker"] == tk and r["side"] == "buy"),
         "sells": sum(1 for r in recent if r["ticker"] == tk and r["side"] == "sell")}
        for tk, n in counts.most_common(top_n)
    ]

    by_ticker: Dict[str, Dict[str, Any]] = {}
    for tk, n in counts.items():
        buys = sum(1 for r in recent if r["ticker"] == tk and r["side"] == "buy")
        by_ticker[tk] = {"trades": n, "buys": buys, "sells": n - buys}

    recent_out = [
        {k: r.get(k) for k in ("ticker", "member", "chamber", "side", "amount_range", "traded_at", "disclosed_at")}
        for r in recent[:top_n]
    ]

    # Most active members (by trade count) with their buy-bias in the window.
    member_stats: Dict[str, Dict[str, Any]] = {}
    for r in recent:
        m = r.get("member") or "Unknown"
        s = member_stats.setdefault(m, {"member": m, "chamber": r.get("chamber"), "trades": 0, "buys": 0, "sells": 0})
        s["trades"] += 1
        s["buys" if r["side"] == "buy" else "sells"] += 1
    top_members = sorted(member_stats.values(), key=lambda s: -s["trades"])[:top_n]
    for s in top_members:
        tot = s["buys"] + s["sells"]
        s["buy_bias"] = round(s["buys"] / tot, 2) if tot else None

    if not recent:
        status, notes = ("unavailable", "No congressional trades in the lookback window.") if not txns \
            else ("partial", "No disclosures within the lookback window (source reachable).")
    else:
        status, notes = "active", None

    return {
        "as_of": today.isoformat(),
        "lookback_days": lookback,
        "recent_count": len(recent),
        "recent": recent_out,
        "most_traded": most_traded,
        "top_members": top_members,
        "by_ticker": by_ticker,
        "_status": status,
        "_notes": notes,
    }
