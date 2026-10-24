"""Parse the report's separate header and body, never chart cells or page dates."""
import calendar
import hashlib
import re
from decimal import Decimal, InvalidOperation
from bs4 import BeautifulSoup
import pandas as pd
from app.core.financial_metadata import _plain, _scope


def period_from_header(text):
    value = _plain(text)
    match = re.fullmatch(r"quy\s*([1-4])\s*[-/]?\s*(20\d{2})", value)
    if match:
        quarter, year = map(int, match.groups())
        month = quarter * 3
        return f"{year}-{month:02d}-{calendar.monthrange(year,month)[1]}", "QUARTER"
    match = re.fullmatch(r"(?:nam\s*)?(20\d{2})", value)
    if match:
        return f"{match[1]}-12-31", "YEAR"
    raise ValueError(f"Unrecognized CafeF report header: {text}")


def number(text):
    value = text.strip().replace('\xa0','').replace(' ','')
    if value in {'','-','--','N/A'}:
        return None
    negative = value.startswith('(') and value.endswith(')')
    if negative:value=value[1:-1]
    # Vietnamese thousands separator and decimal comma; ambiguous formats are rejected.
    if not re.fullmatch(r"-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?",value):
        raise ValueError(f"Invalid CafeF numeric cell: {text}")
    try:parsed=Decimal(value.replace('.','').replace(',','.'))
    except InvalidOperation as exc:raise ValueError('Invalid numeric cell') from exc
    return str(-parsed if negative else parsed)


def parse_cafef_statement(html, source_url, statement, symbol=None):
    soup=BeautifulSoup(html,'html.parser')
    company=soup.select_one('#div_cf_BoxContent a[href]')
    if symbol is not None:
        if company is None or not re.search(r'/'+re.escape(symbol)+r'-',company.get('href',''),re.I):
            raise ValueError('CAFEF_COMPANY_IDENTITY_MISMATCH')
    header=soup.select_one('#tblGridData')
    body=soup.select_one('#tableContent')
    if header is None or body is None:raise ValueError('CafeF report header/body missing')
    # CafeF can render bank values under the non-bank template. Those numbers
    # must not be relabelled as sales, inventory or working capital.
    bank=company is not None and 'ngan hang' in _plain(company.get_text(' ',strip=True))
    labels=_plain(' '.join(row.find(['td','th']).get_text(' ',strip=True)
                          for row in body.find_all('tr',recursive=False) if row.find(['td','th'])))
    if not labels:
        labels=_plain(body.get_text(' ',strip=True))
    if bank and ((statement=='INCOME' and 'doanh thu ban hang' in labels)
                 or (statement=='BALANCESHEET' and 'tai san ngan han' in labels)):
        raise ValueError('CAFEF_BANK_TEMPLATE_MISMATCH: bank values have non-bank item labels')
    headings=header.select('td.h_t, th.h_t')
    if not headings:raise ValueError('CafeF report period headers missing')
    periods=[period_from_header(x.get_text(' ',strip=True)) for x in headings]
    if len(set(periods))!=len(periods):raise ValueError('Duplicate CafeF report periods')
    records=[];seen=set()
    for row in body.find_all('tr'):
        if row.find_parent('table') is not body:continue
        cells=row.find_all(['td','th'],recursive=False)
        if not cells:continue
        if len(cells) not in {len(periods)+1,len(periods)+2}:raise ValueError('CafeF report column count mismatch')
        label=cells[0].get_text(' ',strip=True)
        source_id=row.get('id')
        values=[number(c.get_text(' ',strip=True)) for c in cells[1:len(periods)+1]]
        if not any(v is not None for v in values):continue # structural heading, not a zero
        if not label or not source_id:raise ValueError('CafeF numeric row has no stable item identity')
        # Same row ID can occur twice for distinct source labels. Preserve both deterministically.
        identity=source_id+'_'+hashlib.sha256(label.encode()).hexdigest()[:10]
        for (end,kind),value in zip(periods,values):
            if value is None:continue
            key=(identity,end)
            if key in seen:raise ValueError('Duplicate CafeF financial cell')
            seen.add(key)
            records.append(dict(itemCode='CAF_'+identity,itemVnName=label,itemEnName=label,
                                sourceItemCode=source_id,fiscalDate=end,reportType=kind,numericValue=value))
    if not records:raise ValueError('CafeF report contains no numeric cells')
    result=pd.DataFrame(records)
    # The page-level "ty dong" widget conflicts with the raw full-amount cells.
    # Keep it as unverified evidence, never multiply raw values by a guessed scale.
    unit=soup.select_one('#ContentPlaceHolder1_trDonVi')
    result.attrs['financial_metadata']={
        'source_url':source_url,'source_sha256':hashlib.sha256(html.encode()).hexdigest(),
        'report_scope':_scope(' '.join(x.get_text(' ',strip=True) for x in soup.select('h1, #tableContent caption'))) or 'UNKNOWN',
        'unverified_display_unit':unit.get_text(' ',strip=True) if unit else None,
        'limitations':['RAW_CELL_UNIT_NOT_CERTIFIED_BY_DISPLAY_WIDGET'],
        'period_headers':[x.get_text(' ',strip=True) for x in headings],
    }
    return result
