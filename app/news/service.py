from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.core.config import database_url
from app.news.company_matcher import news_company_matcher
from app.news.models import RawNewsPayload
from app.news.sources import NewsSourceRegistry, canonicalize_url, sha256


class NewsPipelineError(RuntimeError):
    pass


class NewsPipelineService:
    def __init__(self, registry: NewsSourceRegistry | None = None) -> None:
        self.registry = registry or NewsSourceRegistry()

    def _connect(self):
        dsn = database_url()
        if not dsn:
            raise NewsPipelineError("DATABASE_URL (or POSTGRES_DSN) is not configured")
        return psycopg.connect(dsn, row_factory=dict_row)

    def status(self) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT enabled, updated_at FROM news_crawl_controls WHERE id = true")
            row = cur.fetchone()
        if row is None:
            return {"enabled": False, "configured": True, "message": "Run the NEWS pipeline migration first"}
        return {"enabled": row["enabled"], "configured": True, "updated_at": row["updated_at"], "sources": self.registry.codes()}

    def set_enabled(self, enabled: bool) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO news_crawl_controls (id, enabled) VALUES (true, %s)
                   ON CONFLICT (id) DO UPDATE SET enabled = EXCLUDED.enabled, updated_at = now()
                   RETURNING enabled, updated_at""",
                (enabled,),
            )
            row = cur.fetchone()
        return {"enabled": row["enabled"], "updated_at": row["updated_at"], "sources": self.registry.codes()}

    def list_articles(self, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) AS total FROM news_articles")
            total = cur.fetchone()["total"]
            cur.execute(
                """
                SELECT id::text, data_source_id, raw_payload_id::text, external_id,
                       canonical_url, title, sapo, content_text, author, language,
                       published_at, crawled_at, content_hash, dedup_status, metadata,
                       created_at, updated_at
                FROM news_articles
                ORDER BY crawled_at DESC, id DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            articles = cur.fetchall()
        return {"total": total, "limit": limit, "offset": offset, "count": len(articles), "data": articles}

    def match_existing_articles(self, limit: int = 100) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text FROM news_articles
                    ORDER BY crawled_at DESC, id DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                article_ids = [row["id"] for row in cur.fetchall()]
            result = {"processed": 0, "matched_articles": 0, "company_matches": 0}
            for article_id in article_ids:
                with conn.transaction():
                    count = news_company_matcher.match_article(conn, article_id)
                result["processed"] += 1
                result["company_matches"] += count
                if count:
                    result["matched_articles"] += 1
            conn.commit()
        return result

    def list_company_matches(self, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) AS total FROM news_article_companies")
            total = cur.fetchone()["total"]
            cur.execute(
                """
                SELECT match.news_article_id::text, article.title, article.canonical_url,
                       match.company_id::text, company.company_code, company.short_name,
                       match.security_id::text, security.symbol, match.relevance_score,
                       match.match_method, match.created_at
                FROM news_article_companies match
                JOIN news_articles article ON article.id = match.news_article_id
                JOIN companies company ON company.id = match.company_id
                LEFT JOIN securities security ON security.id = match.security_id
                ORDER BY match.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = cur.fetchall()
        return {"total": total, "limit": limit, "offset": offset, "count": len(rows), "data": rows}

    def run_once(self, limit: int = 100) -> dict[str, Any]:
        """Process approved NEWS URLs. A PostgreSQL advisory lock avoids duplicate multi-replica runs."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(hashtext('news-pipeline-v1')) AS acquired")
                if not cur.fetchone()["acquired"]:
                    return {"status": "skipped", "reason": "another news pipeline run is active", "processed": 0, "inserted": 0, "failed": 0}
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT enabled FROM news_crawl_controls WHERE id = true")
                    control = cur.fetchone()
                if not control or not control["enabled"]:
                    return {"status": "skipped", "reason": "news pipeline is disabled", "processed": 0, "inserted": 0, "failed": 0}
                result = self._process(conn, limit)
                conn.commit()
                return result
            finally:
                # A query outside an item-level SAVEPOINT can still fail (for
                # example a schema mismatch). Roll back that failed transaction
                # before issuing the session-level advisory unlock query.
                conn.rollback()
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(hashtext('news-pipeline-v1'))")

    def _process(self, conn, limit: int) -> dict[str, Any]:
        raw_payloads = self._pending_payloads(conn, limit)
        result: dict[str, Any] = {"status": "completed", "limit": limit, "raw_payloads": len(raw_payloads), "processed": 0, "inserted": 0, "duplicates": 0, "failed": 0, "company_matches": 0, "errors": []}
        for raw in raw_payloads:
            for url in self._urls_from_raw(raw):
                if result["processed"] >= limit:
                    return result
                result["processed"] += 1
                try:
                    # A nested transaction is a PostgreSQL SAVEPOINT here.  An
                    # insert failure for one URL must not leave the batch's
                    # outer transaction in the "aborted" state.
                    with conn.transaction():
                        if self._article_exists(conn, url):
                            result["duplicates"] += 1
                            continue
                        article = self.registry.resolve(url).fetch_article(url)
                    article_id = self._insert_article(conn, raw, article)
                    if article_id is None:
                        result["duplicates"] += 1
                    else:
                        result["inserted"] += 1
                        result["company_matches"] += news_company_matcher.match_article(conn, article_id)
                except Exception as exc:
                    result["failed"] += 1
                    result["errors"].append({"raw_payload_id": raw.id, "url": url, "error": str(exc)})
        return result

    @staticmethod
    def _article_exists(conn, url: str) -> bool:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM news_articles WHERE url_hash = %s) AS exists",
                (sha256(canonicalize_url(url)),),
            )
            return cur.fetchone()["exists"]

    @staticmethod
    def _pending_payloads(conn, limit: int) -> list[RawNewsPayload]:
        query = """
            SELECT rp.id::text, rp.data_source_id, rp.source_url, rp.payload,
                   rp.raw_text, rp.published_at
            FROM raw_payloads rp
            WHERE upper(rp.entity_type) = 'NEWS'
              AND EXISTS (
                  SELECT 1 FROM validation_results vr
                  WHERE vr.raw_payload_id = rp.id AND vr.result_status = 'PASS'
              )
            ORDER BY rp.fetched_at ASC
            LIMIT %s
        """
        with conn.cursor() as cur:
            cur.execute(query, (limit,))
            return [RawNewsPayload(**row) for row in cur.fetchall()]

    def _urls_from_raw(self, raw: RawNewsPayload) -> list[str]:
        values: list[str] = []
        if raw.source_url:
            values.append(raw.source_url)

        def visit(value: Any) -> Iterator[str]:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key.lower() in {"url", "link", "source_url", "canonical_url"} and isinstance(item, str):
                        yield item
                    yield from visit(item)
            elif isinstance(value, list):
                for item in value:
                    yield from visit(item)

        values.extend(visit(raw.payload))
        if raw.raw_text:
            try:
                values.extend(visit(json.loads(raw.raw_text)))
            except json.JSONDecodeError:
                pass
        normalized: list[str] = []
        for value in values:
            try:
                url = canonicalize_url(value)
            except ValueError:
                continue
            # raw_payload.source_url can be the upstream listing/API endpoint
            # which produced the payload, not an article. Process only article
            # hosts for which a source adapter has been registered.
            if self.registry.supports(url) and url not in normalized:
                normalized.append(url)
        return normalized

    @staticmethod
    def _insert_article(conn, raw: RawNewsPayload, article) -> str | None:
        content_hash = sha256(article.content_text)
        url_hash = sha256(article.canonical_url)
        metadata = {**article.metadata, "raw_payload_published_at": raw.published_at.isoformat() if raw.published_at else None}
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO news_articles (
                    data_source_id, raw_payload_id, external_id, canonical_url, url_hash,
                    title, sapo, content_text, author, language, published_at,
                    content_hash, metadata
                ) VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (url_hash) WHERE url_hash IS NOT NULL DO NOTHING
                RETURNING id""",
                (raw.data_source_id, raw.id, article.external_id, article.canonical_url, url_hash,
                 article.title, article.sapo, article.content_text, article.author, article.language,
                 article.published_at or raw.published_at, content_hash, json.dumps(metadata)),
            )
            row = cur.fetchone()
            return row["id"] if row else None


news_pipeline_service = NewsPipelineService()
