from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from fastapi import HTTPException


@dataclass(frozen=True)
class ProxyProvider:
    code: str
    base_url: str
    default_headers: dict[str, str] = field(default_factory=dict)


_DEFAULT_PROVIDERS: dict[str, ProxyProvider] = {
    "vndirect": ProxyProvider(
        code="vndirect",
        base_url="https://api-finfo.vndirect.com.vn/v4",
        default_headers={
            "Accept": "application/json",
            "User-Agent": "Financial-Data-Proxy/1.0",
        },
    ),
    "cafef": ProxyProvider(
        code="cafef",
        base_url="https://cafef.vn",
        default_headers={
            "Accept": "application/json,text/plain,text/html,*/*",
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://cafef.vn/",
        },
    ),
    "cafef-financial": ProxyProvider(
        code="cafef-financial",
        base_url="https://s.cafef.vn",
        default_headers={
            "Accept": "application/json,text/plain,text/html,*/*",
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://s.cafef.vn/",
        },
    ),
}


def _validate_base_url(code: str, value: str) -> str:
    base_url = value.strip().rstrip("/")
    parsed = urlsplit(base_url)

    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError(
            f"Proxy provider '{code}' must use an absolute HTTPS base URL"
        )

    if parsed.username or parsed.password:
        raise RuntimeError(
            f"Proxy provider '{code}' must not embed credentials in the URL"
        )

    return base_url


def load_proxy_providers() -> dict[str, ProxyProvider]:
    providers = dict(_DEFAULT_PROVIDERS)
    raw = os.getenv("PROXY_PROVIDER_BASE_URLS_JSON", "").strip()

    if not raw:
        return providers

    try:
        configured = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "PROXY_PROVIDER_BASE_URLS_JSON must be a JSON object"
        ) from exc

    if not isinstance(configured, dict):
        raise RuntimeError(
            "PROXY_PROVIDER_BASE_URLS_JSON must be a JSON object"
        )

    for raw_code, raw_url in configured.items():
        code = str(raw_code).strip().lower()

        if not code or not code.replace("-", "").replace("_", "").isalnum():
            raise RuntimeError(f"Invalid proxy provider code: {raw_code!r}")

        if not isinstance(raw_url, str):
            raise RuntimeError(
                f"Proxy provider '{code}' base URL must be a string"
            )

        providers[code] = ProxyProvider(
            code=code,
            base_url=_validate_base_url(code, raw_url),
            default_headers={
                "Accept": "*/*",
                "User-Agent": "Financial-Data-Proxy/1.0",
            },
        )

    return providers


def resolve_proxy_provider(code: str) -> ProxyProvider:
    normalized = code.strip().lower()
    providers = load_proxy_providers()
    provider = providers.get(normalized)

    if provider is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Unknown proxy provider",
                "provider": normalized,
                "available_providers": sorted(providers.keys()),
            },
        )

    return provider


def build_upstream_url(provider: ProxyProvider, upstream_path: str, query: str) -> str:
    path = upstream_path.strip().lstrip("/")
    segments = [segment for segment in path.split("/") if segment]

    if any(segment in {".", ".."} for segment in segments):
        raise HTTPException(status_code=400, detail="Invalid upstream path")

    url = provider.base_url

    if path:
        url = f"{url}/{path}"

    if query:
        url = f"{url}?{query}"

    return url
