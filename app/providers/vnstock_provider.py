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
        return self.market.equity.ohlcv(symbol=symbol, start=start, end=end)

    def equity_quote(self, symbol: str) -> pd.DataFrame:
        return self.market.equity.quote(symbol=symbol)

    def company_info(self, symbol: str) -> pd.DataFrame:
        return self.reference.company.info(symbol=symbol)

    def financial_statement(self, symbol: str, statement: str, period: str) -> pd.DataFrame:
        loader = getattr(self.fundamental.equity, statement)
        return loader(symbol=symbol, period=period)

    def ratio(self, symbol: str, period: str) -> pd.DataFrame:
        return self.fundamental.equity.ratio(symbol=symbol, period=period)


vnstock_provider = VnStockProvider()
