# Spring Boot API Integration Guide

> Tài liệu dành cho Java Spring Boot gọi Financial Data Python/FastAPI service.
>
> Cập nhật theo source code FastAPI `v0.4.0` trên nhánh `main`.

## 1. Base URL

Production hiện tại:

```text
https://he-thong-data-tai-chinh-test.vercel.app
```

Swagger UI chỉ dùng để xem/test API:

```text
https://he-thong-data-tai-chinh-test.vercel.app/docs
```

Spring Boot **không gọi `/docs`**. Spring Boot gọi trực tiếp các endpoint `/api/v1/...` được liệt kê trong tài liệu này.

Nên cấu hình base URL trong `application.properties`:

```properties
financial.python-service.base-url=https://he-thong-data-tai-chinh-test.vercel.app
```

Hoặc `application.yml`:

```yaml
financial:
  python-service:
    base-url: https://he-thong-data-tai-chinh-test.vercel.app
```

---

## 2. Kiểm tra deployment trước khi tích hợp

### 2.1 Health check

```http
GET /api/v1/health
```

Full URL:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/health
```

Response mong đợi với source hiện tại:

```json
{
  "status": "ok",
  "service": "financial-data-api-playground",
  "version": "0.4.0",
  "proxy_mode": "allowlisted-passthrough"
}
```

Nếu production chưa trả `version = 0.4.0`, có nghĩa deployment Vercel đang chạy code cũ hơn source GitHub hiện tại. Khi đó một số endpoint mới, đặc biệt `/api/v1/proxy/...`, có thể trả `404`.

### 2.2 Danh sách provider nghiệp vụ

```http
GET /api/v1/providers
```

Full URL:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/providers
```

Mục đích: kiểm tra các provider hiện được backend Python đăng ký như VnStock, vnstock_news, VNDirect, CafeF.

---

# 3. Hai loại API trong hệ thống

## 3.1 Normalized API

Các nhóm:

```text
/api/v1/vnstock/...
/api/v1/vndirect/...
/api/v1/cafef/...
/api/v1/vnstock-news/...
```

Python có thể đọc dữ liệu upstream, chuyển DataFrame, merge/parse/chuẩn hóa rồi trả về envelope chung.

Response thường có dạng:

```json
{
  "provider": "cafef",
  "dataset": "news",
  "symbol": "FPT",
  "retrieved_at": "...",
  "elapsed_ms": 123.45,
  "count": 10,
  "data": []
}
```

Đây là nhóm nên dùng khi Spring Boot muốn một API nghiệp vụ ổn định, dễ map DTO.

## 3.2 Raw passthrough proxy

Nhóm:

```text
/api/v1/proxy/...
```

Python đóng vai trò trung gian:

```text
Spring Boot
   -> Python FastAPI
   -> API bên thứ ba
   -> Python FastAPI
   -> Spring Boot
```

Proxy không bọc JSON vào `provider/dataset/count/data`. Response body, status code và content type của upstream được trả lại gần như nguyên bản.

Đây là nhóm dùng khi Spring Boot cần **response gốc của API bên thứ ba**.

---

# 4. Tổng hợp toàn bộ GET API

## 4.1 System

| Method | Path | Params | Mục đích |
|---|---|---|---|
| GET | `/api/v1/health` | Không | Health check và version |
| GET | `/api/v1/providers` | Không | Danh sách provider nghiệp vụ |

---

# 5. VnStock APIs

Prefix:

```text
/api/v1/vnstock
```

## 5.1 Historical OHLCV

```http
GET /api/v1/vnstock/equities/{symbol}/ohlcv
```

Path params:

- `symbol`: mã cổ phiếu, ví dụ `FPT`, `VCB`, `HPG`.

Query params:

- `start`: optional, format `YYYY-MM-DD`.
- `end`: optional, format `YYYY-MM-DD`.
- Nếu không truyền: mặc định khoảng 30 ngày gần nhất.
- Một request tối đa 10 năm.

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock/equities/FPT/ohlcv?start=2026-08-01&end=2026-08-31
```

## 5.2 Current/latest quote

```http
GET /api/v1/vnstock/equities/{symbol}/quote
```

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock/equities/FPT/quote
```

## 5.3 Company profile

