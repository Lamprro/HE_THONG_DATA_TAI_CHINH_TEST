from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence


MARKET_SCHEMA_VERSION = "market_price.v1"
MARKET_DATASETS = frozenset({"equity_ohlcv", "equity_quote"})


def market_contract_metadata() -> dict[str, Any]:
    return {
        "schema_version": MARKET_SCHEMA_VERSION,
        "normalization": {
            "currency": "VND",
            "price_unit": "VND",
            "trading_value_unit": "VND",
            "volume_unit": "shares",
            "trading_timezone": "Asia/Ho_Chi_Minh",
            "interval_codes": {
                "equity_ohlcv": "1d",
                "equity_quote": "snapshot",
            },
            "daily_timestamp_semantics": "start_of_trading_date",
            "quote_timestamp_semantics": "retrieved_snapshot",
            "source_record_path": "data[].source_record",
        },
    }


def normalize_market_records(
    provider: str,
    dataset: str,
    symbol: str,
    records: Sequence[Mapping[str, Any]],
    observed_at: str | None = None,
) -> list[dict[str, Any]]:
    if dataset not in MARKET_DATASETS:
        return [dict(record) for record in records]

    normalized_provider = provider.strip().lower()
    if normalized_provider not in {"vnstock", "cafef"}:
        raise ValueError(f"Unsupported market-data provider: {provider}")

    return [
        _normalize_record(normalized_provider, dataset, symbol, record, observed_at)
        for record in records
    ]


def _normalize_record(
    provider: str,
    dataset: str,
    symbol: str,
    source: Mapping[str, Any],
    observed_at: str | None,
) -> dict[str, Any]:
    if provider == "vnstock":
        return _normalize_vnstock(dataset, symbol, source, observed_at)
    return _normalize_cafef(dataset, symbol, source, observed_at)


def _normalize_vnstock(
    dataset: str,
    symbol: str,
    source: Mapping[str, Any],
    observed_at: str | None,
) -> dict[str, Any]:
    price_multiplier = Decimal("1000") if dataset == "equity_ohlcv" else Decimal("1")
    trading_date = _parse_date(_first(source, "trading_date", "time", "date"))

    return _canonical_record(
        provider="vnstock",
        dataset=dataset,
        symbol=_first(source, "symbol") or symbol,
        trading_date=trading_date,
        open_price=_scaled(_first(source, "open", "open_price"), price_multiplier),
        high_price=_scaled(_first(source, "high", "high_price"), price_multiplier),
        low_price=_scaled(_first(source, "low", "low_price"), price_multiplier),
        close_price=_scaled(_first(source, "close", "close_price"), price_multiplier),
        adjusted_close=_scaled(
            _first(source, "adjusted_close", "adjusted_close_price"), price_multiplier
        ),
        reference_price=_scaled(_first(source, "reference_price"), Decimal("1")),
        ceiling_price=_scaled(_first(source, "ceiling_price"), Decimal("1")),
        floor_price=_scaled(_first(source, "floor_price"), Decimal("1")),
        volume=_scaled(_first(source, "volume", "volume_accumulated"), Decimal("1")),
        trading_value=_scaled(_first(source, "trading_value", "total_value"), Decimal("1")),
        foreign_buy_volume=_scaled(_first(source, "foreign_buy_volume"), Decimal("1")),
        foreign_sell_volume=_scaled(_first(source, "foreign_sell_volume"), Decimal("1")),
        put_through_volume=None,
        put_through_value=None,
        observed_at=observed_at,
        source=source,
    )


