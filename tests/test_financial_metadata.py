import unittest
from unittest.mock import patch
import pandas as pd
from fastapi.testclient import TestClient
from app.main import app
from app.core.financial_metadata import financial_metadata, cafef_metadata


class FinancialMetadataTests(unittest.TestCase):
    def test_missing_source_metadata_is_unknown_and_created_date_is_not_publication(self):
        df = pd.DataFrame([{"fiscalDate": "2026-06-30", "createdDate": "2026-07-28",
                            "modifiedDate": "2026-08-24", "formType": "ALL", "numericValue": 123}])
        meta = financial_metadata(df, "income_statement", "vndirect")
        self.assertEqual(meta["report_scope"], "UNKNOWN")
        self.assertEqual(meta["period_basis"], "UNKNOWN")
        self.assertIsNone(meta["currency"])
        self.assertIsNone(meta["unit_scale"])
        self.assertIsNone(meta["published_at"])
        self.assertIn("2026-06-30", meta["periods"])

    def test_explicit_units_scope_basis_and_vietnam_publication_keep_evidence(self):
        df = pd.DataFrame([{"report_scope": "CONSOLIDATED", "unit": "triệu đồng",
                            "period_basis": "YTD", "publishedAt": "2026-07-20T09:00:00"}])
        meta = financial_metadata(df, "cash_flow", "vndirect")
        self.assertEqual(meta["currency"], "VND")
        self.assertEqual(meta["unit_scale"], 1000000)
        self.assertEqual(meta["report_scope"], "CONSOLIDATED")
        self.assertEqual(meta["period_basis"], "YTD")
        self.assertTrue(meta["published_at"].endswith("+07:00"))
        self.assertEqual(meta["evidence"]["unit_scale"][0]["value"], "triệu đồng")

    def test_conflicting_scopes_are_not_silently_selected(self):
        meta = financial_metadata(pd.DataFrame([{"report_scope":"SEPARATE"},
                                               {"report_scope":"CONSOLIDATED"}]), "income_statement", "vndirect")
        self.assertEqual(meta["report_scope"], "UNKNOWN")
        self.assertTrue(any(x.startswith("CONFLICTING_REPORT_SCOPE") for x in meta["limitations"]))

    def test_publication_is_per_period_not_maximum_across_periods(self):
        meta = financial_metadata(pd.DataFrame([
            {"fiscalDate":"2026-03-31", "publishedAt":"2026-04-20T00:00:00Z"},
            {"fiscalDate":"2026-06-30", "publishedAt":"2026-07-20T00:00:00Z"}]), "income_statement", "vndirect")
        self.assertIsNone(meta["published_at"])
        self.assertEqual(meta["periods"]["2026-03-31"]["published_at"], "2026-04-20T00:00:00+00:00")

    def test_report_headings_not_navigation_determine_cafef_scope(self):
        html = '<nav>Báo cáo hợp nhất</nav><h1>Báo cáo riêng lẻ</h1><span>Đơn vị: nghìn đồng</span>'
        source = cafef_metadata(html, "https://s.cafef.vn/report", "income_statement")
        df = pd.DataFrame([{"item":"Lợi nhuận", "2026Q2":123}])
        df.attrs["financial_metadata"] = source
        meta = financial_metadata(df, "income_statement", "cafef")
        self.assertEqual(meta["report_scope"], "SEPARATE")
        self.assertEqual(meta["unit_scale"], 1000)
        self.assertEqual(meta["currency"], "VND")

    def test_financial_endpoint_adds_metadata_without_changing_values(self):
        df = pd.DataFrame([{"fiscalDate":"2026-06-30", "numericValue":123,
                            "itemCode":11000, "itemEnName":"Current Assets"}])
        with patch("app.api.v1.vndirect.vndirect_provider.balance_sheet", return_value=df):
            response = TestClient(app).get("/api/v1/vndirect/equities/FPT/financials/balance-sheet?fiscal_date=2026-06-30")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"][0]["numericValue"],123)
        self.assertEqual(payload["financial_metadata"]["schema_version"],"financial.metadata.v1")
        self.assertEqual(payload["financial_metadata"]["period_basis"],"POINT_IN_TIME")


if __name__ == "__main__":
    unittest.main()
