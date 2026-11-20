import unittest
from datetime import date
import httpx
from app.providers.cafef_index_provider import index_history

class CafeFIndexTests(unittest.TestCase):
    def row(self, **values):
        return dict(Symbol='VN30INDEX',Ngay='04/01/2016',GiaMoCua=590,GiaCaoNhat=595,
                    GiaThapNhat=585,GiaDongCua=589.91,KhoiLuongKhopLenh=123,**values)
    def fetch(self, rows, total=None):
        payload={'Success':True,'Data':{'Index':'VNINDEX','TotalCount':len(rows) if total is None else total,'Data':rows}}
        with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload))) as c:
            return index_history('VN30',date(2016,1,1),date(2016,1,31),c)
    def test_historical_row_identity_alias_points_and_record_are_preserved(self):
        row=self.row();result=self.fetch([row]);self.assertEqual(result['symbol'],'VN30')
        self.assertEqual(result['source_symbol'],'VN30INDEX');self.assertEqual(result['unit'],'INDEX_POINTS')
        self.assertEqual(result['data'][0]['close'],589.91);self.assertEqual(result['data'][0]['source_record'],row)
    def test_wrong_symbol_out_of_window_ohlc_and_duplicate_are_rejected(self):
        for field,value in [('Symbol','VNINDEX'),('Ngay','04/01/2015'),('GiaCaoNhat',580),('KhoiLuongKhopLenh',-1)]:
            row=self.row();row[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.fetch([row])
        with self.assertRaises(ValueError):self.fetch([self.row(),self.row()])
    def test_truncated_pagination_is_rejected(self):
        calls=[]
        def response(r):
            calls.append(r)
            return httpx.Response(200,json={'Success':True,'Data':{'TotalCount':2,'Data':[self.row()] if len(calls)==1 else []}})
        with httpx.Client(transport=httpx.MockTransport(response)) as c,self.assertRaisesRegex(ValueError,'Incomplete'):
            index_history('VN30',date(2016,1,1),date(2016,1,31),c)
    def test_year_limit_and_unknown_symbol_rejected_before_fetch(self):
        with self.assertRaises(ValueError):index_history('VN30',date(2016,1,1),date(2018,1,1))
        with self.assertRaises(ValueError):index_history('FAKE',date(2016,1,1),date(2016,1,31))

    def test_valid_ohlc_on_verified_closed_session_is_rejected(self):
        row=self.row();row['Ngay']='24/01/2018'
        body={'Success':True,'Data':{'TotalCount':1,'Data':[row]}}
        with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=body))) as c:
            with self.assertRaisesRegex(ValueError,'Known HOSE closure'):
                index_history('VN30',date(2018,1,24),date(2018,1,24),c)
