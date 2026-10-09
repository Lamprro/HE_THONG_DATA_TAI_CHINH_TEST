"""Vietnam macro observations from official APIs; no interpolation or annual-to-quarter conversion."""
from __future__ import annotations

import calendar
import csv
import io
import math
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import httpx

WORLD_BANK = {
    "NY.GDP.MKTP.CD": ("VN_GDP_CURRENT_USD", "GDP (current US$)", "USD"),
    "NY.GDP.MKTP.KD.ZG": ("VN_GDP_REAL_GROWTH_YOY", "GDP growth (annual %)", "%"),
    "FP.CPI.TOTL": ("VN_CPI_INDEX_2010", "Consumer price index (2010 = 100)", "INDEX_2010_100"),
    "FP.CPI.TOTL.ZG": ("VN_CPI_INFLATION_YOY", "Inflation, consumer prices (annual %)", "%"),
    "PA.NUS.FCRF": ("VN_OFFICIAL_USD_VND_YEAR_AVG", "Official exchange rate (LCU per US$, period average)", "VND_PER_USD"),
    "FR.INR.LEND": ("VN_LENDING_RATE_YEAR", "Lending interest rate (%)", "%"),
    "FR.INR.DPST": ("VN_DEPOSIT_RATE_YEAR", "Deposit interest rate (%)", "%"),
    "SL.UEM.TOTL.ZS": ("VN_UNEMPLOYMENT_ILO_ESTIMATE", "Unemployment, total (% of total labor force), modeled ILO estimate", "%"),
    "NE.EXP.GNFS.CD": ("VN_EXPORTS_GOODS_SERVICES_USD", "Exports of goods and services (current US$)", "USD"),
    "NE.IMP.GNFS.CD": ("VN_IMPORTS_GOODS_SERVICES_USD", "Imports of goods and services (current US$)", "USD"),
}
BIS_CODE = "VN_USD_VND_QUARTER_AVG"
SCHEMA = "macro_observations.v1"


class MacroUpstreamError(Exception):
    pass


def validate_window(country: str, start: date, end: date) -> None:
    if country != "VNM":
        raise ValueError("Only Vietnam (VNM) is supported")
    if start > end or start.year < 1960 or end.year - start.year > 20:
        raise ValueError("Invalid macro date window; maximum 20 calendar years")
    if end > datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date():
        raise ValueError("Macro end date must not be in the future")


def catalog(provider: str) -> list[dict]:
    if provider == "worldbank":
        return [dict(code=code, name=name, unit=unit, country_code="VNM", frequency="YEARLY",
                     provider=provider, source_indicator=indicator,
                     description="World Development Indicators; native annual observations. Publication/vintage date is not verified.")
                for indicator, (code, name, unit) in WORLD_BANK.items()]
    if provider == "bis":
        return [dict(code=BIS_CODE, name="VND per USD, quarterly average", unit="VND_PER_USD",
                     country_code="VNM", frequency="QUARTERLY", provider=provider,
                     source_indicator="BIS:WS_XRU(1.0)/Q.VN.VND.A",
                     description="BIS native quarterly period-average exchange rate; not a quarter-end spot quote. Publication/vintage date is not verified.")]
    raise ValueError("Supported macro providers: worldbank, bis")


def number(value) -> float:
    if isinstance(value, bool):
        raise MacroUpstreamError("Invalid boolean macro value")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise MacroUpstreamError("Invalid numeric macro observation") from None
    if not math.isfinite(result):
        raise MacroUpstreamError("Non-finite macro observation")
    return result


def normalize_worldbank(payload, start: date, end: date) -> list[dict]:
    if not isinstance(payload, list) or len(payload) != 2 or not isinstance(payload[0], dict) or not isinstance(payload[1], list):
        raise MacroUpstreamError("Unexpected World Bank response")
    if int(payload[0].get("pages", 0)) != 1:
        raise MacroUpstreamError("Incomplete World Bank pagination")
    series = {s["source_indicator"]: dict(s, observations=[], missing_periods=[]) for s in catalog("worldbank")}
    seen = set()
    for row in payload[1]:
        indicator = row.get("indicator", {}).get("id")
        if indicator not in series or row.get("countryiso3code") != "VNM":
            raise MacroUpstreamError("Unexpected country or indicator from World Bank")
        try:
            year = int(row["date"])
            period_end = date(year, 12, 31)
        except (KeyError, ValueError, TypeError):
            raise MacroUpstreamError("Invalid World Bank observation period") from None
        if not start <= period_end <= end:
            continue
        key = indicator, year
        if key in seen:
            raise MacroUpstreamError("Duplicate World Bank observation period")
        seen.add(key)
        if row.get("value") is None:
            series[indicator]["missing_periods"].append(str(year))
            continue
        series[indicator]["observations"].append(dict(period=str(year), observation_date=period_end.isoformat(),
            value=number(row["value"]), source_record=row))
    for item in series.values():
        item["observations"].sort(key=lambda r: r["observation_date"])
    return list(series.values())


