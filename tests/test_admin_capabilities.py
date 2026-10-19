"""Contract-only tests. No upstream requests, business database or synthetic financial rows."""
from fastapi.testclient import TestClient
from app.main import app
import unittest


class AdminCapabilitiesTests(unittest.TestCase):
    def test_capabilities_reflect_deployed_routes_without_claiming_upstream_health(self):
        with TestClient(app) as client:
            response = client.get('/api/v1/capabilities')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIs(data['stateless'], True)
        routes = {row['path'] for row in data['routes']}
        self.assertIn('/api/v1/kbs/indices/{symbol}/ohlcv', routes)
        self.assertIn('/api/v1/cafef/equities/{symbol}/foreign-trades', routes)
        ratio = next(row for row in data['history_contracts'] if row['operation'] == 'RATIO')
        self.assertEqual(ratio['maximum_calendar_years'], 15)
        self.assertTrue(any('not prove' in line for line in data['limitations']))
