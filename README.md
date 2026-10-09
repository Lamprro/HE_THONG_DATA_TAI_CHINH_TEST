# HE_THONG_DATA_TAI_CHINH_TEST

## Vietnam macro API (v0.6.0)

- `GET /api/v1/macro/worldbank/series?country=VNM`
- `GET /api/v1/macro/worldbank/observations?country=VNM&start=2016-01-01&end=2026-10-09`
- `GET /api/v1/macro/bis/series?country=VNM`
- `GET /api/v1/macro/bis/observations?country=VNM&start=2016-01-01&end=2026-10-09`

Only Vietnam is accepted. World Bank WDI supplies ten native annual series:
GDP current USD, real GDP growth, CPI index/inflation, annual official USD/VND,
lending/deposit rates, modeled ILO unemployment, and exports/imports of goods
and services. BIS supplies its native quarterly average VND per USD series.
Annual values are never divided, repeated or interpolated into quarterly values.
Refresh scheduling and durable storage belong to Java; Python is stateless and
makes a bounded official-source request per call, suitable for the existing
60-second Vercel function.

Contract `macro_observations.v1`: `count` counts series, `observation_count`
counts numeric observations. Each series contains its source indicator,
country, frequency, unit, observations and source records. Null upstream values
are recorded as missing periods and never filled. `observation_date` is the
period end; `retrieved_at` is collection time, not the historical publication date.
World Bank/BIS revision vintages and point-in-time backtest availability are not verified.

Checked 09/10/2026 through the actual FastAPI app: World Bank returned 95
observations from 2016 onward, BIS returned 42 quarters through 2026-Q2.
World Bank rates currently end in 2023; annual FX ends in 2024; most other series
end in 2025. These are dated coverage observations, not promises of future availability.
Ten unittest cases passed (six new macro cases and four NEWS regressions;
provider transport in unit tests is mocked). Run `python -m unittest discover -s tests -v`.
Production acceptance must also check the deployed API and the Java ingestion flow.