def normalize_bis(body: str, start: date, end: date) -> list[dict]:
    reader = csv.DictReader(io.StringIO(body.lstrip('\ufeff')))
    required = {"FREQ", "REF_AREA", "CURRENCY", "COLLECTION", "TIME_PERIOD", "OBS_VALUE", "UNIT_MULT"}
    if not required.issubset(reader.fieldnames or []):
        raise MacroUpstreamError("Unexpected BIS CSV columns")
    result = dict(catalog("bis")[0], observations=[], missing_periods=[])
    seen = set()
    for row in reader:
        if (row["FREQ"], row["REF_AREA"], row["CURRENCY"], row["COLLECTION"]) != ("Q", "VN", "VND", "A") or row["UNIT_MULT"] != "0":
            raise MacroUpstreamError("Unexpected BIS series or unit multiplier")
        try:
            year, quarter = row["TIME_PERIOD"].split("-Q")
            year, quarter = int(year), int(quarter)
            if quarter not in (1, 2, 3, 4):
                raise ValueError()
            month = quarter * 3
            period_end = date(year, month, calendar.monthrange(year, month)[1])
        except (ValueError, KeyError):
            raise MacroUpstreamError("Invalid BIS quarter") from None
        if not start <= period_end <= end:
            continue
        if period_end in seen:
            raise MacroUpstreamError("Duplicate BIS observation period")
        seen.add(period_end)
        if not row["OBS_VALUE"].strip():
            result["missing_periods"].append(row["TIME_PERIOD"])
            continue
        value = number(row["OBS_VALUE"])
        if value <= 0:
            raise MacroUpstreamError("Exchange rate must be positive")
        result["observations"].append(dict(period=row["TIME_PERIOD"], observation_date=period_end.isoformat(),
            value=value, source_record=row))
    result["observations"].sort(key=lambda r: r["observation_date"])
    return [result]


def observations(provider: str, country: str, start: date, end: date, client: httpx.Client | None = None) -> dict:
    validate_window(country, start, end)
    catalog(provider)
    own_client = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(25.0, connect=5.0), follow_redirects=False)
    try:
        if provider == "worldbank":
            url = "https://api.worldbank.org/v2/country/VNM/indicator/" + ";".join(WORLD_BANK)
            response = client.get(url, params=dict(source=2, date=f"{start.year}:{end.year}", format="json", per_page=2000))
            response.raise_for_status()
            data = normalize_worldbank(response.json(), start, end)
        else:
            url = "https://stats.bis.org/api/v1/data/WS_XRU/Q.VN.VND.A"
            response = client.get(url, params=dict(startPeriod=f"{start.year}-Q1", endPeriod=f"{end.year}-Q4"),
                headers={"Accept": "application/vnd.sdmx.data+csv;version=1.0.0"})
            response.raise_for_status()
            data = normalize_bis(response.text, start, end)
        count = sum(len(s["observations"]) for s in data)
        if count == 0:
            raise MacroUpstreamError("No published Vietnam observations in the requested window")
        return dict(schema_version=SCHEMA, dataset="MACRO", provider=provider, country_code=country,
            start_date=start.isoformat(), end_date=end.isoformat(), source_url=str(response.url),
            retrieved_at=datetime.now(timezone.utc).isoformat(), count=len(data), observation_count=count, data=data,
            limitations=["Native source frequency retained; no interpolation, annual-to-quarter allocation, or filling missing values.",
                          "Observation date is period end, not verified publication date; historical backtest availability is not established."])
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise MacroUpstreamError("Macro upstream request or response failed") from exc
    finally:
        if own_client:
            client.close()
