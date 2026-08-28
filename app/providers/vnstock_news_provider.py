from __future__ import annotations

import importlib.util
import os
from importlib import metadata
from pathlib import Path
from typing import Any

import pandas as pd

from app.providers.base import ProviderInfo


# Vercel Python functions have a read-only home directory. vnstock_news and
# its crawler dependencies may create cache/config/output files, so keep all
# runtime writes under /tmp when deployed to Vercel.
if os.getenv("VERCEL"):
    runtime_home = Path("/tmp/vnstock-news-runtime")
    config_home = runtime_home / ".config"
    cache_home = runtime_home / ".cache"
    data_home = runtime_home / ".local" / "share"
    output_home = runtime_home / "output"

    for directory in (runtime_home, config_home, cache_home, data_home, output_home):
        directory.mkdir(parents=True, exist_ok=True)

    os.environ["HOME"] = str(runtime_home)
    os.environ["USERPROFILE"] = str(runtime_home)
    os.environ["XDG_CONFIG_HOME"] = str(config_home)
    os.environ["XDG_CACHE_HOME"] = str(cache_home)
    os.environ["XDG_DATA_HOME"] = str(data_home)
    os.environ["TMPDIR"] = "/tmp"


class VnStockNewsProvider:
    """Optional adapter for the sponsor/private vnstock_news package.

    The public VnStock package is still used separately for company-tagged
    news. This adapter only activates when the private vnstock_news package is
    actually installed in the runtime.
    """

    info = ProviderInfo(
        code="vnstock_news",
        name="VnStock News",
        adapter="optional-python-library",
        status="optional-sponsor",
        auth_required=True,
        capabilities=("rss_latest", "supported_sites", "historical_full_text"),
    )

    @staticmethod
    def installed() -> bool:
        return importlib.util.find_spec("vnstock_news") is not None

    def version(self) -> str | None:
        if not self.installed():
            return None
        try:
            return metadata.version("vnstock_news")
        except metadata.PackageNotFoundError:
            try:
                return metadata.version("vnstock-news")
            except metadata.PackageNotFoundError:
                return "installed"

    def status(self) -> dict[str, Any]:
        is_installed = self.installed()
        return {
            "provider": "vnstock_news",
            "installed": is_installed,
            "version": self.version(),
            "mode": "sponsor-private-package",
            "ready": is_installed,
            "message": (
                "vnstock_news is installed and ready"
                if is_installed
                else "vnstock_news is not installed in this runtime. The package is distributed through the VnStock sponsor installer and requires sponsor access/API key."
            ),
        }

    @staticmethod
    def _require_package():
        if importlib.util.find_spec("vnstock_news") is None:
            raise RuntimeError(
                "vnstock_news package is not installed. It is a sponsor/private VnStock package and must be installed with authorized VnStock sponsor access."
            )
        import vnstock_news

        return vnstock_news

    def supported_sites(self) -> list[str]:
        module = self._require_package()
        sites = getattr(module, "SUPPORTED_SITES", None)
        if sites is None:
            try:
                from vnstock_news.config.sites import SITES_CONFIG

                sites = list(SITES_CONFIG.keys())
            except Exception:
                sites = []
        return sorted(str(site) for site in sites)

    def latest(self, site: str, limit: int) -> list[dict[str, Any]]:
        module = self._require_package()
        crawler = module.Crawler(site_name=site)
        rows = crawler.get_articles_from_feed(limit_per_feed=limit) or []
        if isinstance(rows, pd.DataFrame):
            return rows.to_dict(orient="records")
        return list(rows)

    def historical(self, site: str, limit: int, request_delay: float) -> pd.DataFrame:
        module = self._require_package()
        crawler = module.BatchCrawler(
            site_name=site,
            request_delay=request_delay,
            output_path="/tmp/vnstock-news-runtime/output" if os.getenv("VERCEL") else "./output",
        )
        result = crawler.fetch_articles(limit=limit)
        if isinstance(result, pd.DataFrame):
            return result
        return pd.DataFrame(result or [])


vnstock_news_provider = VnStockNewsProvider()
