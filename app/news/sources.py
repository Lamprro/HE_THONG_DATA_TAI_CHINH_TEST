from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from datetime import datetime
from urllib.parse import urlparse, urlunparse
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from app.news.models import NewsArticle


class NewsSource(ABC):
    """Adapter contract. Add a source here; the processor remains unchanged."""

    code: str

    @abstractmethod
    def supports(self, url: str) -> bool: ...

    @abstractmethod
    def fetch_article(self, url: str) -> NewsArticle: ...

    @abstractmethod
    def parse_article(self, url: str, html: str, http_status: int | None = None) -> NewsArticle: ...


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("A NEWS URL must be an absolute HTTP(S) URL")
    # Tracking parameters do not identify a different CafeF article.
    return urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path, "", "", ""))


def _text(node) -> str | None:
    if node is None:
        return None
    value = node.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", value) or None


class CafeFNewsSource(NewsSource):
    code = "cafef"
    _hosts = {"cafef.vn", "www.cafef.vn"}

    def __init__(self) -> None:
        self.client = httpx.Client(
            timeout=25.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; FinancialNewsBot/1.0)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )

    def supports(self, url: str) -> bool:
        return urlparse(url).netloc.lower() in self._hosts

    def fetch_article(self, url: str) -> NewsArticle:
        canonical_url = canonicalize_url(url)
        response = self.client.get(canonical_url)
        response.raise_for_status()
        return self.parse_article(str(response.url), response.text, response.status_code)

    def parse_article(self, url: str, html: str, http_status: int | None = None) -> NewsArticle:
        canonical_url = canonicalize_url(url)
        soup = BeautifulSoup(html, "html.parser")

        title = _text(soup.select_one("h1.title, h1.article-title, h1"))
        content = soup.select_one("div.detail-content, div#mainContent, div.article-body, article")
        if content is None:
            raise ValueError("CafeF article content container was not found")
        for unwanted in content.select("script, style, iframe, .related-news, .box-related, .ads"):
            unwanted.decompose()
        content_text = _text(content)
        if not title or not content_text:
            raise ValueError("CafeF article has no title or readable content")

        sapo = _text(soup.select_one("h2.sapo, div.sapo, .detail-sapo"))
        author = _text(soup.select_one(".author, .detail-author"))
        published_at = self._parse_published_at(soup)
        external_id = self._external_id(canonical_url)
        return NewsArticle(
            canonical_url=canonical_url,
            title=title,
            sapo=sapo,
            content_text=content_text,
            author=author,
            language="vi",
            published_at=published_at,
            external_id=external_id,
            metadata={"source": self.code, **({"http_status": http_status} if http_status is not None else {})},
        )

    @staticmethod
    def _external_id(url: str) -> str | None:
        match = re.search(r"-(\d+)\.chn$", urlparse(url).path)
        return match.group(1) if match else None

    @staticmethod
    def _parse_published_at(soup: BeautifulSoup) -> datetime | None:
        node = soup.select_one(
            "[itemprop='datePublished'][datetime], meta[property='article:published_time'], "
            "[data-publish-date], time[datetime]"
        )
        raw = (node.get("datetime") or node.get("content") or node.get("data-publish-date")) if node else None
        if raw:
            try:
                value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                return value.replace(tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")) if value.tzinfo is None else value
            except ValueError:
                pass
        node = soup.select_one(".pdate, .detail-time, .time")
        raw = _text(node)
        if raw:
            match = re.search(r"(\d{1,2}[-/]\d{1,2}[-/]\d{4})\s*-?\s*(\d{1,2}:\d{2})", raw)
            if match:
                date_text, time_text = match.groups()
                return datetime.strptime(date_text.replace("-", "/") + " " + time_text, "%d/%m/%Y %H:%M").replace(
                    tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")
                )
        return None


class NewsSourceRegistry:
    def __init__(self, sources: list[NewsSource] | None = None) -> None:
        self._sources = sources or [CafeFNewsSource()]

    def resolve(self, url: str) -> NewsSource:
        for source in self._sources:
            if source.supports(url):
                return source
        host = urlparse(url).netloc or "unknown host"
        raise ValueError(f"No news source adapter is registered for {host}")

    def supports(self, url: str) -> bool:
        return any(source.supports(url) for source in self._sources)

    def codes(self) -> list[str]:
        return [source.code for source in self._sources]


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
