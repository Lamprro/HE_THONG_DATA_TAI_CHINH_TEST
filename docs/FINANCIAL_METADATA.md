# Financial metadata contract — 12/10/2026

The three existing financial endpoint families (VNDirect, CafeF, VnStock) add
`financial_metadata` without changing `data`, values, counts or endpoint paths.
The contract is `financial.metadata.v1`: provider, optional source_url, report_scope,
currency, unit_scale, published_at, period_basis, evidence and limitations. VNDirect
fiscalDate groups also receive a `periods` map keyed by fiscal date, so publication
dates from different periods cannot be merged into one guessed date.

Known values require explicit source fields. `formType=ALL`, numeric form types,
company form and model identifiers do not prove CONSOLIDATED/SEPARATE. createdDate,
modifiedDate, fiscalDate and retrieved_at do not prove publication. Missing or
conflicting fields remain UNKNOWN/null with reasons and preserved raw values.
Balance sheet basis is POINT_IN_TIME; explicit YEAR/ANNUAL report types establish
ANNUAL for flow statements. QUARTER alone does not establish standalone versus YTD.

CafeF metadata inspects report headings/captions and explicit unit labels in the
same fetched HTML; navigation links do not establish scope. Units such as nghìn/triệu
đồng are preserved as currency=VND and unit_scale=1000/1000000. Numeric values stay
in their original source scale; the Java consumer multiplies by scale where needed.
The current VNDirect FPT Q2/2026 response has createdDate/modifiedDate and formType=ALL,
but no verified currency/scale/publication/scope. These remain unknown, not fabricated.

Verification: 16 unittest tests pass (12/10/2026); API tests use mocked providers.
Existing VNDirect provider was also called for FPT Q2/2026 read-only to inspect fields.
Java receives the contract through the existing external adapter and ingestion pipeline;
this Python service does not write the business DB. No historical metadata is guessed.
