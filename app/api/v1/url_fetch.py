from __future__ import annotations

from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

_TEXTUAL_TYPES = ("text/", "application/json", "application/ld+json", "application/xml")
_MAX_RESPONSE_BYTES = 5 * 1024 * 1024


def _validated_url(value: str) -> str:
    url = value.strip()
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="url must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="url must not contain credentials")
    return url


def _is_textual(content_type: str) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type.startswith(_TEXTUAL_TYPES) or media_type.endswith("+json") or media_type.endswith("+xml")


@router.get("", tags=["url-fetch"], summary="Fetch one source URL for backend news ingestion")
async def fetch_url(url: str = Query(..., max_length=4096)) -> dict:
    requested_url = _validated_url(url)
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(45.0),
            follow_redirects=True,
            headers={"Accept": "text/html,application/json,text/plain,application/xml,*/*"},
        ) as client:
            async with client.stream("GET", requested_url) as upstream:
                content_type = upstream.headers.get("content-type", "application/octet-stream")
                textual = _is_textual(content_type)
                chunks: list[bytes] = []
                size = 0
                if textual:
                    async for chunk in upstream.aiter_bytes():
                        size += len(chunk)
                        if size > _MAX_RESPONSE_BYTES:
                            raise HTTPException(status_code=413, detail="Text response exceeds the 5 MiB ingestion limit")
                        chunks.append(chunk)
                return {
                    "requested_url": requested_url,
                    "final_url": str(upstream.url),
                    "http_status": upstream.status_code,
                    "content_type": content_type,
                    "textual": textual,
                    "body": b"".join(chunks).decode(upstream.encoding or "utf-8", errors="replace") if textual else None,
                }
    except HTTPException:
        raise
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Source URL timed out") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not fetch source URL") from exc
