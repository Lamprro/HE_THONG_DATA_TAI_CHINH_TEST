"""Small, explicit adapters for official issuer listings. No date or scope guessing."""
import calendar
import hashlib
import json
import re
from datetime import date, datetime
from urllib.parse import urlsplit, quote, unquote, urljoin, parse_qs
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from app.core.financial_metadata import _plain

ISSUERS = {
    'EIB': {'provider': 'eib-ir', 'source_code': 'EIB_IR',
            'listing': 'https://eximbank.com.vn/bao-cao-tai-chinh',
            'pdf_host': 'media.eximbank.com.vn', 'pdf_prefix': '/exim/files/'},
    'HSG': {'provider': 'hsg-ir', 'source_code': 'HSG_IR',
            'listing': 'https://hoasengroup.vn/vi/quan-he-co-dong/bao-cao-tai-chinh/29/',
            'pdf_host': 'hoasengroup.vn', 'pdf_prefix': '/wp-content/uploads/'},
    'ACB': {'provider': 'acb-ir', 'source_code': 'ACB_IR',
            'listing': 'https://acb.com.vn/nha-dau-tu/bao-cao-tai-chinh',
            'pdf_host': 'acb.com.vn', 'pdf_prefix': '/acbwebsite/'},
    'FPT': {'provider': 'fpt-ir', 'source_code': 'FPT_IR',
            'listing': 'https://fpt.com/vi/nha-dau-tu/thong-tin-cong-bo',
            'pdf_host': 'fpt.com', 'pdf_prefix': '/api/media/'},
    'HPG': {'provider': 'hpg-ir', 'source_code': 'HPG_IR',
            'listing': 'https://www.hoaphat.com.vn/quan-he-co-dong/bao-cao-tai-chinh',
            'pdf_host': 'file.hoaphat.com.vn', 'pdf_prefix': '/hoaphat-com-vn/'},
    'VNM': {'provider': 'vnm-ir', 'source_code': 'VNM_IR',
            'listing': 'https://www.vinamilk.com.vn/investor/reports/financial',
            'pdf_host': 'd8um25gjecm9v.cloudfront.net', 'pdf_prefix': '/cms/'},
}


def allowed_pdf(symbol, url):
    source = ISSUERS[symbol]
    u = urlsplit(url)
    return (u.scheme == 'https' and u.netloc == source['pdf_host']
            and u.path.startswith(source['pdf_prefix']) and u.path.lower().endswith('.pdf')
            and not u.query and not u.fragment
            and not re.search(r'%2f|%5c|%25', u.path, re.I)
            and not any(x in unquote(u.path) for x in ('..', '%', '\\'))
            and all(ord(c) >= 32 and ord(c) != 127 for c in unquote(u.path)))


def report_period(title):
    plain = _plain(title)
    years = set(re.findall(r'\b20\d{2}\b', plain))
    if len(years) != 1:
        return None
    year = int(next(iter(years)))
    quarter = re.search(r'\b(?:quy\s*|q)0?(iv|iii|ii|i|[1-4])\b', plain)
    if quarter:
        q = int(quarter[1]) if quarter[1].isdigit() else {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4}[quarter[1]]
        month, kind = q * 3, 'QUARTER'
    elif re.search(r'ban nien|6 thang|30[./-]0?6', plain):
        month, kind = 6, 'HALF_YEAR'
    elif re.search(r'\bnam\s+20\d{2}\b', plain):
        month, kind = 12, 'ANNUAL'
    else:
        return None
    return date(year, month, calendar.monthrange(year, month)[1]), kind


