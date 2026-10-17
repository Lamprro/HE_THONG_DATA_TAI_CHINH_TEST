# Source contracts for training data — 2026-10-17

Version 0.7.0 adds optional `start`/`end` to VNDirect ratios. Both dates are required
for history (maximum 15 calendar years); the old latest-only call remains supported.
All source pages are retrieved and symbol/date/duplicate mismatches fail the request.
`reportDate` remains an observation date, **not** verified publication or vintage availability.

`GET /api/v1/kbs/indices/{VNINDEX|VN30|HNXINDEX}/ohlcv?start=...&end=...`
retrieves native KBS daily bars in index points and retains each original source record.
This adapter does not scale index points as stock prices or synthesize missing sessions.

`GET /api/v1/cafef/equities/{symbol}/foreign-trades?start=...&end=...`
retrieves the complete source page set. The upstream date filter is month/day/year;
returned days must still match the requested window. Null volume stays null.
The source may provide only recent sessions even when a longer window is requested.

`GET /api/v1/macro/bis/observations?...&include_monthly=true` includes the native
monthly VND/USD average, alongside the existing quarterly series. Defaults are unchanged.
Monthly frequency is not an interpolation of annual/quarterly observations.

Financial metadata retains explicit original/restated evidence and date precision where
provided. Fiscal, created, modified and retrieval dates never substitute for publication.
Historical revision vintages, corporate actions, historical sector membership and full
filing publication history remain unverified unless a source explicitly supplies them.

Validation: 23 Python unit/transport contract tests passed locally on 2026-10-17.
These tests use mocked upstream transports and do not certify live source coverage.
Live Java ingestion acceptance and deployment evidence are recorded in the Java handover.
