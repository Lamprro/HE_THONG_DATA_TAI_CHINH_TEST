from __future__ import annotations

import os
from functools import cached_property
from pathlib import Path

# Vercel serverless functions can only write to /tmp. VnStock and some of its
# dependencies may initialize user-level config/cache files under $HOME, so
# redirect all writable runtime locations before importing vnstock.
if os.getenv("VERCEL"):
    runtime_home = Path("/tmp/vnstock-runtime")
    config_home = runtime_home / ".config"
    cache_home = runtime_home / ".cache"
    data_home = runtime_home / ".local" / "share"
    mpl_home = runtime_home / ".matplotlib"

    for directory in (runtime_home, config_home, cache_home, data_home, mpl_home):
        directory.mkdir(parents=True, exist_ok=True)

    os.environ["HOME"] = str(runtime_home)
    os.environ["USERPROFILE"] = str(runtime_home)
    os.environ["XDG_CONFIG_HOME"] = str(config_home)
    os.environ["XDG_CACHE_HOME"] = str(cache_home)
    os.environ["XDG_DATA_HOME"] = str(data_home)
    os.environ["MPLCONFIGDIR"] = str(mpl_home)
    os.environ["TMPDIR"] = "/tmp"

import pandas as pd
from vnstock import Fundamental, Market, Reference

from app.providers.base import ProviderInfo


class VnStockProvider:
    info = ProviderInfo(
        code="vnstock",
        name="VnStock Unified UI v4",
        adapter="python-library",
        status="active",
        auth_required=False,
        capabilities=(
            "ohlcv",
            "quote",
            "company",
            "company_news",
            "financial_statements",
            "ratio",
        ),
    )

    @cached_property
    def market(self) -> Market:
        return Market()

    @cached_property
    def reference(self) -> Reference:
        return Reference()

    @cached_property
    def fundamental(self) -> Fundamental:
        return Fundamental()

    def equity_ohlcv(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        equity = self.market.equity(symbol)
        return equity.ohlcv(start=start, end=end)

    def equity_quote(self, symbol: str) -> pd.DataFrame:
        return self.market.quote(symbol)

    def company_info(self, symbol: str) -> pd.DataFrame:
        company = self.reference.company(symbol)
        return company.info()

    def company_news(self, symbol: str) -> pd.DataFrame:
        company = self.reference.company(symbol)
        result = company.news()
        if isinstance(result, pd.DataFrame):
            return result
        return pd.DataFrame(result or [])

    def financial_statement(self, symbol: str, statement: str, period: str) -> pd.DataFrame:
        equity = self.fundamental.equity(symbol)
        loader = getattr(equity, statement)
        return loader(period=period)

    def ratio(self, symbol: str, period: str) -> pd.DataFrame:
        equity = self.fundamental.equity(symbol)
        return equity.ratio(period=period)


vnstock_provider = VnStockProvider()
