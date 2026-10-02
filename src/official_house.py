"""Bounded, measured public House PTR ingestion; no OCR or guessed tickers.

Only explicitly ticker-tagged stock rows with transaction and notification dates
are parsed. Coverage is always partial: latest N reports, House only, and scanned
or unsupported layouts are excluded. Trade rows link to their official PDF.
"""

from __future__ import annotations

import datetime as dt
import io
import logging
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

import requests
from pypdf import PdfReader
from pypdf.errors import PyPdfError

_LOG = logging.getLogger(__name__)
_HEADERS = {"User-Agent": "ArkenLabs-congress-disclosures/1.0 (+https://arkenlabs.eu)"}
_MAX_BYTES = 8_000_000
_ROW = re.compile(r"\b(P|S(?:\s*\(partial\))?)\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(\$[\d,]+[^\n]*)")
_TICKER = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,7})\)\s*\[ST\]")


def parse_index(content: bytes, today: dt.date, lookback_days: int) -> list[dict[str, str]]:
    """Read ZIP members in memory (never extract paths); keep dated PTR metadata."""
    cutoff = today - dt.timedelta(days=lookback_days)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        member = next(n for n in archive.namelist() if n.lower().endswith(".xml"))
        if archive.getinfo(member).file_size > _MAX_BYTES:
            raise ValueError("House index exceeds size budget")
        root = ET.fromstring(archive.read(member))
    out = []
    for item in root:
        row = {child.tag: (child.text or "").strip() for child in item}
        if row.get("FilingType") != "P":
            continue
        try:
            filed = dt.datetime.strptime(row["FilingDate"], "%m/%d/%Y").date()
        except (KeyError, ValueError):
            continue
        if not cutoff <= filed <= today or not re.fullmatch(r"\d+", row.get("DocID", "")):
            continue
        if not re.fullmatch(r"20\d{2}", row.get("Year", "")):
            continue
        row["disclosed_at"] = filed.isoformat()
        out.append(row)
    return sorted(out, key=lambda row: (row["disclosed_at"], row["DocID"]), reverse=True)


def parse_layout(text: str, report: dict[str, str], source_url: str) -> list[dict[str, Any]]:
    """Join wrapped asset cells, never use a ticker from the next transaction row."""
    lines = text.splitlines()
    rows = []
    for index, line in enumerate(lines):
        match = _ROW.search(line)
        if not match:
            continue
        asset = [line[: match.start()]]
        for following in lines[index + 1 : index + 4]:
            if not following.strip() or _ROW.search(following) or following.lstrip().startswith("ID "):
                break
            # Only the asset cell, not the amount / date columns.
            asset.append(following[: match.start()])
        ticker = _TICKER.search(" ".join(asset))
        if not ticker:
            continue
        try:
            traded = dt.datetime.strptime(match[2], "%m/%d/%Y").date()
            notified = dt.datetime.strptime(match[3], "%m/%d/%Y").date()
            disclosed = dt.date.fromisoformat(report["disclosed_at"])
        except ValueError:
            continue
        if traded > disclosed or notified > disclosed or notified < traded:
            continue
        amount = match[4].strip()
        if amount.endswith("-") and index + 1 < len(lines):
            tail = lines[index + 1][match.start() :].strip()
            if re.fullmatch(r"\$[\d,]+", tail):
                amount += " " + tail
        rows.append(
            {
                "ticker": ticker[1],
                "member": " ".join(filter(None, [report.get("First"), report.get("Last")])),
                "chamber": "House",
                "side": "buy" if match[1] == "P" else "sell",
                "amount_range": amount,
                "traded_at": traded.isoformat(),
                "disclosed_at": disclosed.isoformat(),
                "source_url": source_url,
                "source_row": index + 1,
            }
        )
    return rows


def _download(url: str, timeout: float) -> bytes:
    response = requests.get(url, headers=_HEADERS, timeout=timeout, stream=True)
    try:
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            content.extend(chunk)
            if len(content) > _MAX_BYTES:
                raise ValueError("Official disclosure exceeds size budget")
        return bytes(content)
    finally:
        response.close()


def gather(cfg: dict[str, Any], today: dt.date | None = None) -> dict[str, Any]:
    today = today or dt.datetime.now(dt.timezone.utc).date()
    timeout = float(cfg.get("source_timeout_seconds", 20))
    errors = []
    reports = []
    # Prior year's index is needed only when the lookback crosses New Year.
    cutoff = today - dt.timedelta(days=int(cfg.get("lookback_days", 45)))
    for year in sorted({today.year, cutoff.year}, reverse=True):
        try:
            content = _download(cfg["house_index_url"].format(year=year), timeout)
            reports.extend(parse_index(content, today, int(cfg.get("lookback_days", 45))))
        except (requests.RequestException, ValueError, zipfile.BadZipFile, ET.ParseError, StopIteration) as exc:
            _LOG.warning("Official House index failed: %s", type(exc).__name__)
            errors.append("index_unavailable")
    reports.sort(key=lambda row: (row["disclosed_at"], row["DocID"]), reverse=True)
    selected = reports[: max(1, min(50, int(cfg.get("max_house_reports", 20))))]
    transactions = []
    parsed = 0
    for report in selected:
        url = cfg["house_pdf_url"].format(year=report["Year"], doc_id=report["DocID"])
        try:
            pdf = PdfReader(io.BytesIO(_download(url, timeout)))
            text = "\n".join(page.extract_text(extraction_mode="layout") or "" for page in pdf.pages)
            rows = parse_layout(text, report, url)
        except (requests.RequestException, ValueError, OSError, PyPdfError) as exc:
            _LOG.warning("Official House PDF %s failed: %s", report["DocID"], type(exc).__name__)
            errors.append("pdf_unavailable")
            continue
        if rows:
            parsed += 1
            transactions.extend(rows)
        else:
            errors.append("no_supported_stock_rows")
    return {
        "txns": transactions,
        "coverage": {
            "House": "official_public_PTR_PDF_sample",
            "Senate": "unavailable",
            "reports_in_window": len(reports),
            "reports_attempted": len(selected),
            "reports_with_supported_stock_rows": parsed,
            "methodology": "Latest bounded House PTR sample; explicit stock tickers only. Scanned/unsupported rows excluded; amendments may repeat transactions.",
        },
        "source_errors": errors,
    }
