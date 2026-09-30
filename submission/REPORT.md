# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Hữu Chương
- **MSSV:** 2A202602601
- **Lớp:** K4-L3B
- **Repository URL:** `https://github.com/hchuong04/K4-L3B-Day13-NguyenHuuChuong-2A202602601-Monitoring-LLMOps`
- **Commit SHA cuối:** `20731681b90c983c0be87e9cb6f3c92b6eab57ed`
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602601`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11a-dashboard-overview-latence-request.png`, `evidence/11b-dashboard-error-cost-token-quality.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | **100/100** | Đầy đủ required fields (`ts`, `level`, `service`, `event`, `correlation_id`), context enrichment 4 fields, 16 unique correlation IDs, 0 PII leak |
| `validate_dashboard.py` | 6/6 panel hợp lệ | **6/6 panel hợp lệ** | Cấu trúc dashboard YAML tuân thủ đúng schema_version 1, đầy đủ 6 panel với threshold và aggregations chuẩn |
| `pytest` | 22/22 passed | **26/26 passed** | Toàn bộ 26 tests (PII, logging, metrics, challenge, tracing adapter, prompt management) đều passed 100% |
| Số traces hợp lệ | 0 | **>= 15 traces** | Traces được ghi nhận đầy đủ lên project cá nhân Langfuse `day13-k4-l3b-2A202602601` |
| Số PII leak | 0 | **0** | Regex scrubbing loại bỏ hoàn toàn Email, Phone VN, CCCD, Thẻ tín dụng, Passport |
| Latency P95 / TTFT P95 | N/A | **154.0ms / 50.0ms** | Baseline P50 153ms, P95 ổn định ~154-165ms; TTFT P95 đạt chuẩn 50ms |
| Retrieval success rate | N/A | **100%** | Toàn bộ truy vấn RAG đều match tài liệu từ CORPUS hoặc trả về fallback đúng hợp đồng |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:**
  - `CorrelationIdMiddleware` chặn mọi HTTP request đến FastAPI. Nếu client gửi header `X-Correlation-ID`, middleware sẽ nhận giá trị đó; nếu không có, middleware tự sinh chuỗi ID dạng `req-<hex8>` (dùng `uuid.uuid4().hex[:8]`).
  - Gắn correlation ID vào `request.state.correlation_id` và trả ngược về cho client qua response header `X-Correlation-ID`.
  - Sử dụng `structlog.contextvars.bind_contextvars()` để tự động tiêm `correlation_id` vào mọi log record trong suốt vòng đời của request.
  - Truyền `correlation_id` vào metadata của Trace trong Langfuse để liên kết log với trace.
- **Các metadata được ghi vào structured log:**
  - Trường bắt buộc: `ts` (ISO 8601 UTC), `level`, `service`, `event`, `correlation_id`.
  - Context enrichment: `user_id_hash` (SHA256 12 ký tự hex), `session_id`, `feature`, `model`, `env`.
  - Business & performance metrics (trong event `response_sent`): `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`, và `payload` đã được redact.
- **Cách bảo đảm PII được scrub trước khi ghi:**
  - Xây dựng module `app/pii.py` với từ điển `PII_PATTERNS` bao gồm 5 biểu thức chính quy (Regex): Email, Phone VN (đầu 0 hoặc +84), CCCD (12 chữ số), Credit Card (16 chữ số chia 4 nhóm), Passport (1 chữ cái hoa + 7 số).
  - Hàm `scrub_text()` duyệt và thay thế các chuỗi nhạy cảm bằng token `[REDACTED_<TYPE>]`.
  - Tích hợp processor `scrub_event` trực tiếp vào pipeline xử lý của `structlog.configure()`, đảm bảo mọi text trong `payload` hoặc `event` đều được duyệt và làm sạch trước khi đi qua `JsonlFileProcessor` và ghi xuống file `data/logs.jsonl`.
- **Cách kiểm chứng kết quả:**
  - Chạy `python scripts/validate_logs.py` kiểm tra độc lập và đạt điểm tuyệt đối 100/100, xác nhận 0 PII leak.
  - Chạy bộ unit tests `pytest tests/test_pii.py` kiểm tra mọi trường hợp biên của việc scrub dữ liệu.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
  - Cấu hình biến môi trường `LANGFUSE_PUBLIC_KEY` và `LANGFUSE_SECRET_KEY` thuộc project riêng `day13-k4-l3b-2A202602601`.
  - Mọi trace đều được gắn tags định danh gồm `["lab", feature, model]`, environment `dev`, và `user_id_hash` đại diện cho học viên Nguyễn Hữu Chương.
- **Cấu trúc root/retrieval/generation observations:**
  - Root observation: `@observe(name="lab-agent-run", as_type="agent")` bao quát toàn bộ hàm `LabAgent.run()`.
  - Child observation 1: `@observe(name="retrieval", as_type="retriever")` đo lường thời gian thực thi của hàm `retrieve(message)` và gắn metadata số lượng tài liệu tìm thấy (`doc_count`).
  - Child observation 2: `@observe(name="generation", as_type="generation")` bao bọc lệnh gọi `FakeLLM.generate()`, nhận managed prompt từ Langfuse, cập nhật usage (`input_tokens`, `output_tokens`) và cost chi tiết (`cost_usd`).
- **Cách nối trace với log:**
  - Sử dụng chung một `correlation_id` duy nhất cho mỗi HTTP request.
  - Correlation ID được ghi vào trường `correlation_id` trong log JSONL của API (`response_sent`) đồng thời được truyền vào `propagate_attributes(metadata={"correlation_id": correlation_id})` của Langfuse trace.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** `v1` (version 1) được gán label `production`.
- **Version/label candidate:** `v2` (version 2) được tinh chỉnh instruction và gán label `staging` hoặc promote thành `production`.
- **Trace ID của mỗi version:**
  - Trace chạy prompt v1: Xem trong danh sách trace ứng với label `production` trước khi đổi label (ví dụ trace của `req-7a89c25d`).
  - Trace chạy prompt v2: Xem trong danh sách trace sau khi promote v2 (hoặc gán candidate).
- **Cách promote và rollback `production`:**
  - **Promote**: Trên giao diện Langfuse (Prompts > `day13-chat`), chuyển label `production` trỏ sang Version 2 (`v2`). Hệ thống tự động fetch bản mới sau khi TTL 60s hết hạn mà không cần restart server hay deploy code.
  - **Rollback**: Khi phát hiện v2 gây suy giảm chất lượng hoặc tăng token/chi phí bất thường, vào lại Langfuse Prompts và gán lại label `production` về Version 1 (`v1`). Ứng dụng sẽ tự động rollback ngay lập tức.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
  1. `latency`: Đo độ trễ P50, P95, P99 và TTFT P95 (threshold: P95 <= 2000ms).
  2. `traffic`: Tổng số lượng request và throughput theo phút (phân tích theo feature).
  3. `errors`: Tỉ lệ lỗi tổng thể và tỉ lệ thành công của retrieval tool (threshold: error_rate <= 2%).
  4. `cost`: Tổng chi phí USD tích lũy và chi phí trung bình trên mỗi request.
  5. `tokens`: Tổng lượng input tokens và output tokens tiêu thụ.
  6. `quality`: Điểm đánh giá chất lượng heuristic trung bình (threshold: quality_score >= 0.75).
- **SLO và lý do chọn:**
  - Service: `day13-l3b-monitoring-llmops-lab`.
  - Primary SLO: `99.5%` fast_successful_requests trong chu kỳ 28 ngày (`28d`).
  - SLI: Số request có `event == "response_sent"` và `latency_ms <= 3000` chia cho tổng số `event == "request_received"`.
  - Lý do chọn: Mô hình trợ lý AI cần phản hồi nhanh và tin cậy; ngưỡng 3000ms là giới hạn chấp nhận được của người dùng trước khi họ cảm thấy hệ thống bị treo hoặc bỏ dở phiên chat.
- **Cách tính error budget:**
  - Với mục tiêu SLO là 99.5% trong cửa sổ 28 ngày, Error Budget cho phép là `0.5%` ($100\% - 99.5\%$).
  - Nếu hệ thống tiếp nhận dự kiến 10,000 requests trong 28 ngày, thì số lượng request tối đa được phép bị lỗi (HTTP 500) hoặc phản hồi chậm quá 3000ms là:
    $$10,000 \times 0.5\% = 50 \text{ requests}$$
  - Khi số request lỗi vượt quá 50, error budget bị cạn kiệt (exhausted), đội ngũ kỹ thuật phải đóng băng tính năng mới (feature freeze) và tập trung khắc phục độ ổn định.
- **Ba alert và runbook tương ứng:**
  1. `HighErrorRate` (Critical): Kích hoạt khi `error_rate_pct > 2%` kéo dài trong 2 phút. Gửi Slack `#k4-l3b-alerts`. Runbook: Kiểm tra panel Error rate, lọc log tìm `event == "request_failed"` lấy `correlation_id`, tra cứu trace Langfuse để xác định sập Vector DB hay LLM provider timeout, kích hoạt feature flag fallback hoặc restart service.
  2. `AnomalousCostSpike` (Warning): Kích hoạt khi chi phí `cost_usd_per_minute > 2.5` kéo dài trong 2 phút. Gửi Slack `#k4-l3b-alerts`. Runbook: Kiểm tra panel Cost & Tokens xem output tokens có tăng vọt không, lọc log tìm request tốn tiền bất thường, mở trace kiểm tra prompt injection hoặc model bị lặp vô tận, giới hạn `max_tokens` hoặc chặn IP spam.
  3. `LowQualityProxy` (Warning): Kích hoạt khi `quality_score_avg < 0.75` trong 5 phút. Gửi Slack `#k4-l3b-alerts`. Runbook: Kiểm tra phân phối điểm quality trên dashboard, tìm correlation ID của các phản hồi điểm thấp, kiểm tra độ tương thích của prompt hoặc ngữ cảnh RAG bị lệch chủ đề, rollback prompt về phiên bản ổn định gần nhất.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** 22:47 - 22:48 UTC+7 (15:47:54Z - 15:48:05Z ngày 30/09/2026)
