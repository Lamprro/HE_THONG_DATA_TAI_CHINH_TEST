from __future__ import annotations

from datetime import date, datetime, timedelta
from io import StringIO

import httpx
import pandas as pd

from app.providers.base import ProviderInfo


class CafeFProvider:
    PRICE_URL = (
        "https://cafef.vn/"
        "du-lieu/ajax/pagenew/datahistory/pricehistory.ashx"
    )

    FINANCIAL_URL = "https://s.cafef.vn/bao-cao-tai-chinh"
    COMPANY_AJAX_URL = (
    "https://cafef.vn/du-lieu/Ajax/CongTy"
)

    info = ProviderInfo(
        code="cafef",
        name="CafeF",
        adapter="http-json-html",
        status="experimental",
        auth_required=False,
        capabilities=(
            "ohlcv",
            "quote",
            "company",
            "financial_statements",
            "management",
            "subsidiaries",
        ),
    )

    def __init__(self) -> None:
        self.client = httpx.Client(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/json,text/plain,*/*"
                ),
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://cafef.vn/",
            },
        )

    # =========================================================
    # MARKET DATA
    # =========================================================

    @staticmethod
    def _format_date(value: str) -> str:
        parsed = datetime.strptime(
            value,
            "%Y-%m-%d",
        )

        return parsed.strftime("%m/%d/%Y")

    def _fetch_range(
        self,
        symbol: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        page = 1
        page_size = 20

        all_rows: list[dict] = []

        total_pages: int | None = None

        while True:
            response = self.client.get(
                self.PRICE_URL,
                params={
                    "Symbol": symbol,
                    "StartDate": self._format_date(start),
                    "EndDate": self._format_date(end),
                    "PageIndex": page,
                    "PageSize": page_size,
                },
            )

            response.raise_for_status()

            payload = response.json()

            if payload.get("Success") is not True:
                message = payload.get(
                    "Message",
                    "Unknown CafeF error",
                )

                raise RuntimeError(
                    f"CafeF returned an error: {message}"
                )

            data = payload.get("Data") or {}

            rows = data.get("Data") or []

            if not rows:
                break

            all_rows.extend(rows)

            if total_pages is None:
                total_count = int(
                    data.get("TotalCount") or 0
                )

                total_pages = (
                    total_count + page_size - 1
                ) // page_size

            if total_pages == 0:
                break

            if page >= total_pages:
                break

            page += 1

        return pd.DataFrame(all_rows)

    def equity_ohlcv(
        self,
        symbol: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        start_date = datetime.strptime(
            start,
            "%Y-%m-%d",
        ).date()

        end_date = datetime.strptime(
            end,
            "%Y-%m-%d",
        ).date()

        if start_date > end_date:
            raise ValueError(
                "start must be <= end"
            )

        all_frames: list[pd.DataFrame] = []

        current_end = end_date

        # CafeF có giới hạn khoảng dữ liệu mỗi request,
        # nên chia thành từng đoạn ~90 ngày.
        while current_end >= start_date:
            chunk_start = max(
                start_date,
                current_end - timedelta(days=89),
            )

            df = self._fetch_range(
                symbol=symbol,
                start=chunk_start.isoformat(),
                end=current_end.isoformat(),
            )

            if not df.empty:
                all_frames.append(df)

            current_end = (
                chunk_start - timedelta(days=1)
            )

        if not all_frames:
            return pd.DataFrame()

        result = pd.concat(
            all_frames,
            ignore_index=True,
        )

        if "Ngay" in result.columns:
            result = result.drop_duplicates(
                subset=["Symbol", "Ngay"]
                if "Symbol" in result.columns
                else ["Ngay"]
            )

        return result.reset_index(drop=True)

    def equity_quote(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        end_date = date.today()

        start_date = (
            end_date - timedelta(days=30)
        )

        df = self.equity_ohlcv(
            symbol=symbol,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
        )

        if df.empty:
            return df

        return df.head(1).reset_index(
            drop=True
        )

    # =========================================================
    # FINANCIAL STATEMENTS
    # =========================================================

    def financial_statement(
        self,
        symbol: str,
        statement_type: str,
        year: int | None = None,
        period: int = 1,
    ) -> pd.DataFrame:
        """
        statement_type:
            BALANCESHEET
            INCOME
            CASHFLOW

        period:
            0 = yearly
            1 = quarterly
            2 = cumulative 6 months
        """

        report_types = {
            "BALANCESHEET": (
                "BSheet",
                "can-doi-ke-toan.chn",
            ),
            "INCOME": (
                "IncSta",
                "ket-qua-hoat-dong-kinh-doanh.chn",
            ),
            "CASHFLOW": (
                "CashFlow",
                "luu-chuyen-tien-te.chn",
            ),
        }

        statement_name = (
            statement_type
            .strip()
            .upper()
        )

        if statement_name not in report_types:
            raise ValueError(
                "statement_type must be "
                "BALANCESHEET, INCOME or CASHFLOW"
            )

        if period not in (0, 1, 2):
            raise ValueError(
                "period must be 0, 1 or 2"
            )

        resolved_year = (
            year or date.today().year
        )

        report_code, slug = (
            report_types[statement_name]
        )

        url = (
            f"{self.FINANCIAL_URL}/"
            f"{symbol}/"
            f"{report_code}/"
            f"{resolved_year}/"
            f"{period}/"
            f"0/0/"
            f"{slug}"
        )

        response = self.client.get(url)

        response.raise_for_status()

        tables = pd.read_html(
            StringIO(response.text),
            attrs={
                "id": "tableContent"
            },
        )

        if not tables:
            return pd.DataFrame()

        df = tables[0]

        # CafeF có thể trả MultiIndex columns.
        # Hiện tại chỉ flatten, chưa chuẩn hóa dữ liệu.
        if isinstance(
            df.columns,
            pd.MultiIndex,
        ):
            df.columns = [
                " | ".join(
                    str(value)
                    for value in column
                    if (
                        str(value) != "nan"
                        and not str(value).startswith(
                            "Unnamed"
                        )
                    )
                ).strip()
                for column in df.columns
            ]
        else:
            df.columns = [
                str(column)
                for column in df.columns
            ]

        return df.reset_index(drop=True)

    def balance_sheet(
        self,
        symbol: str,
        year: int | None = None,
        period: int = 1,
    ) -> pd.DataFrame:
        return self.financial_statement(
            symbol=symbol,
            statement_type="BALANCESHEET",
            year=year,
            period=period,
        )

    def income_statement(
        self,
        symbol: str,
        year: int | None = None,
        period: int = 1,
    ) -> pd.DataFrame:
        return self.financial_statement(
            symbol=symbol,
            statement_type="INCOME",
            year=year,
            period=period,
        )

    def cash_flow(
        self,
        symbol: str,
        year: int | None = None,
        period: int = 1,
    ) -> pd.DataFrame:
        return self.financial_statement(
            symbol=symbol,
            statement_type="CASHFLOW",
            year=year,
            period=period,
        )

    # =========================================================
    # COMPANY INFORMATION
    # =========================================================

    @staticmethod
    def _flatten_columns(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        df = df.copy()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [
                " | ".join(
                    str(value)
                    for value in column
                    if (
                        str(value) != "nan"
                        and not str(value).startswith("Unnamed")
                    )
                ).strip()
                for column in df.columns
            ]
        else:
            df.columns = [
                str(column)
                for column in df.columns
            ]

        return df

    def _company_html_tables(
        self,
        symbol: str,
        endpoint: str,
    ) -> pd.DataFrame:
        response = self.client.get(
            f"{self.COMPANY_AJAX_URL}/{endpoint}.aspx",
            params={
                "sym": symbol,
            },
        )

        response.raise_for_status()

        try:
            tables = pd.read_html(
                StringIO(response.text)
            )
        except ValueError:
            return pd.DataFrame()

        if not tables:
            return pd.DataFrame()

        frames: list[pd.DataFrame] = []

        for index, table in enumerate(tables):
            table = self._flatten_columns(table)

            table.insert(
                0,
                "tableIndex",
                index,
            )

            frames.append(table)

        return pd.concat(
            frames,
            ignore_index=True,
            sort=False,
        )

    def company(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        return self._company_html_tables(
            symbol=symbol,
            endpoint="ThongTinChung",
        )

    def management(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        return self._company_html_tables(
            symbol=symbol,
            endpoint="BanLanhDao",
        )

    def subsidiaries(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        return self._company_html_tables(
            symbol=symbol,
            endpoint="CongTyCon",
        )
    
cafef_provider = CafeFProvider()