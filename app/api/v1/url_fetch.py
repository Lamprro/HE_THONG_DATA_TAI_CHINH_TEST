from __future__ import annotations

from datetime import datetime
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.news.sources import NewsSourceRegistry, canonicalize_url

router = APIRouter(tags=["news-fetch"])
registry = NewsSourceRegistry()
_VIETNAM = ZoneInfo("Asia/Ho_Chi_Minh")
_MAX_BODY_BYTES = 5 * 1024 * 1024


def _approved_url(url: str) -> str:
    parsed = urlparse(url.strip())
    try:
        has_custom_port = parsed.port is not None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="URL port is invalid") from exc
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or has_custom_port:
        raise HTTPException(status_code=400, detail="URL scheme, credentials or port is not allowed")
    try:
        canonical_url = canonicalize_url(url)
        registry.resolve(canonical_url)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="URL host is not an approved NEWS source") from exc
    return canonical_url


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
    current_url = _approved_url(url)

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
                current_url = _approved_url(urljoin(str(response.url), location))
            else:
                raise HTTPException(status_code=502, detail="NEWS source redirected too many times")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Approved NEWS source could not be reached") from exc

    final_url = str(response.url)

    content_type = response.headers.get("content-type", "application/octet-stream")
    media_type = content_type.split(";", 1)[0].strip().lower()
    textual = media_type.startswith("text/") or media_type in {
        "application/xhtml+xml",
        "application/json",
    }
    try:
        if textual and len(response.content) > _MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="NEWS page exceeds the 5 MiB limit")
        body = response.text if textual else None
    except (UnicodeDecodeError, LookupError):
        textual = False
        body = None

    article = None
    extraction_status = "SKIPPED"
    extraction_error = None
    if response.is_success and textual and media_type in {"text/html", "application/xhtml+xml"} and body:
        try:
            article = registry.resolve(final_url).parse_article(final_url, body, response.status_code)
            extraction_status = "SUCCESS"
        except ValueError as exc:
            extraction_status = "FAILED"
            extraction_error = str(exc)

    return {
        "provider": "news-web",
        "dataset": "news_data",
        "requested_url": url.strip(),
        "final_url": final_url,
        "http_status": response.status_code,
        "content_type": content_type,
        "textual": textual,
        "body": body,
        "extraction_status": extraction_status,
        "extraction_error": extraction_error,
        "canonical_url": article.canonical_url if article else None,
        "title": article.title if article else None,
        "sapo": article.sapo if article else None,
        "content_text": article.content_text if article else None,
        "author": article.author if article else None,
        "published_at": article.published_at.isoformat() if article and article.published_at else None,
        "retrieved_at": datetime.now(_VIETNAM).isoformat(),
    }