- **Triệu chứng từ metrics:** Tại Panel 1 (`Latency percentiles and TTFT`), P95 Latency tăng vọt từ mức baseline ~151ms lên **2652.0 ms** (vượt xa ngưỡng cho phép `2000 ms` được chỉ định trong challenge). Trong khi đó, TTFT P95 không bị ảnh hưởng, giữ nguyên ở mức **50.0 ms**, và Panel Errors ghi nhận tỉ lệ lỗi là **0%** (hệ thống không phát sinh exception hay HTTP 500).
- **Log line và correlation ID liên quan:** 
  - `correlation_id`: `req-5fe8da1f` (request cho session `k4-l3b-challenge-s05`, feature `monitoring`).
  - Log line đại diện trong `data/logs.jsonl`:
    ```json
    {"service": "api", "latency_ms": 2652, "ttft_ms": 50, "tokens_in": 49, "tokens_out": 121, "cost_usd": 0.001962, "quality_score": 0.8, "tool_name": "retrieval", "tool_success": true, "payload": {"answer_preview": "Starter answer. You should improve this output logic and add better quality chec..."}, "event": "response_sent", "user_id_hash": "68e37dc7cb5e", "correlation_id": "req-5fe8da1f", "env": "dev", "model": "claude-sonnet-4-5", "feature": "monitoring", "session_id": "k4-l3b-challenge-s05", "level": "info", "ts": "2026-09-30T15:47:54.375751Z"}
    ```
- **Trace ID và span gây ảnh hưởng:**
  - Trace tương ứng với `correlation_id`: `req-5fe8da1f` trên Langfuse project `day13-k4-l3b-2A202602601`.
  - Trace waterfall cho thấy root observation `day13-agent-request` tốn tổng cộng **2.65s**.
  - Span gây ảnh hưởng chính là child span **`retrieval` (as_type: retriever)** tốn tới **2.50s (2500ms)** chiếm > 94% tổng thời gian request.
  - Span `generation` chỉ tốn **0.15s (150ms)** với TTFT 50ms (hoàn toàn bình thường).
- **Root cause:** Điểm nghẽn độ trễ xảy ra tại tầng truy xuất tài liệu (Document Retrieval - RAG) trong hàm `retrieve()`, bị trễ thêm 2500ms mỗi request do sự cố `rag_slow` được kích hoạt (mô phỏng tình trạng Vector Database hoặc External Retriever bị quá tải/nghẽn mạng). Tầng LLM generation và server API không bị lỗi.
- **Fix action:**
  1. Tắt sự cố khẩn cấp: `python scripts/inject_incident.py --scenario rag_slow --disable` để khôi phục độ trễ về baseline.
  2. Scale-up số lượng replica cho cụm Vector Store (Chroma/Qdrant/Pinecone) và tối ưu hóa vector indexing.
  3. Áp dụng Redis Semantic Cache cho các truy vấn và văn bản phổ biến để giảm tải truy vấn trực tiếp vào vector database.
