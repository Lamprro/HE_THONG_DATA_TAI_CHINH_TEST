"""Official issuer records, kept separate from unverified vendor financial values."""
import calendar
import hashlib
import json
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup
from app.core.financial_metadata import _plain
from app.core.serialization import utc_now_iso

FPT_LISTING='https://fpt.com/vi/nha-dau-tu/thong-tin-cong-bo'


def parse_fpt_disclosures(html):
    records={}
    for script in BeautifulSoup(html,'html.parser').find_all('script'):
        text=script.string or ''
        if 'self.__next_f.push(' not in text:continue
        try:payload=json.loads(text[text.index('(')+1:text.rfind(')')])
        except (ValueError,IndexError):continue
        if len(payload)<2 or not isinstance(payload[1],str):continue
        for match in re.finditer(r'\{"id":',payload[1]):
            try:record,_=json.JSONDecoder().raw_decode(payload[1][match.start():])
            except ValueError:continue
            if 'actualPublishedAt' in record and record.get('pdfUrl'):records[str(record['id'])]=record
    output=[]
    for ident,record in records.items():
        title=str(record.get('name',''));plain=_plain(title);path=record['pdfUrl']
        if not ('bao cao tai chinh' in plain or 'bctc' in plain):continue
        if not re.fullmatch(r'/api/media/[A-Za-z0-9_.-]+\.pdf',path):continue
        scope='CONSOLIDATED' if 'hop nhat' in plain else 'SEPARATE' if 'rieng le' in plain else 'UNKNOWN'
        match=re.search(r'quy\s*(iv|iii|ii|i|[1-4])\b.*?(20\d{2})',plain)
        period_source='name'
        if not match:
            match=re.search(r'quy[_ -]*(iv|iii|ii|i|[1-4])[_ -]*(?:nam[_ -]*)?(20\d{2})',_plain(path));period_source='pdfUrl'
        if not match:continue
        quarter=int(match[1]) if match[1].isdigit() else {'i':1,'ii':2,'iii':3,'iv':4}[match[1]]
        year=int(match[2]);month=quarter*3
        end=date(year,month,calendar.monthrange(year,month)[1]);published=record.get('actualPublishedAt')
        try:published_date=date.fromisoformat(published)
        except (ValueError,TypeError):continue
        if published_date<end or published_date>datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date():continue
        revised=any(word in plain for word in ['dieu chinh','dinh chinh','thay the','restated'])
        # A document ID identifies this archived record, not proof of first release.
        output.append(dict(document_id=ident,symbol='FPT',title=title,period_end=end.isoformat(),
            report_scope=scope,published_on=published,publication_precision='DAY',
            available_at=published+'T23:59:59.999999+07:00',
            revision_status='RESTATED' if revised else 'UNKNOWN',
            report_version_id='FPT_IR:'+ident,document_url=urljoin(FPT_LISTING,path),
            publication_evidence=dict(field='actualPublishedAt',value=published),
            scope_evidence=dict(field='name',value=title),
            period_evidence=dict(field=period_source,value=record.get(period_source)),
            source_record_sha256=hashlib.sha256(json.dumps(record,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
            source_record=record,listing_url=FPT_LISTING,
            vintage_status='ARCHIVED_DISCLOSURE_RECONSTRUCTION',
            vendor_value_binding='UNVERIFIED',training_eligible=False))
    return sorted(output,key=lambda d:(d['period_end'],d['published_on'],d['document_id']))


class DisclosureProvider:
    def __init__(self):
        self.client=httpx.Client(timeout=25,follow_redirects=False,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html'})

    def fetch(self,symbol,year=None):
        if symbol!='FPT':raise ValueError('No verified official disclosure adapter registered for this issuer')
        with self.client.stream('GET',FPT_LISTING) as response:
            response.raise_for_status();chunks=[];size=0
            for chunk in response.iter_bytes():
                size+=len(chunk)
                if size>8*1024*1024:raise ValueError('Disclosure listing exceeds 8 MiB')
                chunks.append(chunk)
        raw=b''.join(chunks);html=raw.decode('utf-8');records=parse_fpt_disclosures(html)
        if not records:raise ValueError('Official listing has no supported disclosure records; source format may have changed')
        if year is not None:records=[x for x in records if x['period_end'].startswith(str(year)+'-')]
        return dict(schema_version='financial.disclosures.v1',provider='fpt-ir',symbol=symbol,
            retrieved_at=utc_now_iso(),source_url=FPT_LISTING,source_sha256=hashlib.sha256(raw).hexdigest(),
            count=len(records),data=records,
            limitations=['Metadata belongs to official documents, not automatically to vendor values.',
                          'Original-release vintage is not certified by an archived listing.',
                          'Day precision uses end of publication day for conservative availability.'])


disclosure_provider=DisclosureProvider()
