# News fetch API

This Python service acts as a third-party data provider for the Spring Boot application. It does not connect to the Spring Boot database or write news articles, validation results, or company/security relationships.

`GET /api/v1/cafef/equities/{symbol}/news` returns CafeF news-list items, including each item's URL and `publishedAt` value.

`GET /api/v1/url-fetch?url=...` retrieves an article page from a registered publisher host and returns the source HTTP status, content type, final URL, page body, and retrieval time. Only supported hosts are accepted. The endpoint does not store the response.

Spring Boot owns ingestion, validation, article extraction and persistence, deduplication, and company/security relationships. The old Python database-backed news pipeline, scheduler, and company matcher have been removed.
