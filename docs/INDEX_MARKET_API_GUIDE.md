# Index Market API

The VnStock adapter exposes daily index prices and current constituents for
`VNINDEX`, `VN30`, and `HNXINDEX`.

## Endpoints

```http
GET /api/v1/vnstock/indices
GET /api/v1/vnstock/indices/{indexCode}/ohlcv?start=2026-09-01&end=2026-09-18
GET /api/v1/vnstock/indices/{indexCode}/latest
GET /api/v1/vnstock/indices/{indexCode}/members
```

`latest` returns the latest available completed `1D` bar. It is not advertised
as a realtime quote.

## Recommended Spring Boot ingestion job

Create one `INDEX_OHLCV` job for each active row in `market_indices`:

```json
{
  "operation": "INDEX_OHLCV",
  "provider": "vnstock",
  "indexCode": "VNINDEX",
  "lookbackDays": 7,
  "parameters": {
    "interval": "1D"
  }
}
```

Request path:

```text
/api/v1/vndirect/indices/{indexCode}/ohlcv  WRONG
/api/v1/vnstock/indices/{indexCode}/ohlcv   CORRECT
```

Suggested job codes:

```text
VNSTOCK_VNINDEX_INDEX_OHLCV_DAILY
VNSTOCK_VN30_INDEX_OHLCV_DAILY
VNSTOCK_HNXINDEX_INDEX_OHLCV_DAILY
```

Schedule the jobs after the trading session and fetch the previous seven days
so provider corrections are handled idempotently.

## Normalized mapping to index_prices

```text
market_indices.code  -> lookup market_index_id
data[].time/date     -> price_timestamp
data[].open          -> open_value
data[].high          -> high_value
data[].low           -> low_value
data[].close         -> close_value
data[].volume        -> volume
interval             -> interval_code = 1d
provider             -> data_source_id
raw_payload.id       -> raw_payload_id
data_version.id      -> data_version_id
```

Upsert key:

```text
market_index_id + price_timestamp + interval_code + data_source_id
```

The members endpoint feeds `security_index_memberships`. Membership is
effective-dated and should not be overwritten when the index composition
changes.
