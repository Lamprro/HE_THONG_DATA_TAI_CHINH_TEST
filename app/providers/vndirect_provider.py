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
            return pd.DataFrame(statement_rows)

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

        return result.reset_index(drop=True)

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

        for ratio_code in ratio_codes:
            response = self.client.get(
                f"{self.BASE_URL}/ratios",
                params={
                    "q": (
                        f"code:{symbol}"
                        f"~ratioCode:{ratio_code}"
                    ),
                    "sort": "reportDate:desc",
                    "size": 1,
                    "page": 1,
                },
            )

            response.raise_for_status()

            payload = response.json()

            data = payload.get("data") or []

            if data:
                rows.append(data[0])

        return pd.DataFrame(rows)
    
vndirect_provider = VnDirectProvider()