```http
GET /api/v1/vnstock/companies/{symbol}
```

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock/companies/FPT
```

## 5.4 Financial statement

```http
GET /api/v1/vnstock/equities/{symbol}/financials/{statement}
```

Path params:

- `symbol`: ví dụ `FPT`.
- `statement` chỉ nhận một trong:
  - `balance_sheet`
  - `income_statement`
  - `cash_flow`

Query params:

- `period=year|quarter`
- mặc định `year`.

Ví dụ balance sheet theo năm:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock/equities/FPT/financials/balance_sheet?period=year
```

Ví dụ income statement theo quý:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock/equities/FPT/financials/income_statement?period=quarter
```

Ví dụ cash flow:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock/equities/FPT/financials/cash_flow?period=year
```

## 5.5 Financial ratio

```http
GET /api/v1/vnstock/equities/{symbol}/ratio
```

Query params:

- `period=year|quarter`
- mặc định `year`.

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock/equities/FPT/ratio?period=year
```

### Bảng nhanh VnStock

| Method | Path | Query |
|---|---|---|
| GET | `/api/v1/vnstock/equities/{symbol}/ohlcv` | `start`, `end` optional |
| GET | `/api/v1/vnstock/equities/{symbol}/quote` | - |
| GET | `/api/v1/vnstock/companies/{symbol}` | - |
| GET | `/api/v1/vnstock/equities/{symbol}/financials/{statement}` | `period=year|quarter` |
| GET | `/api/v1/vnstock/equities/{symbol}/ratio` | `period=year|quarter` |

---

# 6. VNDirect APIs

Prefix:

```text
/api/v1/vndirect
```

## 6.1 Historical OHLCV

```http
GET /api/v1/vndirect/equities/{symbol}/ohlcv
```

Query:

- `start`: optional `YYYY-MM-DD`.
- `end`: optional `YYYY-MM-DD`.
- mặc định 30 ngày gần nhất.
- tối đa 10 năm/request.

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vndirect/equities/FPT/ohlcv?start=2026-08-01&end=2026-08-31
```

## 6.2 Latest quote

```http
GET /api/v1/vndirect/equities/{symbol}/quote
```

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vndirect/equities/FPT/quote
```

## 6.3 Company information

```http
GET /api/v1/vndirect/equities/{symbol}/company
```

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vndirect/equities/FPT/company
```

## 6.4 Balance sheet

```http
GET /api/v1/vndirect/equities/{symbol}/financials/balance-sheet
```

Query:

- `fiscal_date`: optional, `YYYY-MM-DD`; bỏ trống để tự lấy kỳ gần nhất.
- `report_type`: optional, mặc định `QUARTER`.

Ví dụ kỳ gần nhất:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vndirect/equities/FPT/financials/balance-sheet
```

Ví dụ truyền ngày:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vndirect/equities/FPT/financials/balance-sheet?fiscal_date=2026-06-30&report_type=QUARTER
```

## 6.5 Income statement

```http
GET /api/v1/vndirect/equities/{symbol}/financials/income-statement
```

Query giống balance sheet:

- `fiscal_date`: optional.
- `report_type`: default `QUARTER`.

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vndirect/equities/FPT/financials/income-statement
```

## 6.6 Cash flow

```http
GET /api/v1/vndirect/equities/{symbol}/financials/cash-flow
```

Query:

- `fiscal_date`: optional.
- `report_type`: default `QUARTER`.

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vndirect/equities/FPT/financials/cash-flow
```

## 6.7 Latest financial ratios

```http
GET /api/v1/vndirect/equities/{symbol}/ratios
```

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vndirect/equities/FPT/ratios
```

### Bảng nhanh VNDirect

| Method | Path | Query |
|---|---|---|
| GET | `/api/v1/vndirect/equities/{symbol}/ohlcv` | `start`, `end` optional |
| GET | `/api/v1/vndirect/equities/{symbol}/quote` | - |
| GET | `/api/v1/vndirect/equities/{symbol}/company` | - |
| GET | `/api/v1/vndirect/equities/{symbol}/financials/balance-sheet` | `fiscal_date`, `report_type` optional |
| GET | `/api/v1/vndirect/equities/{symbol}/financials/income-statement` | `fiscal_date`, `report_type` optional |
| GET | `/api/v1/vndirect/equities/{symbol}/financials/cash-flow` | `fiscal_date`, `report_type` optional |
| GET | `/api/v1/vndirect/equities/{symbol}/ratios` | - |

---

# 7. CafeF APIs

Prefix:

```text
/api/v1/cafef
```

## 7.1 Historical OHLCV

```http
GET /api/v1/cafef/equities/{symbol}/ohlcv
```

Query:

- `start`: optional `YYYY-MM-DD`.
- `end`: optional `YYYY-MM-DD`.
- mặc định 30 ngày gần nhất.
- tối đa 10 năm/request.

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/cafef/equities/FPT/ohlcv?start=2026-08-01&end=2026-08-31
```

