"""Ingest: House + Senate financial-disclosure datasets (free, keyless).

Source-specific parsing lives here; the resulting normalized transaction dicts are what
compute.py operates on. Everything is defensive: on network/parse failure we return an
empty list so build_feed emits a graceful status.
"""
from __future__ import annotations

from typing import Any, Dict, List

import requests

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
}


def _fetch_json(url: str, timeout: float = 20.0) -> Any:
    try:
        r = requests.get(url, timeout=timeout, headers=_HEADERS)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except Exception:
        return None


def _side(raw_type: str) -> str | None:
    t = (raw_type or "").strip().lower()
    if t.startswith("purchase") or t == "buy":
        return "buy"
    if t.startswith("sale") or t == "sell":
        return "sell"
    return None  # exchange / receive / unknown -> ignore


def _clean_ticker(t: Any) -> str | None:
    s = str(t or "").strip().upper()
    if not s or s in {"--", "N/A", "NONE", "<BR>"} or len(s) > 6:
        return None
    return s


def normalize_house(rec: Dict[str, Any]) -> Dict[str, Any] | None:
    ticker = _clean_ticker(rec.get("ticker"))
    side = _side(rec.get("type"))
    if not ticker or not side:
        return None
    return {
        "ticker": ticker,
        "member": rec.get("representative") or rec.get("member") or "Unknown",
        "chamber": "House",
        "side": side,
        "amount_range": rec.get("amount"),
        "traded_at": rec.get("transaction_date"),
        "disclosed_at": rec.get("disclosure_date"),
    }


def normalize_senate(rec: Dict[str, Any]) -> Dict[str, Any] | None:
    ticker = _clean_ticker(rec.get("ticker"))
    side = _side(rec.get("type"))
    if not ticker or not side:
        return None
    return {
        "ticker": ticker,
        "member": rec.get("senator") or rec.get("member") or "Unknown",
        "chamber": "Senate",
        "side": side,
        "amount_range": rec.get("amount"),
        "traded_at": rec.get("transaction_date"),
        "disclosed_at": rec.get("disclosure_date"),
    }


def gather(cfg: Dict[str, Any]) -> Dict[str, Any]:
    txns: List[Dict[str, Any]] = []
    house = _fetch_json(cfg["house_url"])
    if isinstance(house, list):
        txns += [n for n in (normalize_house(r) for r in house if isinstance(r, dict)) if n]
    senate = _fetch_json(cfg["senate_url"])
    if isinstance(senate, list):
        txns += [n for n in (normalize_senate(r) for r in senate if isinstance(r, dict)) if n]
    return {"txns": txns}
