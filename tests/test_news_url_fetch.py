import unittest
from unittest.mock import patch

import httpx

from app.api.v1.url_fetch import fetch_url
from app.news.sources import CafeFNewsSource


ARTICLE = """<html><body>
<nav>MENU MUST NOT BE CONTENT</nav>
<h1 class="title">FPT công bố kết quả kinh doanh</h1>
<h2 class="sapo">Doanh thu tăng trưởng</h2>
<div class="detail-content"><p>Nội dung chính của bài báo về FPT.</p>
<div class="related-news">TIN LIÊN QUAN MUST NOT BE CONTENT</div></div>
<span class="author">Tác giả A</span>
<time datetime="2026-09-26T15:30:00">26/09/2026</time>
</body></html>"""


class NewsUrlFetchTests(unittest.IsolatedAsyncioTestCase):
    def test_cafef_parser_returns_clean_body_and_vietnam_time(self):
        article = CafeFNewsSource().parse_article("https://cafef.vn/story-123.chn?utm_source=x", ARTICLE)
        self.assertEqual(article.canonical_url, "https://cafef.vn/story-123.chn")
        self.assertEqual(article.title, "FPT công bố kết quả kinh doanh")
        self.assertEqual(article.author, "Tác giả A")
        self.assertEqual(article.content_text, "Nội dung chính của bài báo về FPT.")
        self.assertEqual(article.published_at.isoformat(), "2026-09-26T15:30:00+07:00")

    def test_cafef_real_page_date_attribute_is_used(self):
        html = ARTICLE.replace(
            '<time datetime="2026-09-26T15:30:00">26/09/2026</time>',
            '<span class="pdate" itemprop="datePublished" '
            'datetime="2026-08-21T14:37:00+07:00">21-08-2026 - 14:37 PM</span>',
        )
        article = CafeFNewsSource().parse_article("https://cafef.vn/story-123.chn", html)
        self.assertEqual(article.published_at.isoformat(), "2026-08-21T14:37:00+07:00")

    async def test_endpoint_returns_raw_and_parsed_article_from_one_fetch(self):
        requests = []

        def respond(request):
            requests.append(str(request.url))
            return httpx.Response(200, text=ARTICLE, headers={"content-type": "text/html; charset=utf-8"})

        original_client = httpx.AsyncClient

        def client_factory(*args, **kwargs):
            return original_client(*args, transport=httpx.MockTransport(respond), **kwargs)

        with patch("app.api.v1.url_fetch.httpx.AsyncClient", side_effect=client_factory):
            result = await fetch_url("https://cafef.vn/story-123.chn")

        self.assertEqual(len(requests), 1)
        self.assertEqual(result["extraction_status"], "SUCCESS")
        self.assertIn("MENU MUST NOT BE CONTENT", result["body"])
        self.assertNotIn("MENU MUST NOT BE CONTENT", result["content_text"])
        self.assertEqual(result["published_at"], "2026-09-26T15:30:00+07:00")

    async def test_endpoint_reports_missing_article_body(self):
        original_client = httpx.AsyncClient

        def client_factory(*args, **kwargs):
            transport = httpx.MockTransport(lambda request: httpx.Response(
                200, text="<html><body><h1>Listing only</h1></body></html>",
                headers={"content-type": "text/html"}))
            return original_client(*args, transport=transport, **kwargs)

        with patch("app.api.v1.url_fetch.httpx.AsyncClient", side_effect=client_factory):
            result = await fetch_url("https://cafef.vn/listing.chn")

        self.assertEqual(result["extraction_status"], "FAILED")
        self.assertIsNone(result["content_text"])


if __name__ == "__main__":
    unittest.main()
