from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import Response

from app.core.proxy import (
    build_upstream_url,
    load_proxy_providers,
    resolve_proxy_provider,
)

router = APIRouter()

_REQUEST_BLOCKED_HEADERS = {
    "authorization",
    "connection",
    "content-length",
    "cookie",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

_RESPONSE_BLOCKED_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "set-cookie",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def _request_headers(request: Request, defaults: dict[str, str]) -> dict[str, str]:
    headers = dict(defaults)

    for key, value in request.headers.items():
        lower = key.lower()

        if lower in _REQUEST_BLOCKED_HEADERS or lower.startswith("x-forwarded-"):
            continue

        headers[key] = value

    return headers


def _passthrough_response(upstream: httpx.Response, body: bytes) -> Response:
    response = Response(content=body, status_code=upstream.status_code)
    raw_headers: list[tuple[bytes, bytes]] = []
    has_content_length = False

    for key, value in upstream.headers.multi_items():
        lower = key.lower()

        if lower in _RESPONSE_BLOCKED_HEADERS:
            continue

        if lower == "content-length":
            has_content_length = True

        raw_headers.append(
            (key.encode("latin-1"), value.encode("latin-1"))
        )

    if not has_content_length:
        raw_headers.append((b"content-length", str(len(body)).encode("ascii")))

    response.raw_headers = raw_headers
    return response


@router.get(
    "/providers",
    tags=["third-party-proxy"],
    summary="List allowlisted upstream providers",
)
def proxy_providers() -> dict:
    providers = load_proxy_providers()

    return {
        "mode": "allowlisted-passthrough",
        "providers": [
            {
                "code": provider.code,
                "base_url": provider.base_url,
            }
            for provider in providers.values()
        ],
    }


@router.api_route(
    "/{provider}/{upstream_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"],
    tags=["third-party-proxy"],
    summary="Proxy a request to an allowlisted third-party API",
    description=(
        "Forwards the HTTP method, query string and request body to the selected "
        "allowlisted provider. The upstream response body, status code and content "
        "type are returned without wrapping or JSON transformation. Hop-by-hop, "
        "cookie and authorization headers are intentionally not forwarded."
    ),
)
async def passthrough_proxy(
    request: Request,
    provider: str = Path(..., examples=["vndirect"]),
    upstream_path: str = Path(..., examples=["stock_prices"]),
) -> Response:
    selected = resolve_proxy_provider(provider)
    upstream_url = build_upstream_url(
        selected,
        upstream_path,
        request.url.query,
    )

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=False,
        ) as client:
            async with client.stream(
                method=request.method,
                url=upstream_url,
                headers=_request_headers(request, selected.default_headers),
                content=await request.body(),
            ) as upstream:
                body = b"".join([chunk async for chunk in upstream.aiter_raw()])
                return _passthrough_response(upstream, body)

    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail={
                "message": "Upstream provider timed out",
                "provider": selected.code,
            },
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Could not reach upstream provider",
                "provider": selected.code,
                "provider_error": str(exc),
            },
        ) from exc
