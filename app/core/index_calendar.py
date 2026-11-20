"""Verified exceptional closures, not a complete historical exchange calendar."""
from datetime import date

HOSE_KNOWN_CLOSURES = {date(2018,1,23), date(2018,1,24)}
HOSE_CLOSURE_SOURCES = [
    "https://baochinhphu.vn/hose-tiep-tuc-ngung-giao-dich-vao-ngay-24-1-102233813.htm",
    "https://baochinhphu.vn/hose-giao-dich-tro-lai-sau-hai-ngay-dong-cua-102233882.htm",
]


def validate_index_session(symbol: str, day: date):
    if symbol in {"VNINDEX", "VN30"} and day in HOSE_KNOWN_CLOSURES:
        raise ValueError(f"Known HOSE closure date in source: symbol={symbol}, date={day}")
