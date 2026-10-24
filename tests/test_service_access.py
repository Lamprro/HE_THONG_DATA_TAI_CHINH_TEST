import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

class ServiceAccessTests(unittest.TestCase):
    def test_eib_chain_supplement_keeps_certificate_and_hostname_checks(self):
        import ssl, hashlib
        from app.core.provider_tls import eib_tls_context
        context=eib_tls_context()
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
        self.assertIn('c6270a150691fbe190d831f5139bdfeecf7b298b4fa0ca17306a69d7e91e7ba2',
                      {hashlib.sha256(c).hexdigest() for c in context.get_ca_certs(binary_form=True)})
    def test_production_without_token_is_closed_except_health(self):
        with patch.dict(os.environ,{'APP_ENV':'production','PYTHON_SERVICE_TOKEN':''}):
            client=TestClient(app)
            self.assertEqual(client.get('/api/v1/capabilities').status_code,503)
            self.assertEqual(client.get('/api/v1/health').status_code,200)

    def test_token_is_required_on_all_routes_when_configured(self):
        token='isolated-fixture-service-key-long-enough'
        with patch.dict(os.environ,{'APP_ENV':'production','PYTHON_SERVICE_TOKEN':token}):
            client=TestClient(app)
            self.assertEqual(client.get('/api/v1/capabilities').status_code,403)
            self.assertEqual(client.get('/api/v1/capabilities',headers={'Authorization':'Bearer '+token}).status_code,200)
            self.assertEqual(client.get('/docs').status_code,403)

    def test_official_proxy_cannot_mutate_source(self):
        self.assertEqual(TestClient(app).post('/api/v1/proxy/hpg-ir/file.pdf').status_code,405)
