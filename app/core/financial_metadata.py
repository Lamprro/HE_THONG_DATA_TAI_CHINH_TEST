"""Financial metadata from explicit source fields; fiscal/created dates are not publication dates."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
import re
import unicodedata


def _plain(value):
    return unicodedata.normalize("NFKD", str(value).replace("đ", "d").replace("Đ", "D")).encode("ascii", "ignore").decode().lower().strip()


def _scope(value):
    text = _plain(value)
    if text in {"consolidated", "hop nhat"} or re.search(r"\bhop nhat\b", text):
        return "CONSOLIDATED"
    if text in {"separate", "standalone", "rieng le"} or re.search(r"\brieng le\b", text):
        return "SEPARATE"
    return None  # ALL and numeric formType are not a verified consolidation scope.


def _currency(value):
    text = _plain(value).upper()
    if text in {"VND", "USD", "EUR"}:
        return text
    if re.search(r"\b(vnd|dong)\b", text.lower()):
        return "VND"
    return None


def _scale(value):
    text = _plain(value)
    if text in {"1", "1000", "1000000", "1000000000"}:
        return int(text)
    for word, scale in (("ty", 1000000000), ("trieu", 1000000), ("nghin", 1000), ("ngan", 1000)):
        if re.search(rf"\b{word}\b", text):
            return scale
    return 1 if text in {"vnd", "dong", "usd", "eur"} else None


def _published(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        return parsed.isoformat()
    except (ValueError, TypeError):
        return None


def financial_metadata(df, dataset: str, provider: str, *, _per_period=True) -> dict:
    from app.core.serialization import dataframe_to_records
    rows = dataframe_to_records(df)
    supplied = dict(getattr(df, "attrs", {}).get("financial_metadata", {})) if df is not None else {}
    candidates = [supplied, *rows]
    fields = {
        "report_scope": (("report_scope", "reportScope", "formType", "modelVnDesc"), _scope),
        "currency": (("currency", "currencyCode", "unit"), _currency),
        "unit_scale": (("unit_scale", "unitScale", "unit"), _scale),
        "published_at": (("published_at", "publishedAt", "announcementDate", "publicationDate"), _published),
        "period_basis": (("period_basis", "periodBasis"), lambda v: str(v) if str(v) in
                         {"POINT_IN_TIME", "STANDALONE_QUARTER", "YTD", "ANNUAL"} else None),
        "revision_status": (("isRestated", "is_restated"), lambda v:
                            "RESTATED" if v is True else "ORIGINAL" if v is False else None),
        "revision_published_at": (("revisionPublishedAt", "restatementPublishedAt"), _published),
    }
    result = {"schema_version": "financial.metadata.v1", "provider": provider,
              "report_scope": "UNKNOWN", "currency": None, "unit_scale": None,
              "published_at": None, "period_basis": "UNKNOWN", "evidence": {}, "limitations": []}
    result.update(revision_status="UNKNOWN",revision_published_at=None,publication_precision="UNKNOWN")
    if supplied.get("source_url"):
        result["source_url"] = supplied["source_url"]
    for field, (aliases, normalize) in fields.items():
        evidence = []
        values = set()
        for row in candidates:
            for key in aliases:
                if row.get(key) is None:
                    continue
                normalized = normalize(row[key])
                if normalized is not None:
                    values.add(normalized)
                    entry = {"field": key, "value": row[key], "normalized": normalized}
                    if entry not in evidence:
                        evidence.append(entry)
        result["evidence"][field] = evidence
        if len(values) == 1:
            result[field] = values.pop()
        elif len(values) > 1:
            result["limitations"].append(f"CONFLICTING_{field.upper()}: preserve raw fields; no aggregate assumption")
    if dataset == "balance_sheet":
        result["period_basis"] = "POINT_IN_TIME"
        result["evidence"]["period_basis"] = [{"field": "dataset", "value": dataset, "normalized": "POINT_IN_TIME"}]
    elif rows and all(row.get("reportType") in {"YEAR", "ANNUAL", "YEARLY"} for row in rows):
        result["period_basis"] = "ANNUAL"
        result["evidence"]["period_basis"] = [{"field": "reportType", "value": rows[0]["reportType"], "normalized": "ANNUAL"}]
    if result["published_at"] is not None:
        source_dates=result["evidence"]["published_at"]
        result["publication_precision"] = ("DAY" if any(re.fullmatch(r"\d{4}-\d{2}-\d{2}",str(e["value"])) for e in source_dates) else "DATETIME")
    for field in fields:
        if result[field] in (None, "UNKNOWN"):
            result["limitations"].append(f"UNVERIFIED_{field.upper()}")
    if _per_period and df is not None and "fiscalDate" in df.columns:
        result["periods"] = {str(period): financial_metadata(group, dataset, provider, _per_period=False)
                             for period, group in df.groupby("fiscalDate", sort=True)}
    return result


def cafef_metadata(html: str, source_url: str, dataset: str) -> dict:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    # Inspect report headings/captions only; company navigation and historical report links are not evidence.
    headings = " ".join(node.get_text(" ", strip=True) for node in soup.select("h1, #tableContent caption"))
    unit = None
    for node in soup.find_all(string=re.compile(r"Đơn vị\s*(?:tính)?\s*:", re.I)):
        match = re.search(r"Đơn vị\s*(?:tính)?\s*:\s*((?:nghìn|ngàn|triệu|tỷ)?\s*(?:đồng|VND|USD|EUR))", str(node), re.I)
        if match:
            candidate = match.group(1).strip()
            if unit is not None and unit != candidate:
                unit = None
                break
            unit = candidate
    return {"source_url": source_url, "report_scope": _scope(headings) or "UNKNOWN", "unit": unit}