## 7.2 Latest quote

```http
GET /api/v1/cafef/equities/{symbol}/quote
```

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/cafef/equities/FPT/quote
```

## 7.3 Balance sheet

```http
GET /api/v1/cafef/equities/{symbol}/financials/balance-sheet
```

Query:

- `year`: optional, ví dụ `2026`.
- `period`: integer, mặc định `1`.
  - `0` = yearly.
  - `1` = quarterly.
  - `2` = cumulative 6 months.

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/cafef/equities/FPT/financials/balance-sheet?year=2026&period=1
```

## 7.4 Income statement

```http
GET /api/v1/cafef/equities/{symbol}/financials/income-statement
```

Query giống balance sheet:

- `year`: optional.
- `period=0|1|2`, mặc định `1`.

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/cafef/equities/FPT/financials/income-statement?year=2026&period=1
```

## 7.5 Cash flow

```http
GET /api/v1/cafef/equities/{symbol}/financials/cash-flow
```

Query:

- `year`: optional.
- `period=0|1|2`, mặc định `1`.

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/cafef/equities/FPT/financials/cash-flow?year=2026&period=1
```

## 7.6 Company information

```http
GET /api/v1/cafef/equities/{symbol}/company
```

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/cafef/equities/FPT/company
```

## 7.7 Management / leadership

```http
GET /api/v1/cafef/equities/{symbol}/management
```

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/cafef/equities/FPT/management
```

## 7.8 Subsidiaries and associates

```http
GET /api/v1/cafef/equities/{symbol}/subsidiaries
```

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/cafef/equities/FPT/subsidiaries
```

## 7.9 Company news

```http
GET /api/v1/cafef/equities/{symbol}/news
```

Query:

- `limit`: integer, từ `1` đến `1000`.
- mặc định `100`.

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/cafef/equities/FPT/news?limit=20
```

Đây chính là API thật tương ứng với phần `cafef-news` trên Swagger. Spring Boot gọi URL `/api/v1/cafef/...`, **không gọi URL có `/docs#/cafef-news/...`**.

## 7.10 Company events

```http
GET /api/v1/cafef/equities/{symbol}/events
```

Query:

- `limit`: `1..1000`.
- mặc định `100`.

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/cafef/equities/FPT/events?limit=20
```

### Bảng nhanh CafeF

| Method | Path | Query |
|---|---|---|
| GET | `/api/v1/cafef/equities/{symbol}/ohlcv` | `start`, `end` optional |
| GET | `/api/v1/cafef/equities/{symbol}/quote` | - |
| GET | `/api/v1/cafef/equities/{symbol}/financials/balance-sheet` | `year`, `period=0|1|2` |
| GET | `/api/v1/cafef/equities/{symbol}/financials/income-statement` | `year`, `period=0|1|2` |
| GET | `/api/v1/cafef/equities/{symbol}/financials/cash-flow` | `year`, `period=0|1|2` |
| GET | `/api/v1/cafef/equities/{symbol}/company` | - |
| GET | `/api/v1/cafef/equities/{symbol}/management` | - |
| GET | `/api/v1/cafef/equities/{symbol}/subsidiaries` | - |
| GET | `/api/v1/cafef/equities/{symbol}/news` | `limit=1..1000`, default 100 |
| GET | `/api/v1/cafef/equities/{symbol}/events` | `limit=1..1000`, default 100 |

---

# 8. VnStock News APIs

Prefix:

```text
/api/v1/vnstock-news
```

Có hai loại nguồn news:

1. `vnstock_news` crawler: sponsor/private package, runtime phải có package hợp lệ.
2. VnStock community company news: dùng được độc lập với crawler sponsor nếu upstream community hoạt động.

## 8.1 Check vnstock_news package status

```http
GET /api/v1/vnstock-news/status
```

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock-news/status
```

Nên gọi endpoint này trước khi dùng `/sites`, `/latest`, `/history`.

## 8.2 Supported crawler sites

