# News fetch API

This Python service acts as a third-party data provider for the Spring Boot application. It does not connect to the Spring Boot database or write news articles, validation results, or company/security relationships.

`GET /api/v1/cafef/equities/{symbol}/news` returns CafeF news-list items, including each item's URL and `publishedAt` value.

`GET /api/v1/url-fetch?url=...` retrieves an article page from a registered publisher host and returns the source HTTP status, content type, final URL, raw page body, and retrieval time. For a successful HTML page it also uses the registered publisher parser to return `extraction_status`, `canonical_url`, `title`, `sapo`, `content_text`, `author`, and `published_at`. A missing article container is reported as `extraction_status=FAILED` with `extraction_error`; it is never silently replaced with whole-page text. The same HTTP response is parsed without fetching the page twice. Publisher dates without an explicit offset are interpreted in `Asia/Ho_Chi_Minh`; `retrieved_at` also has a Vietnam offset. The endpoint does not store the response.

Spring Boot owns ingestion, validation, article persistence, deduplication, and company/security relationships. It keeps each listing item's `publishedAt` with its URL and uses the publisher date when available, with the listing date as fallback. The old Python database-backed news pipeline, scheduler, and company matcher have been removed.
