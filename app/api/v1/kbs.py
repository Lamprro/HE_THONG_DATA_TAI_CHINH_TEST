from datetime import date,datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter,HTTPException
from app.providers.kbs_provider import index_history
from app.core.serialization import utc_now_iso

router=APIRouter()

@router.get("/indices/{symbol}/ohlcv",tags=["kbs-index"])
def indices(symbol:str,start:date,end:date):
    if end>datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date():
        raise HTTPException(400,"Future index end date")
    try:
        result=index_history(symbol.upper(),start,end)
        result["retrieved_at"]=utc_now_iso()
        return result
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    except Exception as exc:raise HTTPException(502,"KBS index source unavailable") from exc
