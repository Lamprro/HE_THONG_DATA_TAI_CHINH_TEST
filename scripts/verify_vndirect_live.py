"""Exercise the real VNDirect routes and upstream for the five tracked symbols.

Run from the Python repository root: python scripts/verify_vndirect_live.py
This deliberately does not mock HTTP responses or construct provider payloads.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.vndirect import router


SYMBOLS = ("FPT", "ACB", "BID", "HPG", "VCB")
STATEMENTS = ("balance-sheet", "income-statement", "cash-flow")
EXPECTED_MODELS = {
    "FPT": (1, 2, 3),
    "ACB": (101, 102, 103),
    "BID": (101, 102, 103),
    "HPG": (1, 2, 3),
    "VCB": (101, 102, 103),
}


def checked_get(client: TestClient, path: str, symbol: str, dataset: str) -> list[dict]:
    response = client.get(path)
    if response.is_error:
        raise RuntimeError(f"HTTP {response.status_code}: {response.json().get('detail')}")
    payload = response.json()
    assert payload["provider"] == "vndirect", (symbol, dataset, payload)
    assert payload["symbol"] == symbol, (symbol, dataset, payload)
    rows = payload["data"]
    assert rows and payload["count"] == len(rows), (symbol, dataset, payload)
    for row in rows:
        actual = row.get("symbol") or row.get("code")
        assert actual == symbol, (symbol, dataset, actual)
    print(f"{symbol} {dataset}: {len(rows)} rows")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fiscal-date", default="2026-06-30")
    parser.add_argument("--audit-history", action="store_true")
    args = parser.parse_args()

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/vndirect")
    today = date.today()
    start = today - timedelta(days=7)
    history_failures: list[str] = []

    with TestClient(app) as client:
        for symbol in SYMBOLS:
            base = f"/api/v1/vndirect/equities/{symbol}"
            quote = checked_get(client, f"{base}/quote", symbol, "quote")
            assert len(quote) == 1 and quote[0]["record_type"] == "QUOTE_SNAPSHOT"
            assert quote[0]["close_price"] is not None

            company = checked_get(client, f"{base}/company", symbol, "company")
            assert len(company) == 1 and company[0]["companyName"].strip()

            prices = checked_get(
                client,
                f"{base}/ohlcv?start={start}&end={today}",
                symbol,
                "ohlcv",
            )
            assert all(row["record_type"] == "DAILY_CANDLE" for row in prices)
            assert all(row["close_price"] is not None for row in prices)

            if args.audit_history:
                history_start = today.replace(year=today.year - 5)
                try:
                    history = checked_get(
                        client,
                        f"{base}/ohlcv?start={history_start}&end={today}",
                        symbol,
                        "five-year ohlcv",
                    )
                    invalid = [
                        row["trading_date"]
                        for row in history
                        if row["close_price"] is None
                        or row["low_price"] is None
                        or row["high_price"] is None
                        or not row["low_price"] <= row["close_price"] <= row["high_price"]
                    ]
                    assert not invalid, (symbol, "invalid upstream OHLC", invalid[:20])
                except (AssertionError, ValueError, RuntimeError, httpx.HTTPStatusError) as exc:
                    history_failures.append(f"{symbol}: {exc}")
                    print(f"{symbol} five-year ohlcv FAILED: {exc}")

            for statement, model in zip(STATEMENTS, EXPECTED_MODELS[symbol]):
                rows = checked_get(
                    client,
                    f"{base}/financials/{statement}"
                    f"?fiscal_date={args.fiscal_date}&report_type=QUARTER",
                    symbol,
                    statement,
                )
                assert all(
                    row["modelType"] == model
                    and row["fiscalDate"] == args.fiscal_date
                    and row["reportType"] == "QUARTER"
                    for row in rows
                ), (symbol, statement)

    if history_failures:
        raise SystemExit("Five-year source failures: " + "; ".join(history_failures))


if __name__ == "__main__":
    main()
