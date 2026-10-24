import unittest
import json
from app.providers.issuer_disclosures import make_document, parse_hpg, parse_vnm, report_period, ISSUERS

class IssuerDisclosureTests(unittest.TestCase):
    def test_acb_uses_displayed_date_not_creation_timestamp(self):
        from app.providers.issuer_disclosures import parse_acb
        title='Báo cáo tài chính hợp nhất quý 02 năm 2026'
        source=dict(id=10,title=title,created_at='2020-01-01T00:00:00Z',featured_image={'path':'https://acb.com.vn/acbwebsite/files/report 2026.pdf'})
        data=json.dumps({'props':{'pageProps':{'records':[source]}}})
        html=f'<script id="__NEXT_DATA__">{data}</script><div class="item-card-x"><h4 class="title">{title}</h4><span class="day">22/07/2026</span></div>'
        rows,_=parse_acb(html,ISSUERS['ACB']['listing']+'-2026')
        self.assertEqual(rows[0]['published_on'],'2026-07-22')
        self.assertIn('%20',rows[0]['document_url'])
        self.assertEqual(rows[0]['period_end'],'2026-06-30')

    def test_semiannual_and_annual_are_not_quarter_columns(self):
        self.assertEqual(report_period('BCTC hợp nhất bán niên 2026')[1], 'HALF_YEAR')
        self.assertEqual(report_period('BCTC hợp nhất năm 2025 đã kiểm toán')[1], 'ANNUAL')
        self.assertIsNone(report_period('BCTC so sánh năm 2024 và 2025'))

    def test_hpg_child_rows_keep_their_own_dates_and_scope(self):
        html='''<div class="item" data-id="1"><div class="item item-child">
        <div class="name"><a href="https://file.hoaphat.com.vn/hoaphat-com-vn/report.pdf">BCTC riêng quý II/2025</a></div>
        <div class="time">30/07/2025</div></div></div><a rel="next"></a>'''
        rows,more=parse_hpg(html,ISSUERS['HPG']['listing'])
        self.assertEqual(len(rows),1);self.assertTrue(more)
        self.assertEqual(rows[0]['report_scope'],'SEPARATE')
        self.assertEqual(rows[0]['published_on'],'2025-07-30')

    def test_vnm_q4_listing_does_not_certify_quarter_basis(self):
        html='<a href="https://d8um25gjecm9v.cloudfront.net/cms/annual.pdf">27/02/2026 2025 Q4 Báo cáo tài chính hợp nhất Đã soát xét/kiểm toán</a>'
        rows,_=parse_vnm(html,ISSUERS['VNM']['listing'])
        self.assertEqual(rows[0]['period_end'],'2025-12-31')
        self.assertEqual(rows[0]['report_kind'],'UNKNOWN')

    def test_unknown_scope_and_missing_publication_stay_unverified(self):
        r=dict(id='1',name='BCTC quý 2 2025',pdfUrl='https://file.hoaphat.com.vn/hoaphat-com-vn/r.pdf',actualPublishedAt='2025-07-30')
        d=make_document('HPG',r,ISSUERS['HPG']['listing'])
        self.assertEqual(d['report_scope'],'UNKNOWN');self.assertFalse(d['training_eligible'])
        self.assertIsNone(make_document('HPG',{**r,'actualPublishedAt':'2025-06-01'},ISSUERS['HPG']['listing']))

    def test_external_or_encoded_document_paths_rejected(self):
        for url in ['https://file.hoaphat.com.vn.evil.test/a.pdf','https://file.hoaphat.com.vn/hoaphat-com-vn/%2e%2e/a.pdf']:
            r=dict(id='1',name='BCTC hợp nhất năm 2025',pdfUrl=url,actualPublishedAt='2026-03-01')
            self.assertIsNone(make_document('HPG',r,ISSUERS['HPG']['listing']))
