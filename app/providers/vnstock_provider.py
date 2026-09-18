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
            "index_ohlcv",
            "index_latest",
            "index_members",
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

    def index_ohlcv(
        self,
        index_code: str,
        start: str,
        end: str,
        interval: str = "1D",
        source: str = "kbs",
    ) -> pd.DataFrame:
        market_index = self.market.index(index_code)
        return market_index.ohlcv(
            start=start,
            end=end,
            interval=interval,
            source=source,
        )

    def index_latest(
        self,
        index_code: str,
        start: str,
        end: str,
        source: str = "kbs",
    ) -> pd.DataFrame:
        df = self.index_ohlcv(index_code, start, end, "1D", source)
        if df.empty:
            return df

        for column in ("time", "date", "trading_date", "tradingDate"):
            if column not in df.columns:
                continue
            timestamps = pd.to_datetime(df[column], errors="coerce")
            if timestamps.notna().any():
                return df.loc[[timestamps.idxmax()]].reset_index(drop=True)

        # VnStock normally returns daily bars in chronological order. Keep a
        # deterministic fallback if a connector changes/omits its date column.
        return df.tail(1).reset_index(drop=True)

    def index_members(self, index_code: str, source: str = "kbs") -> pd.DataFrame:
        result = self.reference.index.members(index_code, source=source)
        if isinstance(result, pd.DataFrame):
            return result
        return pd.DataFrame(result or [])

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
