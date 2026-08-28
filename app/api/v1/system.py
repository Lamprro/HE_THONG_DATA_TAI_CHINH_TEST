from dataclasses import asdict

from fastapi import APIRouter

from app.providers.vnstock_news_provider import vnstock_news_provider
from app.providers.vnstock_provider import vnstock_provider

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
    data = [vnstock, news]
    return {"count": len(data), "data": data}