```http
GET /api/v1/vnstock-news/sites
```

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock-news/sites
```

Nếu sponsor/private package chưa được cài, endpoint có thể trả `503`.

## 8.3 Latest RSS news

```http
GET /api/v1/vnstock-news/latest
```

Query:

- `site`: mặc định `cafef`; ví dụ `cafef`, `vnexpress`, `vietstock`.
- `limit`: `1..30`, mặc định `10`.

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock-news/latest?site=cafef&limit=10
```

Yêu cầu sponsor/private `vnstock_news` package.

## 8.4 Historical detailed articles

```http
GET /api/v1/vnstock-news/history
```

Query:

- `site`: mặc định `cafef`.
- `limit`: `1..10`, mặc định `5`.
- `request_delay`: `0.2..3.0`, mặc định `0.5` giây.

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock-news/history?site=cafef&limit=5&request_delay=0.5
```

Yêu cầu sponsor/private `vnstock_news` package.

## 8.5 Company-tagged community news

```http
GET /api/v1/vnstock-news/company/{symbol}
```

Query:

- `limit`: `1..50`, mặc định `10`.

Ví dụ:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock-news/company/FPT?limit=10
```

Endpoint này dùng VnStock community company news, không phải multi-publication crawler sponsor.

### Bảng nhanh News

| Method | Path | Query | Ghi chú |
|---|---|---|---|
| GET | `/api/v1/vnstock-news/status` | - | Kiểm tra package |
| GET | `/api/v1/vnstock-news/sites` | - | Sponsor/private |
| GET | `/api/v1/vnstock-news/latest` | `site`, `limit` | Sponsor/private |
| GET | `/api/v1/vnstock-news/history` | `site`, `limit`, `request_delay` | Sponsor/private |
| GET | `/api/v1/vnstock-news/company/{symbol}` | `limit` | VnStock community |

---

# 9. Third-party raw proxy APIs

Prefix:

```text
/api/v1/proxy
```

## 9.1 List allowlisted proxy providers

```http
GET /api/v1/proxy/providers
```

Full URL:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/proxy/providers
```

Provider mặc định trong source hiện tại:

| provider | Upstream base URL |
|---|---|
| `vndirect` | `https://api-finfo.vndirect.com.vn/v4` |
| `cafef` | `https://cafef.vn` |
| `cafef-financial` | `https://s.cafef.vn` |

## 9.2 Generic raw GET proxy

```http
GET /api/v1/proxy/{provider}/{upstream_path}
```

Tất cả query string sau endpoint proxy được chuyển tiếp sang upstream.

Ví dụ VNDirect raw stock prices:

```text
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/proxy/vndirect/stock_prices?q=code:FPT&size=10&page=1
```

FastAPI gọi tương ứng:

```text
https://api-finfo.vndirect.com.vn/v4/stock_prices?q=code:FPT&size=10&page=1
```

Response của VNDirect được trả trực tiếp về Spring Boot, không đổi thành normalized envelope.

### Lưu ý proxy

- Provider phải có trong allowlist.
- Proxy có timeout upstream 30 giây.
- Nếu không kết nối được upstream: Python trả `502`.
- Nếu upstream timeout: Python trả `504`.
- Nếu upstream tự trả `400`, `404`, `500`,... thì status/body upstream được passthrough về caller.
- `Authorization`, `Cookie`, `Host` và các hop-by-hop header nhạy cảm không được forward.
- Source hiện cũng hỗ trợ `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, tuy nhiên tài liệu này tập trung vào các GET endpoint cho Spring Boot.

---

# 10. Spring Boot RestClient - cấu hình khuyến nghị

## 10.1 Bean config

```java
@Configuration
public class FinancialPythonClientConfig {

    @Bean
    public RestClient financialPythonRestClient(
            RestClient.Builder builder,
            @Value("${financial.python-service.base-url}") String baseUrl
    ) {
        return builder
                .baseUrl(baseUrl)
                .build();
    }
}
```

## 10.2 Gọi normalized API bằng JsonNode

`JsonNode` thuận tiện trong giai đoạn đầu vì schema `data` giữa các provider khác nhau.

```java
@Service
public class PythonFinancialService {

    private final RestClient restClient;

    public PythonFinancialService(RestClient financialPythonRestClient) {
        this.restClient = financialPythonRestClient;
    }

