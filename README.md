# congress_trades

Independent ArkenLabs satellite. Publishes recent U.S. congressional stock trades from the
free, keyless **House + Senate stock-watcher** disclosure datasets. Fully decoupled — the app
fetches the feed read-only and degrades gracefully if it is offline.

## Produces `out/congress_trades.json`

`data`:
- `recent` — most recently disclosed trades: `{ticker, member, chamber, side, amount_range, traded_at, disclosed_at}`
- `most_traded` — tickers with the most member trades in the lookback window (`buys`/`sells`)
- `by_ticker` — per-symbol map for the company page

## Data source (no key)

- House: `house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json`
- Senate: `senate-stock-watcher-data.s3-us-west-2.amazonaws.com/aggregate/all_transactions.json`

## Run locally

```bash
pip install -r requirements.txt
python src/build_feed.py && python scripts/post_text.py
```

## Publish

GitHub Actions publishes `out/` to `gh-pages` (weekdays after close + manual dispatch). No secrets.

## Not investment advice

Public financial disclosures, informational only.
