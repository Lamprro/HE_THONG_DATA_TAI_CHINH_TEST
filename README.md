# HE_THONG_DATA_TAI_CHINH_TEST

MVP đầu tiên cho hệ thống phân tích dữ liệu tài chính AI: lấy dữ liệu chứng khoán Việt Nam bằng **VnStock v4** và expose qua **FastAPI**.

## Mục tiêu V0.1

- Kiểm chứng việc lấy dữ liệu thật từ VnStock.
- Có API JSON để Backend/Data pipeline dùng lại.
- Có dashboard rất nhỏ để nhập mã `FPT`, `VCB`, `HPG`... và xem response ngay trên browser.
- Có OpenAPI/Swagger tại `/docs`.
- Sẵn cấu hình deploy thử trên Vercel.

## API hiện có

- `GET /health`
- `GET /api/ohlcv?symbol=FPT&start=2026-08-01&end=2026-08-27`
- `GET /api/company/FPT`
- `GET /api/financial/FPT?statement=balance_sheet&period=year`
- `GET /api/financial/FPT?statement=income_statement&period=year`
- `GET /api/financial/FPT?statement=cash_flow&period=year`
- `GET /api/ratios/FPT?period=year`

## Chạy local

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Mở:

- Dashboard: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## Test trực tiếp VnStock

```bash
python scripts/vnstock_demo.py
```

## Kiến trúc MVP

```text
Browser / Client
      |
      v
   FastAPI
      |
      v
 VnStock v4 Unified UI
      |
      +-- Market      -> OHLCV
      +-- Reference   -> company info
      +-- Fundamental -> BCTC / ratios
      |
      v
Public data providers used by VnStock
```

## Lưu ý

VnStock là **công cụ trích xuất dữ liệu**, không phải nhà cung cấp dữ liệu. MVP này dùng cho nghiên cứu/kiểm thử pipeline. Trước khi dùng thương mại hoặc ra quyết định đầu tư thật, cần kiểm tra điều khoản sử dụng của VnStock và đối soát với nguồn dữ liệu chính thức/được cấp phép.

## Bước tiếp theo

1. Thêm PostgreSQL/TimescaleDB để lưu raw + normalized data.
2. Thêm scheduler/backfill cho khoảng 50 mã ban đầu.
3. Thêm provider adapter thứ hai (DNSE hoặc SSI) để realtime/fallback.
4. Thêm data quality, deduplication và ingestion logs.
5. Sau khi dữ liệu ổn định mới xây feature store và AI scoring.
