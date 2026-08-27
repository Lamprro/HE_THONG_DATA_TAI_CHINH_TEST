# HE_THONG_DATA_TAI_CHINH_TEST

Financial Data API Playground cho dự án phân tích dữ liệu tài chính AI.

## Kiến trúc

- `app/`: FastAPI backend, provider-oriented.
- `frontend/`: Swagger UI frontend độc lập. Có thể nhập URL backend để test như Postman.
- `Dockerfile`: deploy backend lên Render/Railway/Koyeb/Fly.io hoặc nền tảng hỗ trợ Docker.
- `render.yaml`: Render Blueprint.
- `railway.json`: Railway config.
- `.github/workflows/deploy-frontend-pages.yml`: tự deploy frontend lên GitHub Pages.

## Backend API

- `GET /api/v1/health`
- `GET /api/v1/providers`
- `GET /api/v1/vnstock/equities/{symbol}/ohlcv`
- `GET /api/v1/vnstock/equities/{symbol}/quote`
- `GET /api/v1/vnstock/companies/{symbol}`
- `GET /api/v1/vnstock/equities/{symbol}/financials/{statement}`
- `GET /api/v1/vnstock/equities/{symbol}/ratio`

## Local backend

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Swagger backend: `http://127.0.0.1:8000/docs`

## Frontend

Mở `frontend/index.html`, nhập Backend URL rồi bấm `Kết nối`. Frontend tải `/openapi.json` từ backend và tạo Swagger UI, vì vậy khi thêm provider/API mới ở backend, giao diện tự xuất hiện mà không cần hard-code endpoint mới.

## Provider architecture

Mỗi nguồn dữ liệu thêm adapter/router riêng. V0.2 có VnStock. Kế hoạch tiếp theo: DNSE, SSI, World Bank, FRED.
