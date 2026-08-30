from dataclasses import asdict

from fastapi import APIRouter

from app.providers.vnstock_news_provider import vnstock_news_provider
from app.providers.vnstock_provider import vnstock_provider
from app.providers.vndirect_provider import vndirect_provider
from app.providers.cafef_provider import cafef_provider


router = APIRouter(tags=["system"])


@router.get("/health", summary="Check API availability")
def health() -> dict:
    return {
        "status": "ok",
        "service": "financial-data-api-playground",
        "version": "0.3.0",
    }


@router.get("/providers", summary="List registered data providers")
def providers() -> dict:
    vnstock = asdict(vnstock_provider.info)

    news = asdict(vnstock_news_provider.info)
    news["runtime"] = vnstock_news_provider.status()

    vndirect = asdict(vndirect_provider.info)

    cafef = asdict(cafef_provider.info)

    data = [
        vnstock,
        news,
        vndirect,
        cafef,
    ]

    return {
        "count": len(data),
        "data": data,
    }