def make_document(symbol, record, listing_url, period=None):
    title = record['name']
    plain = _plain(title)
    if not ('bao cao tai chinh' in plain or 'bctc' in plain):
        return None
    if ('giai trinh' in plain and not record.get('financial_attachment_verified')) or 'gia han' in plain or 'hop dong' in plain:
        return None
    period = period or report_period(title)
    if not period or not allowed_pdf(symbol, record['pdfUrl']):
        return None
    end, kind = period
    try:
        published = date.fromisoformat(record['actualPublishedAt'])
    except (ValueError, TypeError):
        return None
    if not end <= published <= datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date():
        return None
    consolidated = 'hop nhat' in plain
    separate = bool(re.search(r'rieng|cong ty me', plain))
    scope = 'UNKNOWN' if consolidated == separate else 'CONSOLIDATED' if consolidated else 'SEPARATE'
    ident = str(record['id'])
    return dict(document_id=ident, symbol=symbol, title=title, period_end=end.isoformat(),
                report_kind=kind, report_scope=scope, published_on=published.isoformat(),
                publication_precision='DAY', available_at=f'{published}T23:59:59.999999+07:00',
                revision_status='RESTATED' if re.search(r'dieu chinh|dinh chinh|thay the|restated', plain) else 'UNKNOWN',
                report_version_id=ISSUERS[symbol]['source_code']+':'+ident,
                document_url=record['pdfUrl'], publication_evidence={'field': 'actualPublishedAt', 'value': str(published)},
                scope_evidence={'field': 'name', 'value': title},
                period_evidence={'field': 'name', 'value': title},
                source_record_sha256=hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                source_record=record, listing_url=listing_url,
                vintage_status='ARCHIVED_DISCLOSURE_RECONSTRUCTION', vendor_value_binding='UNVERIFIED',
                training_eligible=False)


def parse_hpg(html, listing_url):
    soup = BeautifulSoup(html, 'html.parser')
    output = []
    for row in soup.select('.item'):
        anchor, time = row.select_one(':scope > .name a[href]'), row.select_one(':scope > .time')
        if not anchor or not time:
            continue
        try:
            published = datetime.strptime(time.get_text(strip=True), '%d/%m/%Y').date().isoformat()
        except ValueError:
            continue
        record = dict(id=hashlib.sha256(anchor['href'].encode()).hexdigest(), name=anchor.get_text(' ', strip=True),
                      pdfUrl=anchor['href'], actualPublishedAt=published,
                      publication_source_text=time.get_text(strip=True))
        doc = make_document('HPG', record, listing_url)
        if doc:
            output.append(doc)
    more = soup.select_one('a[rel="next"]') is not None
    return output, more


def parse_vnm(html, listing_url):
    output = []
    for anchor in BeautifulSoup(html, 'html.parser').select('a[href]'):
        url = anchor['href']
        if not allowed_pdf('VNM', url):
            continue
        title = anchor.get_text(' ', strip=True)
        match = re.match(r'(\d{2}/\d{2}/\d{4})\s+(20\d{2})\s+Q([1-4])\s+(.+)', title)
        if not match:
            continue
        published = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat()
        # Listing Q4 may contain audited annual and unaudited quarterly PDFs.
        # This is document period only, never a claim that the numeric column is quarterly.
        normalized_title = f'{match[4]} - Q{match[3]} {match[2]}'
        record = dict(id=hashlib.sha256(url.encode()).hexdigest(), name=normalized_title,
                      pdfUrl=url, actualPublishedAt=published, publication_source_text=title)
        doc = make_document('VNM', record, listing_url)
        if doc:
            doc['report_kind'] = 'UNKNOWN'  # determine annual/YTD/quarter from the PDF column
            output.append(doc)
    return output, False


def parse_acb(html, listing_url):
    soup = BeautifulSoup(html, 'html.parser')
    script = soup.find('script', id='__NEXT_DATA__')
    if not script:
        raise ValueError('ACB listing format changed')
    records = {}
    def collect(node):
        if isinstance(node, dict):
            if node.get('id') and node.get('title') and isinstance(node.get('featured_image'), dict):
                records[node['title']] = node
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for value in node:
                collect(value)
    collect(json.loads(script.string)['props']['pageProps'])
    output = []
    for card in soup.select('.item-card-x'):
        title_node, day = card.select_one('.title'), card.select_one('.day')
        if not title_node or not day:
            continue
        title = title_node.get_text(' ', strip=True)
        source = records.get(title)
        if not source:
            continue
        # Use the date actually displayed for this card, never created_at/updated_at.
        published = datetime.strptime(day.get_text(strip=True), '%d/%m/%Y').date().isoformat()
        url = quote(source['featured_image'].get('path',''), safe=':/')
        record = dict(id=str(source['id']), name=title, pdfUrl=url, actualPublishedAt=published,
                      publication_source_field='card.day', publication_source_text=day.get_text(strip=True),
                      source_record=source)
        doc = make_document('ACB', record, listing_url)
        if doc:
            output.append(doc)
    return output, False  # server-rendered page only; the site's client pagination is not supported


def hsg_period(title):
    plain = _plain(title.replace('\u2013','-').replace('\u2014','-'))
    years = re.search(r'(20\d{2})\s*[-–]\s*(20\d{2})', plain)
    if not years or int(years[2]) != int(years[1]) + 1:
        return None
    start, end = int(years[1]), int(years[2])
    quarter = re.search(r'quy\s*(iv|iii|ii|i|[1-4])\b', plain)
    if quarter:
        q = int(quarter[1]) if quarter[1].isdigit() else {'i':1,'ii':2,'iii':3,'iv':4}[quarter[1]]
        year, month = (start,12) if q == 1 else (end,(q-1)*3)
        return date(year, month, calendar.monthrange(year,month)[1]), 'QUARTER'
    if re.search(r'6 thang|ban nien|giua nien do', plain):
        return date(end,3,31), 'HALF_YEAR'
    if 'nien do' in plain or 'ndtc' in plain:
        return date(end,9,30), 'ANNUAL'
    return None


def parse_hsg(html, listing_url):
    soup = BeautifulSoup(html, 'html.parser')
    output = {}
    for item in soup.select('.wrap-item .item-content'):
        heading, day = item.select_one('.title-post'), item.select_one('.date')
        if not heading or not day:
            continue
        title = heading.get_text(' ', strip=True)
        period = hsg_period(title)
        stamp = re.search(r'\b(\d{2}/\d{2}/20\d{2})\b', day.get_text())
        if not period or not stamp:
            continue
        published = datetime.strptime(stamp[1], '%d/%m/%Y').date().isoformat()
        for attachment in item.select('.item-sub'):
            anchor, label = attachment.select_one('a.btn-download[href]'), attachment.select_one('.btn-viewer')
            if not anchor or not label:
                continue
            attachment_title = label.get_text(' ',strip=True)
            plain_attachment = _plain(attachment_title).replace('_',' ')
            if not re.search(r'\bbctc\b|bao cao tai chinh', plain_attachment) or 'giai trinh' in plain_attachment:
                continue
            # Preserve the issuer's existing escapes/parentheses so a refresh
            # does not create a second identity for the same archived document.
            url = quote(urljoin(listing_url, anchor['href']),safe=':/%()')
            ident = hashlib.sha256(url.encode()).hexdigest()
            record = dict(id=ident, name=title, pdfUrl=url, actualPublishedAt=published,
                          publication_source_field='article.date', publication_source_text=day.get_text(' ',strip=True),
                          attachment_title=attachment_title, financial_attachment_verified=True,
                          fiscal_calendar='OCTOBER_TO_SEPTEMBER')
            doc = make_document('HSG',record,listing_url,period)
            if doc:
                doc['fiscal_calendar']='OCTOBER_TO_SEPTEMBER'
                doc['period_evidence']={'field':'name','value':title,'calendar':'OCTOBER_TO_SEPTEMBER'}
                output[ident]=doc
    current=int(parse_qs(urlsplit(listing_url).query).get('pg',['1'])[0])
    more=any(int(parse_qs(urlsplit(a['href']).query).get('pg',['0'])[0]) > current
             for a in soup.select('.alm-paging a[href]'))
    return list(output.values()), more


def parse_eib(html, listing_url):
    records = {}
    for script in BeautifulSoup(html,'html.parser').find_all('script'):
        text = script.string or ''
        if not text.startswith('self.__next_f.push('):
            continue
        try:
            payload = json.loads(text[text.index('(')+1:text.rfind(')')])
        except (ValueError,IndexError):
            continue
        if len(payload)<2 or not isinstance(payload[1],str):
            continue
        for match in re.finditer(r'\{"id":',payload[1]):
            try:
                row,_ = json.JSONDecoder().raw_decode(payload[1][match.start():])
            except ValueError:
                continue
            if row.get('title') and isinstance(row.get('featured_image_1'),dict):
                records[str(row['id'])]=row
    output=[]
    for ident,row in records.items():
        published=row.get('published_start')
        if not published:
            continue
        try:
            stamp=datetime.fromisoformat(published)
            if stamp.tzinfo is None:
                continue
            day=stamp.astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date().isoformat()
        except ValueError:
            continue
        url=quote(unquote(row['featured_image_1'].get('path','')),safe=':/')
        record=dict(id=ident,name=row['title'],pdfUrl=url,actualPublishedAt=day,
                    publication_source_field='published_start',publication_source_text=published,source_record=row)
        doc=make_document('EIB',record,listing_url)
        if doc:
            output.append(doc)
    return output, False
