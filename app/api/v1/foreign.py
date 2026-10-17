"""Stateless foreign-volume retrieval. Missing source history remains missing."""
from datetime import date,datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter,HTTPException
from app.providers.cafef_provider import cafef_provider
from app.core.serialization import utc_now_iso

router=APIRouter()
URL="https://cafef.vn/du-lieu/ajax/pagenew/datahistory/gdkhoingoai.ashx"

def fetch_foreign(symbol,start,end,client=None):
    symbol=symbol.strip().upper()
    if not symbol.isalnum() or len(symbol)>12 or start>end or end.year-start.year>15:
        raise ValueError("Invalid foreign-trade symbol or date window")
    client=client or cafef_provider.client
    rows=[];seen=set();total=None;page=1
    while total is None or len(rows)<total:
        response=client.get(URL,params={"Symbol":symbol,"StartDate":start.strftime("%m/%d/%Y"),
            "EndDate":end.strftime("%m/%d/%Y"),"PageIndex":page,"PageSize":100})
        response.raise_for_status()
        body=response.json()
        if body.get("Success") is not True or not isinstance(body.get("Data"),dict):
            raise ValueError("Foreign-trade source schema mismatch")
        data=body["Data"];total=int(data["TotalCount"])
        if not 0<=total<=10000 or not isinstance(data.get("Data"),list):raise ValueError("Oversized/invalid foreign source")
        for row in data["Data"]:
            day=datetime.strptime(row["Ngay"],"%d/%m/%Y").date()
            if row.get("Symbol")!=symbol or not start<=day<=end or day in seen:
                raise ValueError("Foreign source returned wrong symbol/date or duplicate")
            seen.add(day);rows.append(row)
        if len(rows)>total:raise ValueError("Foreign source count mismatch")
        if not data["Data"]:
            if len(rows)<total:raise ValueError("Incomplete foreign source pagination")
            break
        page+=1
        if page>101:raise ValueError("Foreign source pagination limit")
    return dict(schema_version="foreign_trades.v1",provider="cafef",dataset="foreign_trades",symbol=symbol,
        start_date=start.isoformat(),end_date=end.isoformat(),retrieved_at=utc_now_iso(),count=len(rows),
        source_url=URL,volume_unit="SHARES",data=rows,
        limitations=["Only returned source sessions are included; missing history is not zero or forward-filled.",
                      "Current provider vintage; historic publication/revision availability is not verified."])

@router.get("/equities/{symbol}/foreign-trades",tags=["cafef-market"])
def foreign_trades(symbol:str,start:date,end:date):
    if end>datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date():raise HTTPException(400,"Future foreign end date")
    try:return fetch_foreign(symbol,start,end)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    except Exception as exc:raise HTTPException(502,"CafeF foreign source unavailable") from exc
