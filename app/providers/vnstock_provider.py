from __future__ import annotations

from functools import cached_property

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
        capabilities=("ohlcv", "quote", "company", "financial_statements", "ratio"),
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

    def financial_statement(self, symbol: str, statement: str, period: str) -> pd.DataFrame:
        equity = self.fundamental.equity(symbol)
        loader = getattr(equity, statement)
        return loader(period=period)

    def ratio(self, symbol: str, period: str) -> pd.DataFrame:
        equity = self.fundamental.equity(symbol)
        return equity.ratio(period=period)


vnstock_provider = VnStockProvider()
