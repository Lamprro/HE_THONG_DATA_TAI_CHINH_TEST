"""Chay truc tiep VnStock khong qua FastAPI de kiem tra provider."""

from datetime import date, timedelta

from vnstock import Fundamental, Market, Reference

SYMBOL = "FPT"

market = Market()
reference = Reference()
fundamental = Fundamental()

end = date.today()
start = end - timedelta(days=14)

print("\n=== OHLCV ===")
print(market.equity.ohlcv(symbol=SYMBOL, start=start.isoformat(), end=end.isoformat()).tail())

print("\n=== COMPANY ===")
print(reference.company.info(symbol=SYMBOL).head())

print("\n=== BALANCE SHEET ===")
print(fundamental.equity.balance_sheet(symbol=SYMBOL, period="year").head())
