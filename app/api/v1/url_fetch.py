from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.news.sources import NewsSourceRegistry, canonicalize_url

router = APIRouter(tags=["news-fetch"])
registry = NewsSourceRegistry()


@router.get(
    "/url-fetch",
    summary="Fetch an approved news article URL",
    description=(
        "Fetches text from a URL supported by a registered NEWS source adapter. "
        "Only registered publisher hosts are allowed; the source HTTP status and "
        "content type are returned in the response envelope for downstream validation."
    ),
)
async def fetch_url(url: str = Query(..., min_length=8, max_length=2048)) -> dict:
    parsed = urlparse(url.strip())
    try:
        has_custom_port = parsed.port is not None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="URL port is invalid") from exc
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or has_custom_port:
        raise HTTPException(status_code=400, detail="Credentials and custom ports are not allowed")
    try:
        canonical_url = canonicalize_url(url)
        registry.resolve(canonical_url)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="URL host is not an approved NEWS source") from exc

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; FinancialNewsBot/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0), follow_redirects=True) as client:
            response = await client.get(canonical_url, headers=headers)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Approved NEWS source could not be reached") from exc

    final_url = str(response.url)
    try:
        registry.resolve(final_url)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="NEWS source redirected outside approved hosts") from exc

    content_type = response.headers.get("content-type", "application/octet-stream")
    media_type = content_type.split(";", 1)[0].strip().lower()
    textual = media_type.startswith("text/") or media_type in {
        "application/xhtml+xml",
        "application/json",
    }
    try:
        body = response.text if textual else None
    except (UnicodeDecodeError, LookupError):
        textual = False
        body = None

    return {
        "provider": "news-web",
        "dataset": "news_data",
        "requested_url": url.strip(),
        "final_url": final_url,
        "http_status": response.status_code,
        "content_type": content_type,
        "textual": textual,
        "body": body,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }
