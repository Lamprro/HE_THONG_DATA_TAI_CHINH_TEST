from __future__ import annotations

from datetime import date, timedelta
from time import perf_counter
from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query

from app.core.serialization import dataframe_to_records, utc_now_iso
from app.providers.vnstock_provider import vnstock_provider

router = APIRouter()

SUPPORTED_INDEX_CODES = {
    "VNINDEX": {"name": "VN-Index", "exchange": "HOSE"},
    "VN30": {"name": "VN30-Index", "exchange": "HOSE"},
    "HNXINDEX": {"name": "HNX-Index", "exchange": "HNX"},
}
INDEX_SOURCE = "kbs"
INDEX_INTERVAL = "1D"


def normalize_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if not value or len(value) > 12 or not value.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid security symbol")
    return value


def normalize_index_code(index_code: str) -> str:
    value = index_code.strip().upper()
    if value not in SUPPORTED_INDEX_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported index code. Allowed: {', '.join(SUPPORTED_INDEX_CODES)}",
        )
    return value


def provider_error(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=502,
        detail={
            "message": "VnStock/upstream provider could not return data",
            "provider": "vnstock",
            "provider_error": str(exc),
        },
    )


def response(dataset: str, symbol: str, data, started: float, **meta) -> dict:
    rows = dataframe_to_records(data)
    return {
        "provider": "vnstock",
        "dataset": dataset,
        "symbol": symbol,
        "retrieved_at": utc_now_iso(),
        "elapsed_ms": round((perf_counter() - started) * 1000, 2),
        "count": len(rows),
        **meta,
        "data": rows,
    }