- **Preventive measure:**
  1. **Thêm Timeout & Fallback cho Retrieval**: Cấu hình timeout cứng cho tầng retrieval (ví dụ 1000ms); nếu quá thời gian lập tức fallback về tài liệu mặc định thay vì làm treo request của người dùng.
  2. **Áp dụng Circuit Breaker**: Tự động ngắt gọi tới vector database khi phát hiện tỉ lệ trễ cao liên tục để bảo vệ toàn hệ thống.
  3. **Alerting chuyên biệt cho RAG**: Cấu hình alert giám sát riêng span `retrieval` (`retrieval_latency_p95 > 1000ms` kéo dài 2 phút) gửi cảnh báo tới kênh Slack On-call để xử lý trước khi vi phạm SLO chung.

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
  - Quyết định tích hợp hàm `scrub_event` như một processor trực tiếp trong chuỗi `structlog.configure()` thay vì chỉ scrub thủ công ở router. Lý do: Giúp ngăn chặn rò rỉ PII ở mức độ kiến trúc (defense-in-depth); bất kể log được gọi từ router, agent hay middleware, toàn bộ payload đều bắt buộc phải đi qua bộ lọc regex trước khi được serialize thành JSON và ghi vào đĩa.
- **Một lỗi/blocker đã gặp:**
  - Vấn đề mã hóa ký tự UTF-8 trên Windows PowerShell khi chạy các CLI script, dẫn đến việc output tiếng Việt bị vỡ font hoặc sinh ra `UnicodeEncodeError`. Ngoài ra, request đầu tiên bị latency spike giả do cơ chế cold start khi khởi tạo Langfuse client và fetch remote prompt qua mạng.
- **Cách tìm nguyên nhân và xử lý:**
  - Sử dụng hàm `configure_utf8_stdio()` từ `app.cli` để tái cấu hình `sys.stdout` và `sys.stderr` với encoding UTF-8 ngay đầu mỗi script.
  - Với hiện tượng cold start, thực hiện chạy một workload warmup trước khi đo lường baseline chính thức, đảm bảo kết quả P50/P95 phản ánh chính xác hiệu năng runtime.
- **Cách hiểu luồng Metrics → Logs → Traces:**
  - **Metrics (What)**: Đóng vai trò cảnh báo sớm (Early Detection). Trả lời câu hỏi *"Hệ thống đang gặp vấn đề gì, ở panel nào, tại thời điểm nào?"* (ví dụ: P95 latency nhảy vọt > 2000ms).
  - **Logs (Where/Who)**: Đóng vai trò khoanh vùng (Localization). Trả lời câu hỏi *"Request nào, session nào, người dùng nào bị ảnh hưởng?"*, từ đó cung cấp khóa liên kết quan trọng nhất là `correlation_id`.
  - **Traces (Why)**: Đóng vai trò giải phẫu chi tiết (Root Cause Analysis). Khi mở trace theo `correlation_id`, cây Waterfall sẽ bóc tách từng span (retrieval vs generation) và chỉ đích danh mắt xích nào tiêu tốn thời gian bất thường hoặc gây ra lỗi.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
  - Khác với phần mềm truyền thống chỉ có code và data, ứng dụng LLM có thêm trục Prompt và Mô hình. Prompt versioning cho phép coi prompt như một artifact có phiên bản, có thể audit và A/B testing.
  - Quản lý token/cost giúp ngăn ngừa rủi ro cạn kiệt ngân sách hoặc bị tấn công prompt injection gây lạm dụng tài nguyên.
  - SLO và Error Budget tạo ra ranh giới định lượng giữa tốc độ phát triển tính năng và độ ổn định của hệ thống.
  - Cơ chế Rollback tức thì thông qua label (chuyển `production` từ v2 về v1) cho phép kỹ sư khôi phục dịch vụ chỉ trong vài giây mà không cần deploy lại toàn bộ container hay restart backend.
- **Điều quan trọng nhất đã học:**
  - Xây dựng một hệ thống LLMOps không đơn thuần là gọi API mô hình, mà là làm chủ toàn diện vòng đời quan sát: từ Structured Logging bảo mật PII, Distributed Tracing phân rã chi phí/độ trễ, cho đến Dashboarding, Alerting và quy trình điều tra sự cố chuẩn mực.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**
  - Hiện tại mới mô phỏng việc sinh câu trả lời và retrieval qua fake logic; trong môi trường sản xuất thực tế cần kết nối với vector database thực (như Qdrant/Chroma) và LLM provider thực tế kèm cơ chế retry/backoff linh hoạt hơn.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
