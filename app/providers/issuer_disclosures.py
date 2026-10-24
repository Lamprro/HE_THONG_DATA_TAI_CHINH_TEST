"""Small, explicit adapters for official issuer listings. No date or scope guessing."""
import calendar
import hashlib
import json
import re
from datetime import date, datetime
from urllib.parse import urlsplit, quote
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from app.core.financial_metadata import _plain

ISSUERS = {
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
            and not u.query and not u.fragment and not any(x in u.path.replace('%20','') for x in ('..', '%', '\\')))


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
    if 'giai trinh' in plain or 'gia han' in plain or 'hop dong' in plain:
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