@router.get(
    "/equities/{symbol}/ohlcv",
    tags=["vnstock-market"],
    summary="Get historical OHLCV",
    description="Historical open/high/low/close/volume data. Defaults to the latest 30 calendar days.",
)
def equity_ohlcv(
    symbol: str = Path(..., examples=["FPT"]),
    start: date | None = Query(None, description="Start date YYYY-MM-DD", examples=["2026-08-01"]),
    end: date | None = Query(None, description="End date YYYY-MM-DD", examples=["2026-08-27"]),
) -> dict:
    ticker = normalize_symbol(symbol)
    end_date = end or date.today()
    start_date = start or (end_date - timedelta(days=30))
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start must be <= end")
    if (end_date - start_date).days > 3650:
        raise HTTPException(status_code=400, detail="A single request is limited to 10 years")

    started = perf_counter()
    try:
        df = vnstock_provider.equity_ohlcv(ticker, start_date.isoformat(), end_date.isoformat())
        return response(
            "equity_ohlcv",
            ticker,
            df,
            started,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise provider_error(exc) from exc


@router.get(
    "/equities/{symbol}/quote",
    tags=["vnstock-market"],
    summary="Get current equity quote",
)
def equity_quote(symbol: str = Path(..., examples=["FPT"])) -> dict:
    ticker = normalize_symbol(symbol)
    started = perf_counter()
    try:
        df = vnstock_provider.equity_quote(ticker)
        return response("equity_quote", ticker, df, started)
    except Exception as exc:
        raise provider_error(exc) from exc


@router.get(
    "/indices",
    tags=["vnstock-index"],
    summary="List supported market indices",
)
def supported_indices() -> dict:
    rows = [
        {"code": code, **metadata}
        for code, metadata in SUPPORTED_INDEX_CODES.items()
    ]
    return {
        "provider": "vnstock",
        "dataset": "market_indices",
        "retrieved_at": utc_now_iso(),
        "count": len(rows),
        "data": rows,
    }


@router.get(
    "/indices/{index_code}/ohlcv",
    tags=["vnstock-index"],
    summary="Get daily market-index OHLCV",
    description=(
        "Daily OHLCV/index-level history for VNINDEX, VN30 or HNXINDEX. "
        "This endpoint is intended for the end-of-day index ingestion job."
    ),
)
def index_ohlcv(
    index_code: str = Path(..., examples=["VNINDEX"]),
    start: date | None = Query(None, description="Start date YYYY-MM-DD"),
    end: date | None = Query(None, description="End date YYYY-MM-DD"),
) -> dict:
    code = normalize_index_code(index_code)
    end_date = end or date.today()
    start_date = start or (end_date - timedelta(days=30))
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start must be <= end")
    if (end_date - start_date).days > 3650:
        raise HTTPException(status_code=400, detail="A single request is limited to 10 years")

    started = perf_counter()
    try:
        df = vnstock_provider.index_ohlcv(
            code,
            start_date.isoformat(),
            end_date.isoformat(),
            INDEX_INTERVAL,
            INDEX_SOURCE,
        )
        return response(
            "index_ohlcv",
            code,
            df,
            started,
            asset_type="index",
            interval=INDEX_INTERVAL,
            source=INDEX_SOURCE,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise provider_error(exc) from exc


@router.get(
    "/indices/{index_code}/latest",
    tags=["vnstock-index"],
    summary="Get latest available completed daily index bar",
    description="Latest available 1D bar. This is not a realtime index quote.",
)
def index_latest(index_code: str = Path(..., examples=["VNINDEX"])) -> dict:
    code = normalize_index_code(index_code)
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    started = perf_counter()
    try:
        df = vnstock_provider.index_latest(
            code,
            start_date.isoformat(),
            end_date.isoformat(),
            INDEX_SOURCE,
        )
        return response(
            "index_latest_daily",
            code,
            df,
            started,
            asset_type="index",
            interval=INDEX_INTERVAL,
            source=INDEX_SOURCE,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise provider_error(exc) from exc


@router.get(
    "/indices/{index_code}/members",
    tags=["vnstock-index"],
    summary="Get current index constituents",
)
def index_members(index_code: str = Path(..., examples=["VN30"])) -> dict:
    code = normalize_index_code(index_code)
    started = perf_counter()
    try:
        df = vnstock_provider.index_members(code, INDEX_SOURCE)
        return response(
            "index_members",
            code,
            df,
            started,
            asset_type="index",
            source=INDEX_SOURCE,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise provider_error(exc) from exc


@router.get(
    "/companies/{symbol}",
    tags=["vnstock-company"],
    summary="Get company profile",
)
def company_info(symbol: str = Path(..., examples=["FPT"])) -> dict:
    ticker = normalize_symbol(symbol)
    started = perf_counter()
    try:
        df = vnstock_provider.company_info(ticker)
        return response("company_info", ticker, df, started)
    except Exception as exc:
        raise provider_error(exc) from exc


@router.get(
    "/equities/{symbol}/financials/{statement}",
    tags=["vnstock-fundamental"],
    summary="Get a financial statement",
    description="statement = balance_sheet | income_statement | cash_flow",
)
def financial_statement(
    symbol: str = Path(..., examples=["FPT"]),
    statement: Literal["balance_sheet", "income_statement", "cash_flow"] = Path(...),
    period: Literal["year", "quarter"] = Query("year"),
) -> dict:
    ticker = normalize_symbol(symbol)
    started = perf_counter()
    try:
        df = vnstock_provider.financial_statement(ticker, statement, period)
        return response(statement, ticker, df, started, period=period)
    except Exception as exc:
        raise provider_error(exc) from exc


@router.get(
    "/equities/{symbol}/ratio",
    tags=["vnstock-fundamental"],
    summary="Get financial ratios",
)
def financial_ratio(
    symbol: str = Path(..., examples=["FPT"]),
    period: Literal["year", "quarter"] = Query("year"),
) -> dict:
    ticker = normalize_symbol(symbol)
    started = perf_counter()
    try:
        df = vnstock_provider.ratio(ticker, period)
        return response("financial_ratio", ticker, df, started, period=period)
    except Exception as exc:
        raise provider_error(exc) from exc
