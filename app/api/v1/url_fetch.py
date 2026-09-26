from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.news.sources import canonicalize_url
from app.news.service import news_pipeline_service

router = APIRouter(tags=["news-pipeline"])


def _approved_url(url: str) -> str:
    parsed = urlparse(url.strip())
    try:
        custom_port = parsed.port is not None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="URL port is invalid") from exc
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or custom_port:
        raise HTTPException(status_code=400, detail="URL scheme, credentials or port is not allowed")
    try:
        canonical = canonicalize_url(url)
        news_pipeline_service.registry.resolve(canonical)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="URL host is not an approved NEWS source") from exc
    return canonical


@router.get(
    "/url-fetch",
    summary="Fetch an approved news article URL",
    description="Fetch text from a registered NEWS publisher and return the source status/body for validation.",
)
async def fetch_url(url: str = Query(..., min_length=8, max_length=2048)) -> dict:
    requested_url = url.strip()
    current_url = _approved_url(requested_url)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; FinancialNewsBot/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0), follow_redirects=False) as client:
            for _ in range(6):
                response = await client.get(current_url, headers=headers)
                if not response.is_redirect:
                    break
                location = response.headers.get("location")
                if not location:
                    raise HTTPException(status_code=502, detail="NEWS source redirect has no location")
                # Check each hop before making another request; checking only the
                # final URL would allow an intermediate private-network redirect.
                current_url = _approved_url(urljoin(str(response.url), location))
            else:
                raise HTTPException(status_code=502, detail="NEWS source redirected too many times")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Approved NEWS source could not be reached") from exc

    content_type = response.headers.get("content-type", "application/octet-stream")
    media_type = content_type.split(";", 1)[0].strip().lower()
    textual = media_type.startswith("text/") or media_type in {
        "application/xhtml+xml", "application/json",
    }
    try:
        body = response.text if textual else None
    except (UnicodeDecodeError, LookupError):
        textual = False
        body = None

    return {
        "provider": "news-web",
        "dataset": "news_data",
        "requested_url": requested_url,
        "final_url": str(response.url),
        "http_status": response.status_code,
        "content_type": content_type,
        "textual": textual,
        "body": body,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }
