import json,unittest
from app.providers.disclosure_provider import parse_fpt_disclosures
from fastapi.testclient import TestClient
from app.main import app

def html(records):return '<script>self.__next_f.push('+json.dumps([1,json.dumps(records,ensure_ascii=False,separators=(',',':'))])+')</script>'
def record(**kw):return dict(id=1,name='Báo cáo tài chính hợp nhất quý 2 năm 2025',pdfUrl='/api/media/report.pdf',actualPublishedAt='2025-07-22',**kw)

class DisclosureTests(unittest.TestCase):
 def test_explicit_publication_scope_and_conservative_availability(self):
  r=parse_fpt_disclosures(html([record()]))[0]
  self.assertEqual(r['published_on'],'2025-07-22');self.assertEqual(r['report_scope'],'CONSOLIDATED')
  self.assertEqual(r['period_end'],'2025-06-30');self.assertIn('23:59:59',r['available_at'])
  self.assertFalse(r['training_eligible']);self.assertEqual(r['revision_status'],'UNKNOWN')
 def test_revision_preserved_separately(self):
  a=record();b={**a,'id':2,'name':'Điều chỉnh '+a['name'],'actualPublishedAt':'2025-08-01'}
  result=parse_fpt_disclosures(html([a,b]));self.assertEqual(len(result),2)
  self.assertEqual(result[1]['revision_status'],'RESTATED');self.assertNotEqual(result[0]['report_version_id'],result[1]['report_version_id'])
 def test_created_date_and_filename_cannot_supply_publication(self):
  r=record();r.pop('actualPublishedAt');r['createdAt']='2025-07-22'
  self.assertEqual(parse_fpt_disclosures(html([r])),[])
 def test_bad_origin_path_and_publication_before_period_rejected(self):
  for change in [dict(pdfUrl='https://evil.example/file.pdf'),dict(pdfUrl='/api/media/../file.pdf'),dict(actualPublishedAt='2025-06-01')]:
   self.assertEqual(parse_fpt_disclosures(html([{**record(),**change}])),[])
 def test_scope_not_borrowed_from_other_records(self):
  r=record();r['name']='Báo cáo tài chính quý 2 năm 2025'
  self.assertEqual(parse_fpt_disclosures(html([r]))[0]['report_scope'],'UNKNOWN')
 def test_unsupported_issuer_is_explicit(self):
  response=TestClient(app).get('/api/v1/disclosures/NOTREGISTERED');self.assertEqual(response.status_code,422)
  self.assertEqual(response.json()['detail']['code'],'ISSUER_NOT_SUPPORTED')
