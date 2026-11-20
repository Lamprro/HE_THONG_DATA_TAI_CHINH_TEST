"""CafeF index bars in native points; source identity is checked per historical row."""
from datetime import date, datetime, timedelta
import math
import httpx
from app.core.index_calendar import validate_index_session

URL = "https://cafef.vn/du-lieu/ajax/pagenew/datahistory/pricehistory.ashx"
# Verified against source row Symbol and matching KBS closes for January 2016.
SYMBOLS = {"VNINDEX": "VNINDEX", "VN30": "VN30INDEX"}


def index_history(symbol: str, start: date, end: date, client=None):
    if symbol not in SYMBOLS or start > end or (end-start).days + 1 > 366:
        raise ValueError("Invalid index or date window (maximum 366 days)")
    own = client is None
    client = client or httpx.Client(timeout=20, follow_redirects=True,
        headers={"User-Agent":"Mozilla/5.0", "Referer":"https://cafef.vn/", "Accept":"application/json"})
    rows, seen, urls = [], set(), []
    try:
        chunk_start = start
        while chunk_start <= end:
            chunk_end = min(end, chunk_start + timedelta(days=89))
            expected, received, page = None, 0, 1
            while True:
                response = client.get(URL, params={"Symbol":SYMBOLS[symbol],
                    "StartDate":chunk_start.strftime("%m/%d/%Y"), "EndDate":chunk_end.strftime("%m/%d/%Y"),
                    "PageIndex":page, "PageSize":100})
                response.raise_for_status()
                body = response.json()
                data = body.get("Data")
                if body.get("Success") is not True or not isinstance(data,dict) or not isinstance(data.get("Data"),list):
                    raise ValueError("Invalid CafeF index source schema")
                total = data.get("TotalCount")
                if isinstance(total,bool) or not isinstance(total,int) or total < 0:
                    raise ValueError("Invalid CafeF index source count")
                if expected is None: expected = total
                if total != expected: raise ValueError("CafeF index pagination changed during fetch")
                page_rows = data["Data"]
                if not page_rows and received < expected: raise ValueError("Incomplete CafeF index pagination")
                urls.append(str(response.url))
                for source in page_rows:
                    if source.get("Symbol") != SYMBOLS[symbol]: raise ValueError("CafeF index source symbol mismatch")
                    day = datetime.strptime(source["Ngay"],"%d/%m/%Y").date()
                    if not chunk_start <= day <= chunk_end or day in seen:
                        raise ValueError("Duplicate or out-of-window CafeF index bar")
                    validate_index_session(symbol, day)
                    values=[]
                    for field in ("GiaMoCua","GiaCaoNhat","GiaThapNhat","GiaDongCua","KhoiLuongKhopLenh"):
                        raw=source.get(field)
                        if isinstance(raw,bool) or not isinstance(raw,(int,float,str)):
                            raise ValueError("Invalid CafeF index numeric value")
                        value=float(raw)
                        if not math.isfinite(value) or value < 0: raise ValueError("Invalid CafeF index numeric value")
                        values.append(value)
                    opening, high, low, closing, volume=values
                    if high < max(opening,closing,low) or low > min(opening,closing,high):
                        raise ValueError(f"Invalid index OHLC range: symbol={symbol}, date={day}, "
                            f"open={opening}, high={high}, low={low}, close={closing}")
                    seen.add(day)
                    rows.append(dict(trading_date=str(day),open=opening,high=high,low=low,close=closing,
                        volume=volume,source_record=source))
                received += len(page_rows)
                if received > expected: raise ValueError("CafeF index count mismatch")
                if received == expected: break
                page += 1
                if page > 10: raise ValueError("CafeF index pagination exceeds bounded window")
            chunk_start = chunk_end + timedelta(days=1)
        return dict(provider="cafef",dataset="index_ohlcv",symbol=symbol,source_symbol=SYMBOLS[symbol],
            interval="1D",unit="INDEX_POINTS",source_url=URL,source_urls=urls,count=len(rows),
            data=sorted(rows,key=lambda r:r["trading_date"]))
    finally:
        if own: client.close()
