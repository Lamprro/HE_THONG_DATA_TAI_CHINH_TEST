"""Provider mocks only. Live deployment acceptance is performed separately through Java ingestion."""
import unittest
from datetime import date
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.macro import router
from app.providers.macro_provider import MacroUpstreamError, normalize_bis, normalize_worldbank, observations

START, END = date(2016, 1, 1), date(2025, 12, 31)
WB = [{"pages": 1}, [dict(indicator={"id": "NY.GDP.MKTP.CD"}, countryiso3code="VNM", date="2024", value=123.5),
                       dict(indicator={"id": "FR.INR.LEND"}, countryiso3code="VNM", date="2024", value=None)]]
BIS = "FREQ,REF_AREA,CURRENCY,COLLECTION,TIME_PERIOD,OBS_VALUE,UNIT_MULT\nQ,VN,VND,A,2024-Q1,24000,0\n"


class MacroTests(unittest.TestCase):
    def test_native_frequencies_and_missing_values(self):
        result = normalize_worldbank(WB, START, END)
        self.assertEqual(result[0]["frequency"], "YEARLY")
        self.assertEqual(result[0]["observations"][0]["observation_date"], "2024-12-31")
        self.assertEqual(result[5]["missing_periods"], ["2024"])
        self.assertEqual(normalize_bis(BIS, START, END)[0]["observations"][0]["observation_date"], "2024-03-31")

    def test_mixed_country_duplicate_and_incomplete_page_rejected(self):
        import copy
        bad = copy.deepcopy(WB)
        bad[1][0]["countryiso3code"] = "USA"
        with self.assertRaises(MacroUpstreamError): normalize_worldbank(bad, START, END)
        with self.assertRaises(MacroUpstreamError): normalize_worldbank([{"pages": 2}, WB[1]], START, END)
        with self.assertRaises(MacroUpstreamError): normalize_worldbank([WB[0], WB[1]+WB[1]], START, END)

    def test_invalid_bis_unit_and_period_rejected(self):
        for bad in (BIS.replace(",0\n", ",3\n"), BIS.replace("2024-Q1", "2024-Q5"), BIS+BIS.splitlines()[1]+"\n"):
            with self.assertRaises(MacroUpstreamError): normalize_bis(bad, START, END)

    def test_incomplete_quarter_not_returned(self):
        self.assertEqual(normalize_bis(BIS, START, date(2024, 2, 1))[0]["observations"], [])

    def test_actual_provider_request_and_envelope_with_mock_transport(self):
        def handle(request):
            self.assertEqual(request.url.host, "api.worldbank.org")
            self.assertIn("VNM", request.url.path)
            self.assertEqual(request.url.params["source"], "2")
            return httpx.Response(200, json=WB)
        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            result = observations("worldbank", "VNM", START, END, client)
        self.assertEqual(result["count"], 10)
        self.assertEqual(result["observation_count"], 1)
        self.assertEqual(result["schema_version"], "macro_observations.v1")

    def test_route_validation_and_provider_failure(self):
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/macro")
        client = TestClient(app)
        self.assertEqual(client.get("/api/v1/macro/bis/observations?country=USA&start=2016-01-01&end=2025-12-31").status_code, 422)
        self.assertEqual(client.get("/api/v1/macro/unknown/series").status_code, 422)
        with patch("app.api.v1.macro.observations", side_effect=MacroUpstreamError()):
            self.assertEqual(client.get("/api/v1/macro/bis/observations?start=2016-01-01&end=2025-12-31").status_code, 502)


if __name__ == "__main__": unittest.main()
