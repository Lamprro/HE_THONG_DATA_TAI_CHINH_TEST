from dataclasses import asdict
import os

from fastapi import APIRouter, Request

from app.providers.cafef_provider import cafef_provider
from app.providers.vndirect_provider import vndirect_provider
from app.providers.vnstock_news_provider import vnstock_news_provider
from app.providers.vnstock_provider import vnstock_provider


router = APIRouter(tags=["system"])


@router.get("/capabilities", summary="Inspect deployed source routes and history contracts")
def capabilities(request: Request) -> dict:
    """Registration is evidence of an API contract, never proof of upstream availability."""
    paths = request.app.openapi()["paths"]
    routes = [
        {"path": path, "method": method.upper(), "summary": operation.get("summary", ""),
         "parameters": operation.get("parameters", [])}
        for path, methods in sorted(paths.items()) if path.startswith("/api/v1/")
        for method, operation in methods.items() if method in {"get", "post"}
    ]
    return {
        "schema_version": "admin.source_capabilities.v1",
        "build_commit": os.getenv("VERCEL_GIT_COMMIT_SHA", os.getenv("APP_BUILD_COMMIT", "unknown")),
        "timezone": "Asia/Ho_Chi_Minh",
        "stateless": True,
        "routes": routes,
        "history_contracts": [
            {"operation": "RATIO", "provider": "vndirect", "maximum_calendar_years": 15,
             "both_dates_required_for_history": True},
            {"operation": "FOREIGN_TRADES", "provider": "cafef", "maximum_calendar_years": 15,
             "both_dates_required_for_history": True},
            {"operation": "INDEX_OHLCV", "provider": "kbs", "native_adapter": True},
            {"operation": "MACRO_OBSERVATIONS", "providers": ["worldbank", "bis"],
             "country": "VNM", "monthly_opt_in": "include_monthly"},
        ],
        "limitations": [
            "Registered routes do not prove provider credentials, quota, upstream health or historical completeness.",
            "Maximum date window is a request guard, not a claim that all requested history exists.",
            "Ingestion, validation, canonical builds and administrative audit belong to the Java backend.",
            "No missing observations, publication dates or quarterly bases are synthesized.",
        ],
    }


@router.get("/health", summary="Check API availability")
def health() -> dict:
    return {
        "status": "ok",
        "service": "financial-data-api-playground",
        "version": "0.7.3",
        "build_commit": os.getenv("VERCEL_GIT_COMMIT_SHA", os.getenv("APP_BUILD_COMMIT", "unknown")),
        "data_contracts": ["financial.disclosures.v1", "financial.metadata.v1", "vndirect.ratios.history.v1", "foreign_trades.v1", "native-kbs-index", "native-bis-monthly"],
        "proxy_mode": "allowlisted-passthrough",
        "macro_schema": "macro_observations.v1",
        "macro_country": "VNM",
    }


@router.get("/providers", summary="List registered data providers")
def providers() -> dict:
    vnstock = asdict(vnstock_provider.info)
    if vnstock_provider.info.status == "unavailable":
        vnstock["message"] = (
            "VnStock endpoints are registered but unavailable because the required "
            "vnstock package is missing or could not initialize in this runtime."
        )

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
