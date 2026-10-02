# Official House source recovery (2026-10-02)

The former House/Senate Stock Watcher S3 URLs return HTTP 403. Default ingestion
now reads the official House Clerk annual financial-disclosure ZIP index and
fetches at most 20 newest PTR PDFs within the configured 45-day disclosure window.
It requires explicitly ticker-tagged `[ST]` stock rows and valid transaction,
notification and filing dates. Each emitted row links to its official PDF.

**Coverage is always partial**: House only, bounded sample, no OCR/guessed tickers.
Scanned/unsupported PDFs and Senate data are excluded. Amended reports may repeat
transactions; counts are parsed disclosure rows, not certified distinct trades.
The feed exposes report coverage/errors and explanatory notes. No parsed rows
means `unavailable`, never a fabricated measured zero. Historical all-Congress
counts are not directly comparable to this new sample.

`pypdf>=5.9,<7` is the only added dependency. It is a public PDF parser; no account,
API key, login or Senate access-consent automation is used. Offline tests cover
XML filtering, wrapped asset cells, ticker/date rejection, source links, failures,
and partial-coverage labeling.
