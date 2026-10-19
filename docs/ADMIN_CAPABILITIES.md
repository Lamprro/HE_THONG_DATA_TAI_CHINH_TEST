# Admin source contract — 2026-10-19

`GET /api/v1/capabilities` lists routes from the running FastAPI application and
documents the historical-ratio/foreign-trade/native-index/macro contracts.
Java exposes it through the existing adapter as
`GET /api/external-financial-data/capabilities` (`CAPABILITIES` operation).

The admin browser talks to Java. Python stays stateless: it does not own database
cleanup, job scheduling, validation, canonical builds or administrator audit.
Route registration does not prove provider availability, credentials, quota,
publication provenance or ten years of complete observations.

Verification: 24 Python unittest tests passed, including the new deployed-route
contract check. Provider transport tests use mocks and do not prove live coverage.
The Java admin acceptance separately calls a real historical FPT source request.
No LLM implementation or financial transformation was changed here.
