from fastapi import APIRouter,HTTPException,Query
from app.providers.disclosure_provider import disclosure_provider

router=APIRouter(tags=['financial-disclosures'])

@router.get('/disclosures/{symbol}',summary='Official financial disclosure metadata with source evidence')
def disclosures(symbol:str,year:int|None=Query(None,ge=2000,le=2100)):
    ticker=symbol.strip().upper()
    if ticker!='FPT':raise HTTPException(422,detail={'code':'ISSUER_NOT_SUPPORTED','supported_symbols':['FPT']})
    try:return disclosure_provider.fetch(ticker,year)
    except Exception as exc:
        raise HTTPException(502,detail={'code':'DISCLOSURE_SOURCE_UNAVAILABLE','error_type':type(exc).__name__}) from exc
