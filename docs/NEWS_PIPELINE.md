# NEWS pipeline

## What was added

- `app/news/sources.py`: source-adapter contract plus the first `CafeFNewsSource`. It downloads an article URL, strips non-content HTML and maps its title, sapo, body, author, publication time and CafeF article ID to a normalized article. Add another publisher by implementing `NewsSource` and registering it in `NewsSourceRegistry`; no pipeline or API route changes are required.
- `app/news/service.py`: selects `raw_payloads` with `entity_type = NEWS` only when at least one associated `validation_results.result_status = PASS`, obtains URLs from `source_url`, JSON `payload` and JSON `raw_text`, deduplicates by SHA-256 canonical URL, and inserts into `news_articles`.
- `app/news/company_matcher.py`: deterministic ticker/company-alias matching from `companies`, `company_aliases`, and `securities` into `news_article_companies`. New articles are matched immediately after insertion.
- `app/news/scheduler.py`: starts with FastAPI and attempts its first run after 900 seconds (15 minutes), then every 15 minutes. It obeys the persistent enabled flag and uses a PostgreSQL advisory lock, so overlapping manual/scheduled runs and multiple service replicas do not process the same run concurrently.
- `app/api/v1/news_pipeline.py`: Swagger endpoints for status, enable/disable, and manual execution.

## Setup

1. Install dependencies: `pip install -r requirements.txt`.
2. Configure PostgreSQL only on the service host: `DATABASE_URL=postgresql://user:password@host:5432/database`.
3. Ensure the NEWS pipeline database migration has been applied after the existing `database.sql` schema. The current shared database has already been migrated.
4. Start FastAPI as usual. The scheduler is loaded but starts disabled by default, so a deployment cannot crawl unexpectedly.

`NEWS_CRAWLER_INTERVAL_SECONDS` can change the interval for an environment; default is `900` and the application enforces a minimum of 60 seconds.

## Swagger endpoints

All endpoints are under `/api/v1/news-pipeline`.

| Method and path | Purpose | Main response |
| --- | --- | --- |
| `GET /status` | Shows the persisted on/off state and registered source codes. | `enabled`, `updated_at`, `sources` |
| `PUT /control` | Persists the crawler switch. Body: `{ "enabled": true }` or `{ "enabled": false }`. | updated `enabled`, `updated_at`, `sources` |
| `POST /runs?limit=100` | Runs the approved NEWS pipeline immediately. It still respects the switch. `limit` is the maximum number of article URLs processed in this run. | `status`, `raw_payloads`, `processed`, `inserted`, `duplicates`, `failed`, `errors` |
| `GET /articles?limit=20&offset=0` | Lists the normalized rows currently stored in `news_articles`. | `total`, pagination fields, and `data` containing article fields |
| `POST /company-matches/runs?limit=100` | Runs rule-based matching for articles already stored in `news_articles`. | `processed`, `matched_articles`, `company_matches` |
| `GET /company-matches?limit=20&offset=0` | Lists the article-to-company/security links created by the matcher. | `total`, pagination fields, and match data |

Responses are `503` when `DATABASE_URL` is absent/unreachable or the migration has not been applied. A disabled pipeline returns a successful `skipped` response from `POST /runs`; call `PUT /control` with `enabled: true` first.

## Data behavior

The pipeline does not use validation result order: one `PASS` associated with a raw payload is sufficient. It never processes `FAIL`/`SKIP`-only payloads. The same article is not inserted twice because the existing unique `news_articles.url_hash` index is used; previously stored URLs are checked before the source page is downloaded. A payload can contain a list such as `{ "data": [{ "url": "..." }] }`, which is handled directly. Listing/API URLs that produced the raw payload are ignored unless their host has a registered article-source adapter.

The scheduler is in-process, appropriate for a persistent FastAPI worker. For serverless deployments that do not keep a process alive, trigger `POST /runs` from the platform's external cron instead.

`news_ai_analyses` is deliberately not populated by this ingestion pipeline: it requires a separate AI enrichment stage. Company matching is rule-based and uses aliases/tickers already present in the database; improving `company_aliases` (especially `NEWS_ALIAS`) improves matching accuracy.
