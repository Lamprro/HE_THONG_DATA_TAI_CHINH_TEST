from __future__ import annotations

from datetime import date, timedelta
from time import perf_counter

from fastapi import APIRouter, HTTPException, Path, Query

from app.core.serialization import dataframe_to_records, utc_now_iso
from app.providers.cafef_provider import cafef_provider


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
            "message": "CafeF upstream provider could not return data",
            "provider": "cafef",
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
        "provider": "cafef",
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
    tags=["cafef-market"],
    summary="Get CafeF historical OHLCV",
    description=(
        "Historical equity market data from CafeF. "
        "Long date ranges are automatically split into smaller requests."
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
        examples=["2026-08-01"],
    ),
    end: date | None = Query(
        None,
        description="End date YYYY-MM-DD",
        examples=["2026-08-30"],
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
        df = cafef_provider.equity_ohlcv(
            symbol=ticker,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
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
    tags=["cafef-market"],
    summary="Get latest CafeF quote",
    description="Latest available trading session from CafeF.",
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
        df = cafef_provider.equity_quote(ticker)

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
# FINANCIAL STATEMENTS
# =========================================================

@router.get(
    "/equities/{symbol}/financials/balance-sheet",
    tags=["cafef-financials"],
    summary="Get CafeF balance sheet",
    description=(
        "Balance sheet data parsed from CafeF financial statement pages."
    ),
)
def balance_sheet(
    symbol: str = Path(
        ...,
        examples=["FPT"],
    ),
    year: int | None = Query(
        None,
        description="Financial statement year",
        examples=[2026],
    ),
    period: int = Query(
        1,
        ge=0,
        le=2,
        description=(
            "CafeF report period. "
            "0 = yearly, 1 = quarterly, 2 = cumulative 6 months."
        ),
    ),
) -> dict:
    ticker = normalize_symbol(symbol)

    started = perf_counter()

    try:
        df = cafef_provider.balance_sheet(
            symbol=ticker,
            year=year,
            period=period,
        )

        return response(
            "balance_sheet",
            ticker,
            df,
            started,
            year=year,
            period=period,
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise provider_error(exc) from exc


@router.get(
    "/equities/{symbol}/financials/income-statement",
    tags=["cafef-financials"],
    summary="Get CafeF income statement",
    description=(
        "Income statement data parsed from CafeF financial statement pages."
    ),
)
def income_statement(
    symbol: str = Path(
        ...,
        examples=["FPT"],
    ),
    year: int | None = Query(
        None,
        description="Financial statement year",
        examples=[2026],
    ),
    period: int = Query(
        1,
        ge=0,
        le=2,
        description=(
            "CafeF report period. "
            "0 = yearly, 1 = quarterly, 2 = cumulative 6 months."
        ),
    ),
) -> dict:
    ticker = normalize_symbol(symbol)

    started = perf_counter()

    try:
        df = cafef_provider.income_statement(
            symbol=ticker,
            year=year,
            period=period,
        )

        return response(
            "income_statement",
            ticker,
            df,
            started,
            year=year,
            period=period,
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise provider_error(exc) from exc


@router.get(
    "/equities/{symbol}/financials/cash-flow",
    tags=["cafef-financials"],
    summary="Get CafeF cash flow statement",
    description=(
        "Cash flow statement data parsed from CafeF financial statement pages."
    ),
)
def cash_flow(
    symbol: str = Path(
        ...,
        examples=["FPT"],
    ),
    year: int | None = Query(
        None,
        description="Financial statement year",
        examples=[2026],
    ),
    period: int = Query(
        1,
        ge=0,
        le=2,
        description=(
            "CafeF report period. "
            "0 = yearly, 1 = quarterly, 2 = cumulative 6 months."
        ),
    ),
) -> dict:
    ticker = normalize_symbol(symbol)

    started = perf_counter()

    try:
        df = cafef_provider.cash_flow(
            symbol=ticker,
            year=year,
            period=period,
        )

        return response(
            "cash_flow",
            ticker,
            df,
            started,
            year=year,
            period=period,
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise provider_error(exc) from exc


# =========================================================
# COMPANY DATA
# =========================================================

@router.get(
    "/equities/{symbol}/company",
    tags=["cafef-company"],
    summary="Get CafeF company information",
    description="Basic company information parsed from CafeF.",
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
        df = cafef_provider.company(ticker)

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


@router.get(
    "/equities/{symbol}/management",
    tags=["cafef-company"],
    summary="Get CafeF company management",
    description=(
        "Management and leadership information parsed from CafeF."
    ),
)
def management(
    symbol: str = Path(
        ...,
        examples=["FPT"],
    ),
) -> dict:
    ticker = normalize_symbol(symbol)

    started = perf_counter()

    try:
        df = cafef_provider.management(ticker)

        return response(
            "management",
            ticker,
            df,
            started,
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise provider_error(exc) from exc


@router.get(
    "/equities/{symbol}/subsidiaries",
    tags=["cafef-company"],
    summary="Get CafeF subsidiaries and associates",
    description=(
        "Subsidiaries and associated companies parsed from CafeF."
    ),
)
def subsidiaries(
    symbol: str = Path(
        ...,
        examples=["FPT"],
    ),
) -> dict:
    ticker = normalize_symbol(symbol)

    started = perf_counter()

    try:
        df = cafef_provider.subsidiaries(ticker)

        return response(
            "subsidiaries",
            ticker,
            df,
            started,
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise provider_error(exc) from exc

# =========================================================
# NEWS / EVENTS
# =========================================================
# =========================================================
# NEWS
# =========================================================

@router.get(
    "/equities/{symbol}/news",
    tags=["cafef-news"],
    summary="Get CafeF company news",
)
def news(
    symbol: str = Path(
        ...,
        examples=["FPT"],
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
    ),
) -> dict:
    ticker = normalize_symbol(symbol)
    started = perf_counter()

    try:
        df = cafef_provider.news(
            symbol=ticker,
            limit=limit,
        )

        return response(
            "news",
            ticker,
            df,
            started,
            limit=limit,
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise provider_error(exc) from exc


# =========================================================
# EVENTS
# =========================================================

@router.get(
    "/equities/{symbol}/events",
    tags=["cafef-events"],
    summary="Get CafeF company events",
)
def events(
    symbol: str = Path(
        ...,
        examples=["FPT"],
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
    ),
) -> dict:
    ticker = normalize_symbol(symbol)
    started = perf_counter()

    try:
        df = cafef_provider.events(
            symbol=ticker,
            limit=limit,
        )

        return response(
            "events",
            ticker,
            df,
            started,
            limit=limit,
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise provider_error(exc) from exc