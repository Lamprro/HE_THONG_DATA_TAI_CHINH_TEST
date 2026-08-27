from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd


def dataframe_to_records(df: pd.DataFrame | None) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    return json.loads(df.to_json(orient="records", date_format="iso", force_ascii=False))


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
