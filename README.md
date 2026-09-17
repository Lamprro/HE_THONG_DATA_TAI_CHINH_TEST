# HE_THONG_DATA_TAI_CHINH_TEST

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

### Contract giá thống nhất cho Spring Boot

Các endpoint market normalized của VnStock và CafeF dùng chung schema
`market_price.v1`:

- `GET /api/v1/vnstock/equities/{symbol}/ohlcv`
- `GET /api/v1/vnstock/equities/{symbol}/quote`
- `GET /api/v1/cafef/equities/{symbol}/ohlcv`
- `GET /api/v1/cafef/equities/{symbol}/quote`

Quy ước:

- mọi giá (`open_price`, `high_price`, `low_price`, `close_price`, ...) là VND;
- `trading_value` là VND;
- `volume` là số cổ phiếu khớp lệnh;
- candle ngày dùng `interval_code = 1d`;
- `trading_date` là ngày giao dịch, không phải ngày Python gọi upstream;
- `price_timestamp` là đầu ngày giao dịch theo UTC+07:00 để tạo khóa ngày ổn định;
- record nguyên bản của provider được giữ tại `source_record` để audit.

Ví dụ rút gọn:

```json
{
  "provider": "cafef",
  "dataset": "equity_quote",
  "schema_version": "market_price.v1",
  "normalization": {
    "currency": "VND",
    "price_unit": "VND",
    "trading_value_unit": "VND",
    "volume_unit": "shares",
    "trading_timezone": "Asia/Ho_Chi_Minh",
    "interval_code": "1d"
  },
  "data": [
    {
      "symbol": "FPT",
      "trading_date": "2026-08-28",
      "price_timestamp": "2026-08-28T00:00:00+07:00",
      "interval_code": "1d",
      "open_price": 72200,
      "high_price": 74000,
      "low_price": 72200,
      "close_price": 73200,
      "volume": 10196800,
      "trading_value": 749760000000,
      "source_record": {}
    }
  ]
}
```

## Local backend

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Swagger backend: `http://127.0.0.1:8000/docs`

Danh sách proxy providers: `http://127.0.0.1:8000/api/v1/proxy/providers`

## Frontend

Mở `frontend/index.html`, nhập Backend URL rồi bấm `Kết nối`. Frontend tải `/openapi.json` từ backend và tạo Swagger UI, vì vậy khi thêm provider/API mới ở backend, giao diện tự xuất hiện mà không cần hard-code endpoint mới.

## Security note

Không triển khai endpoint kiểu `/proxy?url=https://bat-ky-domain-nao...` vì cách đó biến backend thành open proxy và tạo rủi ro SSRF. Phiên bản hiện tại chỉ proxy tới provider nằm trong allowlist/registry.