    public JsonNode getCafeFNews(String symbol, int limit) {
        return restClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/api/v1/cafef/equities/{symbol}/news")
                        .queryParam("limit", limit)
                        .build(symbol))
                .retrieve()
                .body(JsonNode.class);
    }

    public JsonNode getVnStockBalanceSheet(String symbol, String period) {
        return restClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/api/v1/vnstock/equities/{symbol}/financials/balance_sheet")
                        .queryParam("period", period)
                        .build(symbol))
                .retrieve()
                .body(JsonNode.class);
    }

    public JsonNode getVnDirectRatios(String symbol) {
        return restClient.get()
                .uri("/api/v1/vndirect/equities/{symbol}/ratios", symbol)
                .retrieve()
                .body(JsonNode.class);
    }
}
```

Import:

```java
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
```

## 10.3 Gọi raw proxy và giữ nguyên body

Nếu mục đích là nhận JSON/text upstream gần như nguyên bản, có thể nhận `String`:

```java
public String getRawVnDirectStockPrice(String symbol) {
    return restClient.get()
            .uri(uriBuilder -> uriBuilder
                    .path("/api/v1/proxy/vndirect/stock_prices")
                    .queryParam("q", "code:" + symbol)
                    .queryParam("size", 10)
                    .queryParam("page", 1)
                    .build())
            .retrieve()
            .body(String.class);
}
```

Nếu Spring Boot phải trả nguyên cả status/header/body từ Python cho caller, nên dùng `exchange(...)` thay vì chỉ `.retrieve().body(String.class)` để chủ động map status và headers.

---

# 11. Ví dụ Controller Spring Boot

```java
@RestController
@RequestMapping("/api/financial-data")
public class FinancialDataController {

    private final PythonFinancialService pythonFinancialService;

    public FinancialDataController(PythonFinancialService pythonFinancialService) {
        this.pythonFinancialService = pythonFinancialService;
    }

    @GetMapping("/cafef/{symbol}/news")
    public ResponseEntity<JsonNode> getCafeFNews(
            @PathVariable String symbol,
            @RequestParam(defaultValue = "20") int limit
    ) {
        return ResponseEntity.ok(
                pythonFinancialService.getCafeFNews(symbol, limit)
        );
    }

    @GetMapping("/vndirect/{symbol}/raw-price")
    public ResponseEntity<String> getRawPrice(
            @PathVariable String symbol
    ) {
        return ResponseEntity.ok(
                pythonFinancialService.getRawVnDirectStockPrice(symbol)
        );
    }
}
```

Flow:

```text
Frontend/Postman
      |
      v
Spring Boot
      |
      | HTTPS
      v
https://he-thong-data-tai-chinh-test.vercel.app
      |
      v
Python FastAPI
      |
      +----> VnStock
      +----> VNDirect
      +----> CafeF
      +----> vnstock_news
