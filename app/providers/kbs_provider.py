"""Small stateless index transport; no optional Vnstock install or business DB writes.

Protocol reference: vnstock/explorer/kbs/quote.py in thinh-vu/vnstock.
Index prices stay in points; stock price scaling is deliberately outside this adapter.
"""
from datetime import date
import math
import httpx

BASE = "https://kbbuddywts.kbsec.com.vn/iis-server/investment"
CODES = {"VNINDEX", "VN30", "HNXINDEX"}


def index_history(symbol: str, start: date, end: date, client=None):
    if symbol not in CODES or start > end or end.year-start.year > 15:
        raise ValueError("Invalid index or date window")
    own = client is None
    client = client or httpx.Client(timeout=25, follow_redirects=False, headers={"User-Agent":"Mozilla/5.0"})
    try:
        response = client.get(f"{BASE}/index/{symbol}/data_day", params={
            "sdate":start.strftime("%d-%m-%Y"),"edate":end.strftime("%d-%m-%Y")})
        response.raise_for_status()
        body = response.json()
        if body.get("symbol") != symbol or not isinstance(body.get("data_day"),list):
            raise ValueError("Index source symbol/schema mismatch")
        rows, seen = [], set()
        for source in body["data_day"]:
            day = date.fromisoformat(str(source["t"]).split(" ")[0])
            if not start <= day <= end or day in seen:
                raise ValueError("Duplicate or out-of-window source index bar")
            seen.add(day)
            values = [source[k] for k in ("o","h","l","c","v")]
            if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in values):
                raise ValueError("Invalid index numeric value")
            opening,high,low,closing,volume=values
            if high<max(opening,closing,low) or low>min(opening,closing,high):
                raise ValueError("Invalid index OHLC range")
            rows.append(dict(trading_date=day.isoformat(),open=opening,high=high,low=low,
                close=closing,volume=volume,source_record=source))
        return dict(provider="kbs",dataset="index_ohlcv",symbol=symbol,interval="1D",count=len(rows),
            source_url=str(response.url),unit="INDEX_POINTS",data=sorted(rows,key=lambda r:r["trading_date"]))
    finally:
        if own:client.close()
