import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.providers.macro_provider import MacroUpstreamError, catalog, observations, validate_window

router = APIRouter(tags=["vietnam-macro"])
logger = logging.getLogger(__name__)


@router.get("/{provider}/series")
def series(provider: str, country: str = Query("VNM")):
    try:
        if country != "VNM":
            raise ValueError("Only Vietnam (VNM) is supported")
        data = catalog(provider)
        return dict(country_code=country, count=len(data), data=data)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from None


@router.get("/{provider}/observations")
def fetch_observations(provider: str, start: date, end: date, country: str = Query("VNM")):
    try:
        validate_window(country, start, end)
        catalog(provider)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from None
    try:
        result = observations(provider, country, start, end)
        logger.info("Vietnam macro fetched provider=%s count=%s start=%s end=%s", provider, result["count"], start, end)
        return result
    except MacroUpstreamError:
        logger.warning("Vietnam macro upstream failed provider=%s start=%s end=%s", provider, start, end)
        raise HTTPException(502, detail="Official macro source unavailable or response failed validation") from None
