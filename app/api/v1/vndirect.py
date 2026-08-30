from __future__ import annotations

from datetime import date, timedelta
from time import perf_counter

from fastapi import APIRouter, HTTPException, Path, Query

from app.core.serialization import dataframe_to_records, utc_now_iso
from app.providers.vndirect_provider import vndirect_provider


router = APIRouter()


# =========================================================
# COMMON HELPERS
# =========================================================

def normalize_symbol(symbol: str) -> str:
    value = symbol.strip().upper()

    if (
        not value
        or len(value) > 12
        or not value.replace("-", "").isalnum()
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid security symbol",
        )

    return value


def provider_error(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=502,
        detail={
            "message": "VNDirect upstream provider could not return data",
            "provider": "vndirect",
            "provider_error": str(exc),
        },
    )


def response(
    dataset: str,
    symbol: str,
    data,
    started: float,
    **meta,
) -> dict:
    rows = dataframe_to_records(data)

    return {
        "provider": "vndirect",
        "dataset": dataset,
        "symbol": symbol,
        "retrieved_at": utc_now_iso(),
        "elapsed_ms": round(
            (perf_counter() - started) * 1000,
            2,
        ),
        "count": len(rows),
        **meta,
        "data": rows,
    }


# =========================================================
# MARKET DATA
# =========================================================

@router.get(
    "/equities/{symbol}/ohlcv",
    tags=["vndirect-market"],
    summary="Get VNDirect historical OHLCV",
    description=(
        "Historical market data directly from VNDirect. "
        "Defaults to the latest 30 calendar days."
    ),
)
def equity_ohlcv(
    symbol: str = Path(
        ...,
        examples=["FPT"],
    ),
    start: date | None = Query(
        None,
        description="Start date YYYY-MM-DD",
    ),
    end: date | None = Query(
        None,
        description="End date YYYY-MM-DD",
    ),
) -> dict:
    ticker = normalize_symbol(symbol)

    end_date = end or date.today()

    start_date = start or (
        end_date - timedelta(days=30)
    )

    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start must be <= end",
        )

    if (end_date - start_date).days > 3650:
        raise HTTPException(
            status_code=400,
            detail="A single request is limited to 10 years",
        )

    started = perf_counter()

    try:
        df = vndirect_provider.equity_ohlcv(
            ticker,
            start_date.isoformat(),
            end_date.isoformat(),
        )

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
    tags=["vndirect-market"],
    summary="Get latest VNDirect quote",
    description="Latest available trading session from VNDirect.",
)
def equity_quote(
    symbol: str = Path(
        ...,
        examples=["FPT"],
    ),
) -> dict:
    ticker = normalize_symbol(symbol)

    started = perf_counter()

    try:
        df = vndirect_provider.equity_quote(ticker)

        return response(
            "equity_quote",
            ticker,
            df,
            started,
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise provider_error(exc) from exc


# =========================================================
# COMPANY
# =========================================================

@router.get(
    "/equities/{symbol}/company",
    tags=["vndirect-company"],
    summary="Get VNDirect company information",
    description="Basic listed company information from VNDirect.",
)
def company(
    symbol: str = Path(
        ...,
        examples=["FPT"],
    ),
) -> dict:
    ticker = normalize_symbol(symbol)

    started = perf_counter()

    try:
        df = vndirect_provider.company(ticker)

        return response(
            "company",
            ticker,
            df,
            started,
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise provider_error(exc) from exc


# =========================================================
# FINANCIAL STATEMENTS
# =========================================================

@router.get(
    "/equities/{symbol}/financials/balance-sheet",
    tags=["vndirect-financials"],
    summary="Get VNDirect balance sheet",
    description=(
        "Balance sheet from VNDirect. "
        "Automatically detects the correct financial model "
        "for non-financial companies, banks and securities firms."
    ),
)
def balance_sheet(
    symbol: str = Path(
        ...,
        examples=["FPT"],
    ),
    fiscal_date: date | None = Query(
        None,
        description=(
            "Fiscal date YYYY-MM-DD. "
            "If omitted, the latest available period is used."
        ),
    ),
    report_type: str = Query(
        "QUARTER",
        description="VNDirect report type, default QUARTER.",
    ),
) -> dict:
    ticker = normalize_symbol(symbol)

    started = perf_counter()

    try:
        resolved_date = (
            fiscal_date.isoformat()
            if fiscal_date
            else None
        )

        df = vndirect_provider.balance_sheet(
            symbol=ticker,
            fiscal_date=resolved_date,
            report_type=report_type.upper(),
        )

        return response(
            "balance_sheet",
            ticker,
            df,
            started,
            requested_fiscal_date=resolved_date,
            report_type=report_type.upper(),
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise provider_error(exc) from exc


@router.get(
    "/equities/{symbol}/financials/income-statement",
    tags=["vndirect-financials"],
    summary="Get VNDirect income statement",
    description=(
        "Income statement from VNDirect. "
        "Automatically detects the correct financial model."
    ),
)
def income_statement(
    symbol: str = Path(
        ...,
        examples=["FPT"],
    ),
    fiscal_date: date | None = Query(
        None,
        description=(
            "Fiscal date YYYY-MM-DD. "
            "If omitted, the latest available period is used."
        ),
    ),
    report_type: str = Query(
        "QUARTER",
        description="VNDirect report type, default QUARTER.",
    ),
) -> dict:
    ticker = normalize_symbol(symbol)

    started = perf_counter()

    try:
        resolved_date = (
            fiscal_date.isoformat()
            if fiscal_date
            else None
        )

        df = vndirect_provider.income_statement(
            symbol=ticker,
            fiscal_date=resolved_date,
            report_type=report_type.upper(),
        )

        return response(
            "income_statement",
            ticker,
            df,
            started,
            requested_fiscal_date=resolved_date,
            report_type=report_type.upper(),
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise provider_error(exc) from exc


@router.get(
    "/equities/{symbol}/financials/cash-flow",
    tags=["vndirect-financials"],
    summary="Get VNDirect cash flow statement",
    description=(
        "Cash flow statement from VNDirect. "
        "Automatically detects the correct financial model."
    ),
)
def cash_flow(
    symbol: str = Path(
        ...,
        examples=["FPT"],
    ),
    fiscal_date: date | None = Query(
        None,
        description=(
            "Fiscal date YYYY-MM-DD. "
            "If omitted, the latest available period is used."
        ),
    ),
    report_type: str = Query(
        "QUARTER",
        description="VNDirect report type, default QUARTER.",
    ),
) -> dict:
    ticker = normalize_symbol(symbol)

    started = perf_counter()

    try:
        resolved_date = (
            fiscal_date.isoformat()
            if fiscal_date
            else None
        )

        df = vndirect_provider.cash_flow(
            symbol=ticker,
            fiscal_date=resolved_date,
            report_type=report_type.upper(),
        )

        return response(
            "cash_flow",
            ticker,
            df,
            started,
            requested_fiscal_date=resolved_date,
            report_type=report_type.upper(),
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise provider_error(exc) from exc

@router.get(
    "/equities/{symbol}/ratios",
    tags=["vndirect-financials"],
    summary="Get latest VNDirect financial ratios",
    description=(
        "Latest available fundamental and valuation ratios "
        "from VNDirect."
    ),
)
def ratios(
    symbol: str = Path(
        ...,
        examples=["FPT"],
    ),
) -> dict:
    ticker = normalize_symbol(symbol)

    started = perf_counter()

    try:
        df = vndirect_provider.ratios(ticker)

        return response(
            "ratios",
            ticker,
            df,
            started,
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise provider_error(exc) from exc