from __future__ import annotations

from datetime import date, timedelta

import httpx
import pandas as pd

from app.providers.base import ProviderInfo


class VnDirectProvider:
    BASE_URL = "https://api-finfo.vndirect.com.vn/v4"

    info = ProviderInfo(
        code="vndirect",
        name="VNDirect Finfo",
        adapter="http-json",
        status="active",
        auth_required=False,
        capabilities=(
            "ohlcv",
            "quote",
            "company",
            "financial_statements",
            "ratio",
        ),
    )

    def __init__(self) -> None:
        self.client = httpx.Client(
            timeout=20.0,
            follow_redirects=True,
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
        )

    # =========================================================
    # MARKET DATA
    # =========================================================

    def equity_ohlcv(
        self,
        symbol: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        query = (
            f"code:{symbol}"
            f"~date:gte:{start}"
            f"~date:lte:{end}"
        )

        all_rows: list[dict] = []

        page = 1
        page_size = 100

        total_pages: int | None = None

        while True:
            response = self.client.get(
                f"{self.BASE_URL}/stock_prices",
                params={
                    "sort": "date",
                    "q": query,
                    "size": page_size,
                    "page": page,
                },
            )

            response.raise_for_status()

            payload = response.json()

            rows = payload.get("data") or []

            if not rows:
                break

            all_rows.extend(rows)

            # VNDirect hiện thường chỉ trả totalPages đầy đủ ở page đầu.
            if total_pages is None:
                value = payload.get("totalPages")

                if value is not None:
                    total_pages = int(value)

            if total_pages is not None:
                if page >= total_pages:
                    break

            elif len(rows) < page_size:
                break

            page += 1

        return pd.DataFrame(all_rows)

    def equity_quote(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        df = self.equity_ohlcv(
            symbol=symbol,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
        )

        if df.empty:
            return df

        return df.head(1).reset_index(drop=True)

    # =========================================================
    # COMPANY
    # =========================================================

    def company(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        response = self.client.get(
            f"{self.BASE_URL}/stocks",
            params={
                "q": f"code:{symbol}",
                "size": 10,
                "page": 1,
            },
        )

        response.raise_for_status()

        payload = response.json()

        rows = payload.get("data") or []

        return pd.DataFrame(rows)

    # =========================================================
    # FINANCIAL STATEMENT HELPERS
    # =========================================================

    def latest_fiscal_date(
        self,
        symbol: str,
        model_type: int,
        report_type: str = "QUARTER",
    ) -> str | None:
        response = self.client.get(
            f"{self.BASE_URL}/financial_statements",
            params={
                "q": (
                    f"code:{symbol}"
                    f"~modelType:{model_type}"
                    f"~reportType:{report_type}"
                ),
                "sort": "fiscalDate",
                "size": 1,
                "page": 1,
            },
        )

        response.raise_for_status()

        payload = response.json()

        rows = payload.get("data") or []

        if not rows:
            return None

        return rows[0].get("fiscalDate")

    def detect_statement_model(
        self,
        symbol: str,
        statement_name: str,
        report_type: str = "QUARTER",
        fiscal_date: str | None = None,
    ) -> tuple[int, str] | None:
        """
        Tự tìm modelType thực tế mà symbol đang dùng.

        Ví dụ hiện tại:
        FPT:
            BALANCESHEET -> 1
            INCOME       -> 2
            CASHFLOW     -> 3

        VCB:
            BALANCESHEET -> 101
            INCOME       -> 102
            CASHFLOW     -> 103

        SSI:
            BALANCESHEET -> 89
            INCOME       -> 90
            CASHFLOW     -> 91

        Không hard-code các giá trị trên.
        VNDirect được dùng để tự xác định modelType.
        """

        # Nếu không truyền fiscal_date thì tìm kỳ gần nhất.
        if fiscal_date is None:
            response = self.client.get(
                f"{self.BASE_URL}/financial_statements",
                params={
                    "q": (
                        f"code:{symbol}"
                        f"~reportType:{report_type}"
                    ),
                    "sort": "fiscalDate",
                    "size": 1,
                    "page": 1,
                },
            )

            response.raise_for_status()

            payload = response.json()

            rows = payload.get("data") or []

            if not rows:
                return None

            fiscal_date = rows[0].get("fiscalDate")

            if not fiscal_date:
                return None

        # Lấy tất cả modelType xuất hiện trong đúng kỳ báo cáo.
        response = self.client.get(
            f"{self.BASE_URL}/financial_statements",
            params={
                "q": (
                    f"code:{symbol}"
                    f"~reportType:{report_type}"
                    f"~fiscalDate:{fiscal_date}"
                ),
                "size": 1000,
                "page": 1,
            },
        )

        response.raise_for_status()

        payload = response.json()

        rows = payload.get("data") or []

        if not rows:
            return None

        model_types = sorted(
            {
                int(row["modelType"])
                for row in rows
                if row.get("modelType") is not None
            }
        )

        target_name = statement_name.strip().upper()

        # Kiểm tra từng modelType trong financial_models
        # để biết đó là BALANCESHEET / INCOME / CASHFLOW.
        for model_type in model_types:
            model_response = self.client.get(
                f"{self.BASE_URL}/financial_models",
                params={
                    "q": f"modelType:{model_type}",
                    "size": 1,
                    "page": 1,
                },
            )

            model_response.raise_for_status()

            model_payload = model_response.json()

            model_rows = model_payload.get("data") or []

            if not model_rows:
                continue

            model_name = str(
                model_rows[0].get("modelTypeName") or ""
            ).strip().upper()

            if model_name == target_name:
                return model_type, fiscal_date

        return None

    # =========================================================
    # GENERIC FINANCIAL STATEMENT
    # =========================================================

    def financial_statement(
        self,
        symbol: str,
        statement_name: str,
        fiscal_date: str | None = None,
        report_type: str = "QUARTER",
    ) -> pd.DataFrame:
        detected = self.detect_statement_model(
            symbol=symbol,
            statement_name=statement_name,
            report_type=report_type,
            fiscal_date=fiscal_date,
        )

        if detected is None:
            return pd.DataFrame()

        model_type, resolved_fiscal_date = detected

        # -----------------------------------------------------
        # 1. Lấy số liệu BCTC
        # -----------------------------------------------------

        statement_response = self.client.get(
            f"{self.BASE_URL}/financial_statements",
            params={
                "q": (
                    f"code:{symbol}"
                    f"~modelType:{model_type}"
                    f"~reportType:{report_type}"
                    f"~fiscalDate:{resolved_fiscal_date}"
                ),
                "size": 1000,
                "page": 1,
            },
        )

        statement_response.raise_for_status()

        statement_payload = statement_response.json()

        statement_rows = (
            statement_payload.get("data") or []
        )

        if not statement_rows:
            return pd.DataFrame()

        # -----------------------------------------------------
        # 2. Lấy metadata/tên chỉ tiêu
        # -----------------------------------------------------

        model_response = self.client.get(
            f"{self.BASE_URL}/financial_models",
            params={
                "q": f"modelType:{model_type}",
                "size": 1000,
                "page": 1,
            },
        )

        model_response.raise_for_status()

        model_payload = model_response.json()

        model_rows = (
            model_payload.get("data") or []
        )

        if not model_rows:
            result = pd.DataFrame(statement_rows)
            result.attrs["financial_metadata"] = {"source_url": str(statement_response.url)}
            return result

        # -----------------------------------------------------
        # 3. Merge numericValue với tên item
        # -----------------------------------------------------

        statement_df = pd.DataFrame(statement_rows)
        model_df = pd.DataFrame(model_rows)

        model_columns = [
            "modelType",
            "itemCode",
            "modelTypeName",
            "modelVnDesc",
            "companyForm",
            "itemVnName",
            "itemEnName",
            "displayOrder",
            "displayLevel",
            "formType",
        ]

        available_columns = [
            column
            for column in model_columns
            if column in model_df.columns
        ]

        model_df = model_df[available_columns]

        result = statement_df.merge(
            model_df,
            on=[
                "modelType",
                "itemCode",
            ],
            how="left",
        )

        # -----------------------------------------------------
        # 4. Sắp theo thứ tự hiển thị của VNDirect
        # -----------------------------------------------------

        if "displayOrder" in result.columns:
            result = result.sort_values(
                "displayOrder",
                na_position="last",
            )

        result = result.reset_index(drop=True)
        result.attrs["financial_metadata"] = {"source_url": str(statement_response.url)}
        return result

    # =========================================================
    # FINANCIAL STATEMENT WRAPPERS
    # =========================================================

    def balance_sheet(
        self,
        symbol: str,
        fiscal_date: str | None = None,
        report_type: str = "QUARTER",
    ) -> pd.DataFrame:
        return self.financial_statement(
            symbol=symbol,
            statement_name="BALANCESHEET",
            fiscal_date=fiscal_date,
            report_type=report_type,
        )

    def income_statement(
        self,
        symbol: str,
        fiscal_date: str | None = None,
        report_type: str = "QUARTER",
    ) -> pd.DataFrame:
        return self.financial_statement(
            symbol=symbol,
            statement_name="INCOME",
            fiscal_date=fiscal_date,
            report_type=report_type,
        )

    def cash_flow(
        self,
        symbol: str,
        fiscal_date: str | None = None,
        report_type: str = "QUARTER",
    ) -> pd.DataFrame:
        return self.financial_statement(
            symbol=symbol,
            statement_name="CASHFLOW",
            fiscal_date=fiscal_date,
            report_type=report_type,
        )

    def ratios(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        ratio_codes = (
            "PRICE_TO_EARNINGS",
            "PRICE_TO_BOOK",
            "EPS_TR",
            "ROAE_TR_AVG5Q",
            "ROAA_TR_AVG5Q",
            "DIVIDEND_YIELD",
        )

        rows: list[dict] = []

        if (start is None) != (end is None):
            raise ValueError("Both start and end are required for ratio history")
        if start is not None and (date.fromisoformat(start) > date.fromisoformat(end)
                or date.fromisoformat(end).year - date.fromisoformat(start).year > 15):
            raise ValueError("Invalid ratio history window; maximum 15 calendar years")
        seen = set()
        for ratio_code in ratio_codes:
            query = f"code:{symbol}~ratioCode:{ratio_code}"
            if start is not None:
                query += f"~reportDate:gte:{start}~reportDate:lte:{end}"
            page, total_pages = 1, 1
            while page <= total_pages:
                response = self.client.get(f"{self.BASE_URL}/ratios", params={
                    "q": query, "sort": "reportDate:desc", "size": 1000 if start else 1, "page": page})
                response.raise_for_status()
                payload = response.json()
                data = payload.get("data")
                if not isinstance(data, list):
                    raise ValueError("Invalid ratio source response")
                total_pages = int(payload.get("totalPages", 1)) if start else 1
                if total_pages > 50 or (page < total_pages and not data):
                    raise ValueError("Incomplete or oversized ratio pagination")
                for row in data:
                    report_date = date.fromisoformat(row["reportDate"]).isoformat()
                    identity = ratio_code, report_date
                    if (row.get("code") != symbol or row.get("ratioCode") != ratio_code
                            or (start and not start <= report_date <= end) or identity in seen):
                        raise ValueError("Mismatched or duplicate ratio source row")
                    seen.add(identity)
                    rows.append(row)
                page += 1
        result = pd.DataFrame(rows)
        result.attrs["ratio_metadata"] = {
            "contract": "vndirect.ratios.history.v1", "source_url": self.BASE_URL + "/ratios",
            "mode": "HISTORICAL" if start else "LATEST", "start": start, "end": end,
            "availability": "REPORT_DATE_IS_NOT_VERIFIED_PUBLICATION_DATE",
            "vintage": "CURRENT_SOURCE_VINTAGE", "missing_values": "PRESERVED_AS_NULL"}
        return result
    
vndirect_provider = VnDirectProvider()
