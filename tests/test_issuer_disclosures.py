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

class FiscalIssuerTests(unittest.TestCase):
    def test_hsg_quarters_follow_october_fiscal_calendar(self):
        from app.providers.issuer_disclosures import hsg_period
        for quarter,end in [('I','2025-12-31'),('II','2026-03-31'),('III','2026-06-30'),('IV','2026-09-30')]:
            self.assertEqual(hsg_period(f'BCTC quy {quarter} NDTC 2025 \u2013 2026')[0].isoformat(),end)
        self.assertEqual(hsg_period('BCTC giua nien do NDTC 2025-2026')[1],'HALF_YEAR')
        self.assertIsNone(hsg_period('BCTC quy III NDTC 2024-2026'))

    def test_hsg_keeps_report_attachment_and_its_own_publication(self):
        from app.providers.issuer_disclosures import parse_hsg
        html='''<div class="wrap-item"><div class="item-content"><div class="date">11:15 - 29/07/2026</div>
        <h4 class="title-post">HSG Bao cao tai chinh hop nhat va Giai trinh KQKD hop nhat Quy III NDTC 2025-2026</h4>
        <div class="item-sub"><a class="btn-viewer">BCTC HN Quy III NDTC 2025-2026</a><a class="btn-download" href="/wp-content/uploads/2026/07/report.pdf"></a></div>
        <div class="item-sub"><a class="btn-viewer">Giai trinh BCTC</a><a class="btn-download" href="/wp-content/uploads/2026/07/explanation.pdf"></a></div>
        </div></div><div class="alm-paging"><a href="?pg=2">2</a></div>'''
        rows,more=parse_hsg(html,ISSUERS['HSG']['listing']+'?pg=1')
        self.assertEqual(len(rows),1);self.assertTrue(more)
        self.assertEqual(rows[0]['period_end'],'2026-06-30')
        self.assertEqual(rows[0]['published_on'],'2026-07-29')
        self.assertEqual(rows[0]['report_scope'],'CONSOLIDATED')

    def test_hsg_legacy_attachment_names_keep_underscores_and_spaces_in_url(self):
        from app.providers.issuer_disclosures import parse_hsg
        html='''<div class="wrap-item"><div class="item-content"><div class="date">29/07/2017</div>
        <h4 class="title-post">Bao cao tai chinh hop nhat Quy III NDTC 2016-2017</h4>
        <div class="item-sub"><a class="btn-viewer">BCTC_hop_nhat_Quy_3.pdf</a>
        <a class="btn-download" href="/wp-content/uploads/report%20old (1).pdf"></a></div></div></div>'''
        rows,_=parse_hsg(html,ISSUERS['HSG']['listing']+'?pg=19')
        self.assertEqual(rows[0]['period_end'],'2017-06-30')
        self.assertTrue(rows[0]['document_url'].endswith('report%20old%20(1).pdf'))

    def test_eib_requires_publication_not_created_at(self):
        from app.providers.issuer_disclosures import parse_eib
        source=dict(id=1,title='Bao cao tai chinh hop nhat Quy 2 nam 2026',published_start='2026-07-30 13:53:28+07',created_at='2026-01-01',featured_image_1={'path':'https://media.eximbank.com.vn/exim/files/report (1).pdf'})
        def page(row):return '<script>self.__next_f.push('+json.dumps([1,'1:'+json.dumps(row)])+')</script>'
        rows,_=parse_eib(page(source),ISSUERS['EIB']['listing'])
        self.assertEqual(rows[0]['published_on'],'2026-07-30')
        self.assertEqual(rows[0]['report_scope'],'CONSOLIDATED')
        self.assertEqual(parse_eib(page({**source,'published_start':None}),ISSUERS['EIB']['listing'])[0],[])

    def test_encoded_document_names_do_not_allow_encoded_traversal(self):
        from app.providers.issuer_disclosures import allowed_pdf
        root='https://media.eximbank.com.vn/exim/files/'
        self.assertTrue(allowed_pdf('EIB',root+'report%20%281%29.pdf'))
        for name in ['%2e%2e/file.pdf','x%2fy.pdf','%252e%252e/a.pdf','x%5cy.pdf','a%00.pdf']:
            self.assertFalse(allowed_pdf('EIB',root+name))
