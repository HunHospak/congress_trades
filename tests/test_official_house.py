import datetime as dt
import io
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import official_house as house
import build_feed

REPORT = {"First": "Test", "Last": "Member", "disclosed_at": "2026-09-30", "Year": "2026", "DocID": "123"}
URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/123.pdf"
ROW = "                      Apple Inc. (AAPL) [ST]                  P                  09/01/2026  09/20/2026  $1,001 - $15,000"


def archive(xml):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("2026FD.xml", xml)
    return buf.getvalue()


class OfficialHouseTests(unittest.TestCase):
    def test_only_valid_recent_nonfuture_PTRs(self):
        def item(kind, date, doc):
            return f"<Member><FilingType>{kind}</FilingType><FilingDate>{date}</FilingDate><DocID>{doc}</DocID><Year>2026</Year></Member>"

        xml = (
            "<Root>"
            + item("P", "9/30/2026", "123")
            + item("P", "10/3/2026", "124")
            + item("P", "1/1/2026", "125")
            + item("A", "9/30/2026", "126")
            + item("P", "bad", "127")
            + "</Root>"
        )
        self.assertEqual([r["DocID"] for r in house.parse_index(archive(xml), dt.date(2026, 10, 2), 45)], ["123"])

    def test_measured_row_has_side_dates_and_official_source(self):
        row = house.parse_layout(ROW, REPORT, URL)[0]
        self.assertEqual((row["ticker"], row["side"], row["traded_at"]), ("AAPL", "buy", "2026-09-01"))
        self.assertEqual(row["source_url"], URL)

    def test_wrapped_ticker_and_partial_sale(self):
        text = "                      Apple common stock                     S (partial)        09/01/2026  09/20/2026  $1,001 - $15,000\n                      (AAPL) [ST]"
        self.assertEqual(house.parse_layout(text, REPORT, URL)[0]["side"], "sell")

    def test_no_guessed_tickers_or_future_trades(self):
        self.assertEqual(house.parse_layout(ROW.replace("(AAPL) [ST]", "Apple bond [GS]"), REPORT, URL), [])
        self.assertEqual(house.parse_layout(ROW.replace("09/01/2026", "10/01/2026"), REPORT, URL), [])
        unknown = ROW.replace("(AAPL) [ST]", "Unknown stock")
        self.assertEqual(len(house.parse_layout(unknown + "\n\n" + ROW, REPORT, URL)), 1)

    def test_index_failure_never_fabricates_trades(self):
        with patch.object(house, "_download", side_effect=house.requests.ConnectionError):
            result = house.gather(
                {"house_index_url": "https://example/{year}", "house_pdf_url": URL}, dt.date(2026, 10, 2)
            )
        self.assertEqual(result["txns"], [])
        self.assertEqual(result["coverage"]["Senate"], "unavailable")
        self.assertIn("index_unavailable", result["source_errors"])

    def test_house_sample_never_claims_complete_congress_coverage(self):
        raw = {
            "txns": [house.parse_layout(ROW, REPORT, URL)[0]],
            "coverage": {
                "reports_with_supported_stock_rows": 1,
                "reports_attempted": 2,
                "House": "sample",
                "Senate": "unavailable",
            },
        }
        with patch.object(build_feed, "gather", return_value=raw):
            feed = build_feed.build({"service": "congress_trades", "schema_version": "1.0", "ttl_hours": 48})
        self.assertEqual(feed["status"], "partial")
        self.assertIn("Senate", feed["notes"])
        self.assertEqual(feed["data"]["recent"][0]["source_url"], URL)


if __name__ == "__main__":
    unittest.main()
