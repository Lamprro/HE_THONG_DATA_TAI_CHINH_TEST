from dataclasses import asdict

from fastapi import APIRouter

from app.providers.vnstock_provider import vnstock_provider

router = APIRouter(tags=["system"])


@router.get("/health", summary="Check API availability")
def health() -> dict:
    return {
        "status": "ok",
        "service": "financial-data-api-playground",
        "version": "0.2.0",
    }


@router.get("/providers", summary="List registered data providers")
def providers() -> dict:
    data = [asdict(vnstock_provider.info)]
    return {"count": len(data), "data": data}