Official contracts: [World Bank Indicators API](https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures)
and [BIS exchange-rate series](https://data.bis.org/topics/XRU/BIS,WS_XRU,1.0/Q.VN.VND.A).

Financial Data API Playground cho dự án phân tích dữ liệu tài chính AI.

## Mục tiêu kiến trúc

Python service có 2 vai trò song song:

1. **Normalized provider APIs**: các API hiện có có thể xử lý/chuẩn hóa dữ liệu thành format riêng của hệ thống.
2. **Third-party passthrough proxy**: hệ thống khác gọi Python -> Python gọi API bên thứ ba -> Python trả response upstream về gần như nguyên bản, không bọc thêm `provider`, `dataset`, `count`, `data` và không đổi cấu trúc JSON/body.

Luồng passthrough:

```text
Spring Boot / Frontend / Service khác
            |
            v
GET /api/v1/proxy/{provider}/{upstream_path}
            |
            v
      FastAPI Python
            |
            v
     Third-party API
            |
            v
status + body + content-type
            |
            v
      Caller ban đầu
```

## Kiến trúc thư mục

- `app/`: FastAPI backend, provider-oriented.
- `app/api/v1/proxy.py`: HTTP passthrough API cho các third-party provider đã whitelist.
- `app/core/proxy.py`: registry/base URL và validation cho proxy provider.
- `app/providers/`: adapter xử lý/chuẩn hóa dữ liệu cho các API nghiệp vụ hiện có.
- `frontend/`: Swagger UI frontend độc lập. Có thể nhập URL backend để test như Postman.
- `Dockerfile`: deploy backend lên Render/Railway/Koyeb/Fly.io hoặc nền tảng hỗ trợ Docker.
- `render.yaml`: Render Blueprint.
- `railway.json`: Railway config.
- `.github/workflows/deploy-frontend-pages.yml`: tự deploy frontend lên GitHub Pages.

## Backend API

### System

- `GET /api/v1/health`
- `GET /api/v1/providers`

### Third-party passthrough proxy

- `GET /api/v1/proxy/providers`
- `GET|POST|PUT|PATCH|DELETE|HEAD /api/v1/proxy/{provider}/{upstream_path}`

Provider mặc định:

- `vndirect` -> `https://api-finfo.vndirect.com.vn/v4`
- `cafef` -> `https://cafef.vn`
- `cafef-financial` -> `https://s.cafef.vn`

Ví dụ gọi VNDirect qua Python proxy:

```bash
curl --get "http://127.0.0.1:8000/api/v1/proxy/vndirect/stock_prices" \
  --data-urlencode "q=code:FPT~date:gte:2026-08-01~date:lte:2026-08-31" \
  --data-urlencode "sort=date" \
  --data-urlencode "size=10" \
  --data-urlencode "page=1"
```

Python sẽ gọi tương ứng:

```text
https://api-finfo.vndirect.com.vn/v4/stock_prices?q=...&sort=date&size=10&page=1
```

Response body của VNDirect được trả thẳng về caller, không đổi thành format kiểu:

```json
{
  "provider": "vndirect",
  "dataset": "...",
  "count": 10,
  "data": []
}
```

Ví dụ CafeF:

```bash
curl --get "http://127.0.0.1:8000/api/v1/proxy/cafef/du-lieu/ajax/pagenew/datahistory/pricehistory.ashx" \
  --data-urlencode "Symbol=FPT" \
  --data-urlencode "StartDate=08/01/2026" \
  --data-urlencode "EndDate=08/31/2026" \
  --data-urlencode "PageIndex=1" \
  --data-urlencode "PageSize=20"
```

### Thêm third-party provider mà không sửa router

Thiết lập biến môi trường `PROXY_PROVIDER_BASE_URLS_JSON` bằng JSON object `provider_code -> HTTPS base URL`.

Ví dụ:

```bash
PROXY_PROVIDER_BASE_URLS_JSON='{"worldbank":"https://api.worldbank.org/v2","my-provider":"https://api.example.com/v1"}'
```

Sau đó có thể gọi:

```text
/api/v1/proxy/worldbank/...
/api/v1/proxy/my-provider/...
```

Chỉ HTTPS absolute URL được chấp nhận. Credentials không được nhúng trực tiếp trong base URL.

### Quy tắc passthrough

Proxy giữ:

- upstream HTTP status code;
- response body dạng raw bytes;
- `Content-Type` và các response header thông thường;
- query string;
- request body;
- HTTP method `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`.

Proxy chủ động bỏ các hop-by-hop/sensitive header như `Host`, `Connection`, `Transfer-Encoding`, `Cookie`, `Authorization`, `Set-Cookie`. Vì vậy API key/private credential của provider không bị vô tình chuyển tiếp từ credential đăng nhập của caller. Nếu sau này cần provider có API key, nên cấu hình credential server-side theo từng provider thay vì dùng chung Authorization của client.

Nếu không kết nối được upstream, proxy trả `502`. Nếu upstream timeout, proxy trả `504`. Đây là lỗi do lớp proxy sinh ra; còn khi upstream thực sự trả 4xx/5xx thì status/body upstream được passthrough về caller.

### Existing normalized APIs

Các endpoint cũ vẫn giữ nguyên để không phá code hiện tại, ví dụ:

- `GET /api/v1/vnstock/equities/{symbol}/ohlcv`
- `GET /api/v1/vnstock/equities/{symbol}/quote`
- `GET /api/v1/vnstock/companies/{symbol}`
- `GET /api/v1/vnstock/equities/{symbol}/financials/{statement}`
- `GET /api/v1/vnstock/equities/{symbol}/ratio`
- các route `vndirect`, `cafef`, `vnstock-news` hiện có.

Nhóm API này có thể chuẩn hóa/merge/transform data. Nếu caller cần **response y nguyên của API thứ ba**, dùng `/api/v1/proxy/...`.

## Local backend

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

VnStock-based market and company endpoints are optional. Install
`requirements-vnstock.txt` in environments where the package is available;
CafeF, VNDirect, and the stateless NEWS URL fetch API do not require it.

Swagger backend: `http://127.0.0.1:8000/docs`

Danh sách proxy providers: `http://127.0.0.1:8000/api/v1/proxy/providers`

## Frontend

Mở `frontend/index.html`, nhập Backend URL rồi bấm `Kết nối`. Frontend tải `/openapi.json` từ backend và tạo Swagger UI, vì vậy khi thêm provider/API mới ở backend, giao diện tự xuất hiện mà không cần hard-code endpoint mới.

## Security note

Không triển khai endpoint kiểu `/proxy?url=https://bat-ky-domain-nao...` vì cách đó biến backend thành open proxy và tạo rủi ro SSRF. Phiên bản hiện tại chỉ proxy tới provider nằm trong allowlist/registry.
