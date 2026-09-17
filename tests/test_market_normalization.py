from __future__ import annotations

import unittest

from app.core.market_normalization import (
    MARKET_SCHEMA_VERSION,
    market_contract_metadata,
    normalize_market_records,
)


class MarketNormalizationTests(unittest.TestCase):
    def test_vnstock_daily_prices_are_converted_from_thousand_vnd(self) -> None:
        result = normalize_market_records(
            "vnstock",
            "equity_ohlcv",
            "FPT",
            [
                {
                    "time": "2026-08-03T07:00:00.000",
                    "open": 67.4,
                    "high": 71.7,
                    "low": 67.3,
                    "close": 71.7,
                    "volume": 16_279_100,
                }
            ],
        )[0]

        self.assertEqual(result["trading_date"], "2026-08-03")
        self.assertEqual(result["price_timestamp"], "2026-08-03T00:00:00+07:00")
        self.assertEqual(result["record_type"], "DAILY_CANDLE")
        self.assertEqual(result["interval_code"], "1d")
        self.assertEqual(result["open_price"], 67_400)
        self.assertEqual(result["close_price"], 71_700)
        self.assertEqual(result["volume"], 16_279_100)
        self.assertEqual(result["normalization_warnings"], [])

    def test_vnstock_quote_prices_remain_in_vnd(self) -> None:
        result = normalize_market_records(
            "vnstock",
            "equity_quote",
            "FPT",
            [
                {
                    "symbol": "FPT",
                    "trading_date": "2026-08-28",
                    "open_price": 72_200,
                    "high_price": 74_000,
                    "low_price": 72_200,
                    "close_price": 73_200,
                    "reference_price": 72_200,
                    "ceiling_price": 77_200,
                    "floor_price": 67_200,
                    "volume_accumulated": 10_196_800,
                    "total_value": 749_755_960_000,
                    "foreign_buy_volume": 4_443_191,
                    "foreign_sell_volume": 1_164_400,
                }
            ],
            observed_at="2026-08-31T04:45:55+00:00",
        )[0]

        self.assertEqual(result["record_type"], "QUOTE_SNAPSHOT")
        self.assertEqual(result["interval_code"], "snapshot")
        self.assertEqual(result["price_timestamp"], "2026-08-31T04:45:55+00:00")
        self.assertEqual(result["close_price"], 73_200)
        self.assertEqual(result["trading_value"], 749_755_960_000)
        self.assertEqual(result["foreign_buy_volume"], 4_443_191)
        self.assertEqual(result["source_record"]["close_price"], 73_200)

    def test_cafef_prices_and_values_are_converted_to_vnd(self) -> None:
        result = normalize_market_records(
            "cafef",
            "equity_quote",
            "FPT",
            [
                {
                    "Ngay": "28/08/2026",
                    "Symbol": "FPT",
                    "GiaMoCua": 72.2,
                    "GiaCaoNhat": 74.0,
                    "GiaThapNhat": 72.2,
                    "GiaDongCua": 73.2,
                    "GiaDieuChinh": 73.2,
                    "GiaTriKhopLenh": 749.76,
                    "KhoiLuongKhopLenh": 10_196_800,
                    "GtThoaThuan": 252.19,
                    "KLThoaThuan": 3_305_900,
                }
            ],
            observed_at="2026-08-31T09:25:03+00:00",
        )[0]

        self.assertEqual(result["record_type"], "QUOTE_SNAPSHOT")
        self.assertEqual(result["interval_code"], "snapshot")
        self.assertEqual(result["trading_date"], "2026-08-28")
        self.assertEqual(result["close_price"], 73_200)
        self.assertEqual(result["adjusted_close"], 73_200)
        self.assertEqual(result["trading_value"], 749_760_000_000)
        self.assertEqual(result["put_through_value"], 252_190_000_000)
        self.assertEqual(result["put_through_volume"], 3_305_900)

    def test_missing_trading_date_is_explicitly_reported(self) -> None:
        result = normalize_market_records(
            "vnstock",
            "equity_quote",
            "FPT",
            [{"symbol": "FPT", "close_price": 73_200}],
            observed_at="2026-08-31T04:45:55+00:00",
        )[0]

        self.assertEqual(result["price_timestamp"], "2026-08-31T04:45:55+00:00")
        self.assertIn("missing_trading_date", result["normalization_warnings"])

    def test_quote_and_ohlcv_use_the_same_record_shape(self) -> None:
        daily = normalize_market_records(
            "vnstock",
            "equity_ohlcv",
            "FPT",
            [{"time": "2026-08-28", "close": 73.2}],
        )[0]
        quote = normalize_market_records(
            "cafef",
            "equity_quote",
            "FPT",
            [{"Ngay": "28/08/2026", "GiaDongCua": 73.2}],
            observed_at="2026-08-28T08:00:00+00:00",
        )[0]

        self.assertEqual(set(daily), set(quote))

    def test_contract_metadata_documents_units_and_raw_path(self) -> None:
        metadata = market_contract_metadata()

        self.assertEqual(metadata["schema_version"], MARKET_SCHEMA_VERSION)
        self.assertEqual(metadata["normalization"]["price_unit"], "VND")
        self.assertEqual(
            metadata["normalization"]["interval_codes"]["equity_quote"],
            "snapshot",
        )
        self.assertEqual(
            metadata["normalization"]["source_record_path"],
            "data[].source_record",
        )


if __name__ == "__main__":
    unittest.main()