def _normalize_cafef(
    dataset: str,
    symbol: str,
    source: Mapping[str, Any],
    observed_at: str | None,
) -> dict[str, Any]:
    # CafeF quote is the latest daily OHLCV row and uses the same units, but keep
    # the requested dataset name so downstream lineage still distinguishes the route.
    price_multiplier = Decimal("1000")
    value_multiplier = Decimal("1000000000")
    trading_date = _parse_date(_first(source, "Ngay", "trading_date", "time", "date"))

    return _canonical_record(
        provider="cafef",
        dataset=dataset,
        symbol=_first(source, "Symbol", "symbol") or symbol,
        trading_date=trading_date,
        open_price=_scaled(_first(source, "GiaMoCua", "open", "open_price"), price_multiplier),
        high_price=_scaled(_first(source, "GiaCaoNhat", "high", "high_price"), price_multiplier),
        low_price=_scaled(_first(source, "GiaThapNhat", "low", "low_price"), price_multiplier),
        close_price=_scaled(_first(source, "GiaDongCua", "close", "close_price"), price_multiplier),
        adjusted_close=_scaled(_first(source, "GiaDieuChinh", "adjusted_close"), price_multiplier),
        reference_price=None,
        ceiling_price=None,
        floor_price=None,
        volume=_scaled(_first(source, "KhoiLuongKhopLenh", "volume"), Decimal("1")),
        trading_value=_scaled(_first(source, "GiaTriKhopLenh", "trading_value"), value_multiplier),
        foreign_buy_volume=None,
        foreign_sell_volume=None,
        put_through_volume=_scaled(_first(source, "KLThoaThuan"), Decimal("1")),
        put_through_value=_scaled(_first(source, "GtThoaThuan"), value_multiplier),
        observed_at=observed_at,
        source=source,
    )


def _canonical_record(
    *,
    provider: str,
    dataset: str,
    symbol: Any,
    trading_date: date | None,
    open_price: int | float | None,
    high_price: int | float | None,
    low_price: int | float | None,
    close_price: int | float | None,
    adjusted_close: int | float | None,
    reference_price: int | float | None,
    ceiling_price: int | float | None,
    floor_price: int | float | None,
    volume: int | float | None,
    trading_value: int | float | None,
    foreign_buy_volume: int | float | None,
    foreign_sell_volume: int | float | None,
    put_through_volume: int | float | None,
    put_through_value: int | float | None,
    observed_at: str | None,
    source: Mapping[str, Any],
) -> dict[str, Any]:
    warnings: list[str] = []
    if trading_date is None:
        warnings.append("missing_trading_date")
    if close_price is None:
        warnings.append("missing_close_price")

    trading_date_text = trading_date.isoformat() if trading_date else None
    if dataset == "equity_quote":
        interval_code = "snapshot"
        record_type = "QUOTE_SNAPSHOT"
        price_timestamp = _parse_timestamp(observed_at)
        timestamp_semantics = "retrieved_snapshot"
        if price_timestamp is None:
            warnings.append("missing_observed_at")
    else:
        interval_code = "1d"
        record_type = "DAILY_CANDLE"
        price_timestamp = (
            f"{trading_date_text}T00:00:00+07:00" if trading_date_text else None
        )
        timestamp_semantics = "start_of_trading_date"

    return {
        "symbol": str(symbol).strip().upper(),
        "provider": provider,
        "dataset": dataset,
        "record_type": record_type,
        "trading_date": trading_date_text,
        "price_timestamp": price_timestamp,
        "timestamp_semantics": timestamp_semantics,
        "interval_code": interval_code,
        "currency": "VND",
        "open_price": open_price,
        "high_price": high_price,
        "low_price": low_price,
        "close_price": close_price,
        "adjusted_close": adjusted_close,
        "reference_price": reference_price,
        "ceiling_price": ceiling_price,
        "floor_price": floor_price,
        "volume": volume,
        "trading_value": trading_value,
        "foreign_buy_volume": foreign_buy_volume,
        "foreign_sell_volume": foreign_sell_volume,
        "put_through_volume": put_through_volume,
        "put_through_value": put_through_value,
        "normalization_warnings": warnings,
        "source_record": dict(source),
    }


def _first(source: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        value = source.get(name)
        if value is not None and value != "":
            return value
    return None


def _scaled(value: Any, multiplier: Decimal) -> int | float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value).strip()) * multiplier
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not number.is_finite():
        return None
    integral = number.to_integral_value()
    if number == integral:
        return int(integral)
    return float(number)


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None

    for parser in (
        lambda raw: datetime.strptime(raw, "%d/%m/%Y").date(),
        lambda raw: datetime.fromisoformat(raw.replace("Z", "+00:00")).date(),
        lambda raw: date.fromisoformat(raw[:10]),
    ):
        try:
            return parser(text)
        except (ValueError, TypeError):
            continue
    return None


def _parse_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.isoformat()
