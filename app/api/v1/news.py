from __future__ import annotations

from time import perf_counter

import pandas as pd
from fastapi import APIRouter, HTTPException, Path, Query

from app.core.serialization import dataframe_to_records, utc_now_iso
from app.providers.vnstock_news_provider import vnstock_news_provider
from app.providers.vnstock_provider import vnstock_provider

router = APIRouter()


def normalize_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if not value or len(value) > 12 or not value.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid security symbol")
    return value


def sponsor_error(exc: Exception) -> HTTPException:
    message = str(exc)
    status_code = 503 if "not installed" in message.lower() else 502
    return HTTPException(
        status_code=status_code,
        detail={
            "message": "vnstock_news crawler is not available in this runtime" if status_code == 503 else "vnstock_news/upstream source could not return data",
            "provider": "vnstock_news",
            "provider_error": message,
            "hint": "vnstock_news is a sponsor/private package. The deployed runtime must have the authorized package installed before crawler endpoints can run.",
        },
    )


@router.get(
    "/status",
    tags=["vnstock-news-crawler"],
    summary="Check vnstock_news package status",
    description="Shows whether the sponsor/private vnstock_news package is installed in the deployed runtime.",
)
def vnstock_news_status() -> dict:
    return vnstock_news_provider.status()


@router.get(
    "/sites",
    tags=["vnstock-news-crawler"],
    summary="List sites supported by vnstock_news",
)
def vnstock_news_sites() -> dict:
    started = perf_counter()
    try:
        sites = vnstock_news_provider.supported_sites()
        return {
            "provider": "vnstock_news",
            "dataset": "supported_sites",
            "retrieved_at": utc_now_iso(),
            "elapsed_ms": round((perf_counter() - started) * 1000, 2),
            "count": len(sites),
            "data": sites,
        }
    except Exception as exc:
        raise sponsor_error(exc) from exc


@router.get(
    "/latest",
    tags=["vnstock-news-crawler"],
    summary="Get latest RSS news from a supported site",
    description="Uses vnstock_news.Crawler.get_articles_from_feed(). Requires the sponsor/private package to be installed.",
)
def latest_news(
    site: str = Query("cafef", examples=["cafef", "vnexpress", "vietstock"]),
    limit: int = Query(10, ge=1, le=30),
) -> dict:
    started = perf_counter()
    try:
        rows = vnstock_news_provider.latest(site=site.strip().lower(), limit=limit)
        data = dataframe_to_records(pd.DataFrame(rows))
        return {
            "provider": "vnstock_news",
            "dataset": "rss_latest",
            "source": site.strip().lower(),
            "retrieved_at": utc_now_iso(),
            "elapsed_ms": round((perf_counter() - started) * 1000, 2),
            "count": len(data),
            "data": data,
        }
    except Exception as exc:
        raise sponsor_error(exc) from exc


@router.get(
    "/history",
    tags=["vnstock-news-crawler"],
    summary="Fetch detailed historical articles from a supported site",
    description=(
        "Uses vnstock_news.BatchCrawler.fetch_articles(). This can fetch article content and is deliberately capped for the Vercel demo. "
        "Use a persistent worker later for large backfills."
    ),
)
def historical_news(
    site: str = Query("cafef", examples=["cafef", "vnexpress", "vietstock"]),
    limit: int = Query(5, ge=1, le=10),
    request_delay: float = Query(0.5, ge=0.2, le=3.0),
) -> dict:
    started = perf_counter()
    try:
        df = vnstock_news_provider.historical(
            site=site.strip().lower(),
            limit=limit,
            request_delay=request_delay,
        )
        data = dataframe_to_records(df)
        return {
            "provider": "vnstock_news",
            "dataset": "historical_articles",
            "source": site.strip().lower(),
            "retrieved_at": utc_now_iso(),
            "elapsed_ms": round((perf_counter() - started) * 1000, 2),
            "count": len(data),
            "data": data,
        }
    except Exception as exc:
        raise sponsor_error(exc) from exc


@router.get(
    "/company/{symbol}",
    tags=["vnstock-news-community"],
    summary="Get company-tagged news using public VnStock",
    description=(
        "Immediate test endpoint that uses the currently installed community VnStock Reference.company(symbol).news() API. "
        "This is company-tagged news and is distinct from the sponsor vnstock_news multi-publication crawler."
    ),
)
def company_news(
    symbol: str = Path(..., examples=["FPT"]),
    limit: int = Query(10, ge=1, le=50),
) -> dict:
    ticker = normalize_symbol(symbol)
    started = perf_counter()
    try:
        df = vnstock_provider.company_news(ticker)
        if not df.empty:
            df = df.head(limit)
        data = dataframe_to_records(df)
        return {
            "provider": "vnstock",
            "engine": "community-reference-company-news",
            "dataset": "company_news",
            "symbol": ticker,
            "retrieved_at": utc_now_iso(),
            "elapsed_ms": round((perf_counter() - started) * 1000, 2),
            "count": len(data),
            "data": data,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "VnStock company news/upstream provider could not return data",
                "provider": "vnstock",
                "provider_error": str(exc),
            },
        ) from exc
