"""Transport mocks exercise source contracts only; live acceptance is separate."""
import unittest
from datetime import date
from unittest.mock import patch
import httpx
import pandas as pd
from app.providers.vndirect_provider import vndirect_provider
from app.providers.kbs_provider import index_history
from app.providers.macro_provider import normalize_bis
from app.api.v1.foreign import fetch_foreign
from app.core.financial_metadata import financial_metadata

class TrainingDataQualityTests(unittest.TestCase):
    def test_ratio_history_uses_every_page_without_changing_report_date(self):
        calls=[]
        def handle(request):
            calls.append(request);q=request.url.params['q'];code=q.split('ratioCode:')[1].split('~')[0]
            page=int(request.url.params['page'])
            return httpx.Response(200,json={'totalPages':2,'data':[{'code':'FPT','ratioCode':code,
                'reportDate':f'2020-01-0{page}','value':page}]})
        with httpx.Client(transport=httpx.MockTransport(handle)) as client,patch.object(vndirect_provider,'client',client):
            result=vndirect_provider.ratios('FPT','2020-01-01','2020-01-31')
        self.assertEqual(len(result),12);self.assertEqual(len(calls),12)
        self.assertEqual(result.attrs['ratio_metadata']['mode'],'HISTORICAL')
        self.assertIn('reportDate:gte:2020-01-01',calls[0].url.params['q'])

    def test_ratio_wrong_symbol_or_incomplete_page_rejected(self):
        for payload in ({'totalPages':2,'data':[]},{'data':[{'code':'VCB','ratioCode':'PRICE_TO_EARNINGS','reportDate':'2020-01-01'}]}):
            with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload))) as client,patch.object(vndirect_provider,'client',client):
                with self.assertRaises(ValueError):vndirect_provider.ratios('FPT','2020-01-01','2020-12-31')

    def test_foreign_source_dates_use_month_first_and_missing_volume_is_not_zero(self):
        def handle(request):
            self.assertEqual(request.url.params['EndDate'],'01/31/2020')
            return httpx.Response(200,json={'Success':True,'Data':{'TotalCount':1,'Data':[{'Symbol':'FPT','Ngay':'31/01/2020','KLMua':None,'KLBan':0}]}})
        with httpx.Client(transport=httpx.MockTransport(handle)) as client:
            result=fetch_foreign('FPT',date(2020,1,1),date(2020,1,31),client)
        self.assertIsNone(result['data'][0]['KLMua']);self.assertEqual(result['data'][0]['KLBan'],0)

    def test_foreign_silently_ignored_source_filter_is_rejected(self):
        payload={'Success':True,'Data':{'TotalCount':1,'Data':[{'Symbol':'FPT','Ngay':'16/10/2026'}]}}
        with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload))) as client:
            with self.assertRaises(ValueError):fetch_foreign('FPT',date(2020,1,1),date(2020,1,31),client)

    def test_native_index_is_points_and_keeps_source_record(self):
        payload={'symbol':'VNINDEX','data_day':[{'t':'2016-01-04 07:00','o':'580','h':585,'l':575,'c':'580','v':'123.0'}]}
        with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload))) as client:
            result=index_history('VNINDEX',date(2016,1,1),date(2016,1,31),client)
        self.assertEqual(result['data'][0]['close'],580);self.assertEqual(result['unit'],'INDEX_POINTS')
        self.assertEqual(result['data'][0]['source_record'],payload['data_day'][0])

    def test_monthly_fx_remains_native_month_end_and_no_interpolation(self):
        csv='FREQ,REF_AREA,CURRENCY,COLLECTION,TIME_PERIOD,OBS_VALUE,UNIT_MULT\nM,VN,VND,A,2024-02,24000,0\n'
        result=normalize_bis(csv,date(2024,1,1),date(2024,12,31),frequency='M')
        self.assertEqual(result[0]['frequency'],'MONTHLY');self.assertEqual(result[0]['observations'][0]['observation_date'],'2024-02-29')
        self.assertEqual(len(result[0]['observations']),1)

    def test_revision_and_date_precision_only_from_explicit_fields(self):
        metadata=financial_metadata(pd.DataFrame([{'fiscalDate':'2024-12-31','publishedAt':'2025-03-01','isRestated':False}]),'income_statement','vndirect')
        self.assertEqual(metadata['publication_precision'],'DAY');self.assertEqual(metadata['revision_status'],'ORIGINAL')
        self.assertIn('revision_status',metadata['evidence'])
        unknown=financial_metadata(pd.DataFrame([{'modifiedDate':'2025-03-01'}]),'income_statement','vndirect')
        self.assertEqual(unknown['revision_status'],'UNKNOWN');self.assertIsNone(unknown['published_at'])
