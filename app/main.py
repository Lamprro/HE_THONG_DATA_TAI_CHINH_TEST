from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from vnstock import Fundamental, Market, Reference

app = FastAPI(
    title="HE THONG DATA TAI CHINH TEST - VnStock MVP",
    version="0.1.0",
    description="MVP API de kiem thu du lieu chung khoan Viet Nam qua thu vien VnStock.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

market = Market()
reference = Reference()
fundamental = Fundamental()


def normalize_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if not value or len(value) > 12 or not value.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Ma chung khoan khong hop le")
    return value


def dataframe_to_records(df: pd.DataFrame | None) -> list[dict]:
    if df is None or df.empty:
        return []
    return json.loads(df.to_json(orient="records", date_format="iso", force_ascii=False))


def upstream_error(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=502,
        detail={
            "message": "Khong lay duoc du lieu tu VnStock/provider tai thoi diem nay",
            "provider_error": str(exc),
        },
    )


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> str:
    return DASHBOARD_HTML


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "financial-data-vnstock-mvp",
        "vnstock_mode": "Unified UI v4",
    }


@app.get("/api/ohlcv")
def get_ohlcv(
    symbol: str = Query("FPT", min_length=1, max_length=12),
    start: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    end: date = Query(default_factory=date.today),
) -> dict:
    ticker = normalize_symbol(symbol)
    if start > end:
        raise HTTPException(status_code=400, detail="start phai nho hon hoac bang end")
    if (end - start).days > 3650:
        raise HTTPException(status_code=400, detail="MVP gioi han mot lan lay toi da 10 nam")

    try:
        df = market.equity.ohlcv(
            symbol=ticker,
            start=start.isoformat(),
            end=end.isoformat(),
        )
        return {
            "source": "vnstock",
            "dataset": "equity_ohlcv",
            "symbol": ticker,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "count": len(df),
            "data": dataframe_to_records(df),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise upstream_error(exc) from exc


@app.get("/api/company/{symbol}")
def get_company(symbol: str) -> dict:
    ticker = normalize_symbol(symbol)
    try:
        df = reference.company.info(symbol=ticker)
        return {
            "source": "vnstock",
            "dataset": "company_info",
            "symbol": ticker,
            "count": len(df),
            "data": dataframe_to_records(df),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise upstream_error(exc) from exc


@app.get("/api/financial/{symbol}")
def get_financial_statement(
    symbol: str,
    statement: Literal["balance_sheet", "income_statement", "cash_flow"] = "balance_sheet",
    period: Literal["year", "quarter"] = "year",
) -> dict:
    ticker = normalize_symbol(symbol)
    try:
        loader = getattr(fundamental.equity, statement)
        df = loader(symbol=ticker, period=period)
        return {
            "source": "vnstock",
            "dataset": statement,
            "symbol": ticker,
            "period": period,
            "count": len(df),
            "data": dataframe_to_records(df),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise upstream_error(exc) from exc


@app.get("/api/ratios/{symbol}")
def get_ratios(
    symbol: str,
    period: Literal["year", "quarter"] = "year",
) -> dict:
    ticker = normalize_symbol(symbol)
    try:
        df = fundamental.equity.ratios(symbol=ticker, period=period)
        return {
            "source": "vnstock",
            "dataset": "financial_ratios",
            "symbol": ticker,
            "period": period,
            "count": len(df),
            "data": dataframe_to_records(df),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise upstream_error(exc) from exc


DASHBOARD_HTML = r"""
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Financial Data MVP - VnStock</title>
  <style>
    :root { font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif; color: #111827; background: #f4f7fb; }
    * { box-sizing: border-box; }
    body { margin: 0; }
    main { max-width: 1180px; margin: 0 auto; padding: 32px 20px 56px; }
    h1 { margin: 0 0 8px; font-size: clamp(28px, 5vw, 44px); }
    .lead { color: #4b5563; margin: 0 0 24px; }
    .panel { background: white; border: 1px solid #e5e7eb; border-radius: 18px; padding: 18px; box-shadow: 0 8px 30px rgba(17,24,39,.05); }
    .controls { display: grid; grid-template-columns: 1.1fr 1fr 1fr 1.2fr auto; gap: 10px; align-items: end; }
    label { display: grid; gap: 6px; font-size: 13px; color: #374151; font-weight: 600; }
    input, select, button { width: 100%; min-height: 42px; border-radius: 10px; border: 1px solid #d1d5db; padding: 9px 11px; background: white; font: inherit; }
    button { border: 0; background: #111827; color: white; font-weight: 700; cursor: pointer; padding-inline: 18px; }
    button:hover { opacity: .9; }
    .quick { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
    .quick button { width: auto; min-height: 34px; background: #eef2ff; color: #3730a3; font-size: 13px; }
    .meta { display: flex; gap: 16px; flex-wrap: wrap; margin: 18px 0 10px; color: #4b5563; font-size: 14px; }
    pre { min-height: 360px; max-height: 620px; overflow: auto; background: #0b1020; color: #dbeafe; border-radius: 14px; padding: 16px; margin: 0; font-size: 12px; line-height: 1.55; }
    .status { font-weight: 700; }
    a { color: #4338ca; }
    @media (max-width: 900px) { .controls { grid-template-columns: 1fr 1fr; } .controls button { grid-column: 1 / -1; } }
    @media (max-width: 560px) { .controls { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
<main>
  <h1>Financial Data MVP</h1>
  <p class="lead">Thu nghiem lay du lieu thi truong Viet Nam tu <strong>VnStock</strong>. API docs: <a href="/docs">/docs</a>.</p>

  <section class="panel">
    <div class="controls">
      <label>Ma chung khoan
        <input id="symbol" value="FPT" maxlength="12" />
      </label>
      <label>Loai du lieu
        <select id="dataset">
          <option value="ohlcv">OHLCV</option>
          <option value="company">Company info</option>
          <option value="balance_sheet">Balance sheet</option>
          <option value="income_statement">Income statement</option>
          <option value="cash_flow">Cash flow</option>
          <option value="ratios">Financial ratios</option>
        </select>
      </label>
      <label>Tu ngay
        <input id="start" type="date" />
      </label>
      <label>Den ngay
        <input id="end" type="date" />
      </label>
      <button id="load">Lay data</button>
    </div>
    <div class="quick">
      <button data-symbol="FPT">FPT</button>
      <button data-symbol="VCB">VCB</button>
      <button data-symbol="HPG">HPG</button>
      <button data-symbol="VNM">VNM</button>
      <button data-symbol="MWG">MWG</button>
    </div>

    <div class="meta">
      <span>Trang thai: <span id="status" class="status">ready</span></span>
      <span id="request"></span>
    </div>
    <pre id="output">Bam "Lay data" de goi API.</pre>
  </section>
</main>
<script>
  const $ = (id) => document.getElementById(id);
  const iso = (d) => d.toISOString().slice(0, 10);
  const now = new Date();
  const before = new Date(now); before.setDate(now.getDate() - 30);
  $('start').value = iso(before); $('end').value = iso(now);

  document.querySelectorAll('[data-symbol]').forEach(btn => {
    btn.addEventListener('click', () => { $('symbol').value = btn.dataset.symbol; load(); });
  });
  $('load').addEventListener('click', load);

  async function load() {
    const symbol = $('symbol').value.trim().toUpperCase();
    const dataset = $('dataset').value;
    let url;
    if (dataset === 'ohlcv') {
      url = `/api/ohlcv?symbol=${encodeURIComponent(symbol)}&start=${$('start').value}&end=${$('end').value}`;
    } else if (dataset === 'company') {
      url = `/api/company/${encodeURIComponent(symbol)}`;
    } else if (dataset === 'ratios') {
      url = `/api/ratios/${encodeURIComponent(symbol)}?period=year`;
    } else {
      url = `/api/financial/${encodeURIComponent(symbol)}?statement=${dataset}&period=year`;
    }

    $('status').textContent = 'loading...';
    $('request').textContent = url;
    $('output').textContent = 'Dang goi VnStock...';
    try {
      const response = await fetch(url);
      const data = await response.json();
      $('status').textContent = response.ok ? `OK ${response.status}` : `ERROR ${response.status}`;
      $('output').textContent = JSON.stringify(data, null, 2);
    } catch (error) {
      $('status').textContent = 'NETWORK ERROR';
      $('output').textContent = String(error);
    }
  }
</script>
</body>
</html>
"""
