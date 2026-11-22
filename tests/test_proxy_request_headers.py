import unittest
from starlette.requests import Request
from app.api.v1.proxy import _request_headers

class ProxyRequestHeaderTests(unittest.TestCase):
    def test_hop_by_hop_and_connection_named_headers_are_not_forwarded(self):
        incoming={'connection':'Upgrade, HTTP2-Settings, x-temporary','upgrade':'h2c',
                  'http2-settings':'abc','te':'trailers','trailer':'x-footer','transfer-encoding':'chunked',
                  'x-temporary':'discard','authorization':'Bearer fixture','host':'localhost',
                  'accept':'application/json','x-request-id':'audit-id'}
        request=Request({'type':'http','headers':[(k.encode(),v.encode()) for k,v in incoming.items()]})
        headers=_request_headers(request,{'User-Agent':'Provider adapter'})
        self.assertEqual(headers,{'User-Agent':'Provider adapter','accept':'application/json','x-request-id':'audit-id'})

    def test_defaults_survive_without_connection_header(self):
        request=Request({'type':'http','headers':[(b'accept',b'application/json')]})
        self.assertEqual(_request_headers(request,{'Referer':'https://cafef.vn/'}),
                         {'Referer':'https://cafef.vn/','accept':'application/json'})

    def test_header_override_does_not_send_duplicate_case_variants(self):
        request=Request({'type':'http','headers':[(b'user-agent',b'Client'),(b'accept',b'application/json')]})
        headers=_request_headers(request,{'User-Agent':'Adapter','Accept':'*/*'})
        self.assertEqual(headers,{'user-agent':'Client','accept':'application/json'})
