from fastapi import APIRouter,HTTPException,Query
from app.providers.disclosure_provider import disclosure_provider
from app.providers.issuer_disclosures import ISSUERS

router=APIRouter(tags=['financial-disclosures'])

@router.get('/disclosures/{symbol}',summary='Official financial disclosure metadata with source evidence')
def disclosures(symbol:str,year:int|None=Query(None,ge=2000,le=2100),page:int=Query(1,ge=1,le=100)):
    ticker=symbol.strip().upper()
    if ticker not in ISSUERS:raise HTTPException(422,detail={'code':'ISSUER_NOT_SUPPORTED','supported_symbols':sorted(ISSUERS)})
    if ticker!='HPG' and page!=1:raise HTTPException(422,detail={'code':'PAGE_NOT_SUPPORTED'})
    try:return disclosure_provider.fetch(ticker,year,page)
    except Exception as exc:
        raise HTTPException(502,detail={'code':'DISCLOSURE_SOURCE_UNAVAILABLE','error_type':type(exc).__name__}) from exc
