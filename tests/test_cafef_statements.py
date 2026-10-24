import unittest
from app.core.cafef_statements import parse_cafef_statement,number
from app.core.financial_metadata import financial_metadata

HTML='''<table id="tblGridData"><tr><td>Trước</td><td class="h_t">Quý 2- 2025</td><td class="h_t">Quý 3- 2025</td><td>Tăng trưởng</td></tr></table>
<table id="tableContent"><tr id="60"><td>Lợi nhuận sau thuế</td><td>2.740.242.077.853</td><td>(1.250,5)</td><td><table><tr><td>999</td></tr></table></td></tr>
<tr id="heading"><td>Nhóm</td><td></td><td>-</td><td></td></tr></table>
<tr id="ContentPlaceHolder1_trDonVi"><td>Đơn vị: tỷ đồng</td></tr>'''

class CafeFStatementsTests(unittest.TestCase):
 def test_bank_values_under_non_bank_labels_are_rejected(self):
  identity='<div id="div_cf_BoxContent"><a href="/du-lieu/hose/EIB-bank.chn">Ngan hang EIB</a></div>'
  for statement,label in [('INCOME','Doanh thu ban hang'),('BALANCESHEET','Tai san ngan han')]:
   html=identity+HTML.replace('Lợi nhuận sau thuế',label)
   with self.assertRaisesRegex(ValueError,'CAFEF_BANK_TEMPLATE_MISMATCH'):
    parse_cafef_statement(html,'url',statement,'EIB')
 def test_requested_company_must_match_report(self):
  html='<div id="div_cf_BoxContent"><a href="/du-lieu/hose/FPT-company.chn">FPT</a></div>'+HTML
  with self.assertRaisesRegex(ValueError,'CAFEF_COMPANY_IDENTITY_MISMATCH'):
   parse_cafef_statement(html,'url','INCOME','EIB')
  self.assertEqual(len(parse_cafef_statement(html,'url','INCOME','FPT')),2)
 def test_separate_header_nested_chart_and_exact_amount(self):
  d=parse_cafef_statement(HTML,'https://cafef.vn/report','INCOME')
  self.assertEqual(len(d),2)
  self.assertEqual(d.fiscalDate.tolist(),['2025-06-30','2025-09-30'])
  self.assertEqual(d.numericValue.tolist(),['2740242077853','-1250.5'])
  self.assertTrue(all(d.itemCode.str.startswith('CAF_60_')))
 def test_unverified_widget_never_multiplies_values(self):
  d=parse_cafef_statement(HTML,'https://cafef.vn/report','INCOME')
  m=financial_metadata(d,'income_statement','cafef')
  self.assertIsNone(m['unit_scale']);self.assertIsNone(m['published_at'])
  self.assertEqual(len(m['periods']),2)
  self.assertIn('tỷ đồng',m['unverified_display_unit'])
 def test_missing_or_duplicate_periods_rejected(self):
  for html in [HTML.replace('tblGridData','other'),HTML.replace('Quý 3- 2025','Quý 2- 2025')]:
   with self.assertRaises(ValueError):parse_cafef_statement(html,'url','INCOME')
 def test_missing_cells_do_not_shift_periods(self):
  d=parse_cafef_statement(HTML.replace('2.740.242.077.853',''),'url','INCOME')
  self.assertEqual(d.fiscalDate.tolist(),['2025-09-30'])
 def test_ambiguous_number_rejected(self):
  with self.assertRaises(ValueError):number('1,234.56')
 def test_unknown_header_rejected(self):
  with self.assertRaises(ValueError):parse_cafef_statement(HTML.replace('Quý 3- 2025','6 tháng'),'url','INCOME')