```

---

# 12. Error handling cho Spring Boot

Các status cần xử lý:

| HTTP status | Ý nghĩa thường gặp |
|---|---|
| `200` | Thành công |
| `400` | Param không hợp lệ, ví dụ symbol/date/path |
| `404` | Route/provider không tồn tại hoặc deployment chưa có endpoint mới |
| `422` | FastAPI validation lỗi: query/path param sai kiểu hoặc ngoài range |
| `502` | Python không lấy được dữ liệu từ upstream/provider |
| `503` | Ví dụ `vnstock_news` sponsor/private package chưa cài trong runtime |
| `504` | Proxy gọi upstream bị timeout |

Không nên coi mọi `5xx` là lỗi Spring Boot. Với hệ thống này, `502/503/504` thường thể hiện lỗi hoặc trạng thái của Python/upstream data provider.

---

# 13. Endpoint Spring Boot nên ưu tiên theo nhu cầu

## Giá lịch sử

Ưu tiên một trong:

```text
GET /api/v1/vnstock/equities/{symbol}/ohlcv
GET /api/v1/vndirect/equities/{symbol}/ohlcv
GET /api/v1/cafef/equities/{symbol}/ohlcv
```

Có nhiều nguồn để sau này đối soát dữ liệu.

## Giá/quote gần nhất

```text
GET /api/v1/vnstock/equities/{symbol}/quote
GET /api/v1/vndirect/equities/{symbol}/quote
GET /api/v1/cafef/equities/{symbol}/quote
```

## Hồ sơ doanh nghiệp

```text
GET /api/v1/vnstock/companies/{symbol}
GET /api/v1/vndirect/equities/{symbol}/company
GET /api/v1/cafef/equities/{symbol}/company
```

## Báo cáo tài chính

VnStock:

```text
GET /api/v1/vnstock/equities/{symbol}/financials/balance_sheet
GET /api/v1/vnstock/equities/{symbol}/financials/income_statement
GET /api/v1/vnstock/equities/{symbol}/financials/cash_flow
```

VNDirect:

```text
GET /api/v1/vndirect/equities/{symbol}/financials/balance-sheet
GET /api/v1/vndirect/equities/{symbol}/financials/income-statement
GET /api/v1/vndirect/equities/{symbol}/financials/cash-flow
```

CafeF:

```text
GET /api/v1/cafef/equities/{symbol}/financials/balance-sheet
GET /api/v1/cafef/equities/{symbol}/financials/income-statement
GET /api/v1/cafef/equities/{symbol}/financials/cash-flow
```

## Ratio

```text
GET /api/v1/vnstock/equities/{symbol}/ratio
GET /api/v1/vndirect/equities/{symbol}/ratios
```

## Tin tức

```text
GET /api/v1/cafef/equities/{symbol}/news
GET /api/v1/vndirect/...             # hiện chưa có normalized VNDirect news route
GET /api/v1/vnstock-news/company/{symbol}
GET /api/v1/vnstock-news/latest      # yêu cầu sponsor/private package
GET /api/v1/vnstock-news/history     # yêu cầu sponsor/private package
```

## Sự kiện doanh nghiệp

```text
GET /api/v1/cafef/equities/{symbol}/events
```

## Ban lãnh đạo / công ty con

```text
GET /api/v1/cafef/equities/{symbol}/management
GET /api/v1/cafef/equities/{symbol}/subsidiaries
```

---

# 14. Checklist tích hợp Spring Boot

1. Gọi `GET /api/v1/health`.
2. Xác nhận production đang chạy version source mong muốn.
3. Lưu base URL trong configuration, không hard-code ở nhiều service.
4. Dùng normalized API khi cần schema nghiệp vụ ổn định.
5. Dùng `/api/v1/proxy/...` khi cần raw upstream response.
6. Giai đoạn đầu có thể parse response normalized bằng `JsonNode`.
7. Khi schema ổn định, tạo DTO Java tương ứng.
8. Xử lý riêng `502`, `503`, `504` để phân biệt upstream failure.
9. Không gọi Swagger `/docs#/...` từ Java.
10. Không gọi `http://python-service:8000` khi Python đang chạy public trên Vercel; URL đó chỉ có ý nghĩa trong Docker network có service tên `python-service`.

---

# 15. Quick copy/paste URLs với FPT

```text
# System
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/health
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/providers

# VnStock
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock/equities/FPT/quote
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock/companies/FPT
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock/equities/FPT/financials/balance_sheet?period=year
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock/equities/FPT/financials/income_statement?period=year
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock/equities/FPT/financials/cash_flow?period=year
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock/equities/FPT/ratio?period=year

# VNDirect
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vndirect/equities/FPT/quote
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vndirect/equities/FPT/company
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vndirect/equities/FPT/financials/balance-sheet
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vndirect/equities/FPT/financials/income-statement
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vndirect/equities/FPT/financials/cash-flow
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vndirect/equities/FPT/ratios

# CafeF
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/cafef/equities/FPT/quote
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/cafef/equities/FPT/company
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/cafef/equities/FPT/management
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/cafef/equities/FPT/subsidiaries
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/cafef/equities/FPT/news?limit=20
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/cafef/equities/FPT/events?limit=20

# News
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock-news/status
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/vnstock-news/company/FPT?limit=10

# Raw proxy
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/proxy/providers
https://he-thong-data-tai-chinh-test.vercel.app/api/v1/proxy/vndirect/stock_prices?q=code:FPT&size=10&page=1
```

---

## Source of truth

Nếu tài liệu này và Swagger khác nhau, kiểm tra theo thứ tự:

1. `app/main.py` để biết router prefix.
2. `app/api/v1/*.py` để biết path/query params thực tế.
3. `/openapi.json` hoặc `/docs` của deployment đang chạy để biết deployment production hiện tại đã nhận version code nào.

Tài liệu này mô tả source FastAPI `v0.4.0` hiện tại trong repository.