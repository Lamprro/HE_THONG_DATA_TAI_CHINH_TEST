from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NewsArticle:
    canonical_url: str
    title: str
    sapo: str | None
    content_text: str
    author: str | None
    language: str
    published_at: datetime | None
    external_id: str | None
    metadata: dict


@dataclass(frozen=True)
class RawNewsPayload:
    id: str
    data_source_id: int
    source_url: str | None
    payload: object
    raw_text: str | None
    published_at: datetime | None
