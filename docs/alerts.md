# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighErrorRate`
- Severity: `critical`
- Duration: `2m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: guardrail `error_rate_pct_max`
- Điều kiện và thời gian duy trì: `error_rate_pct > 2%` trong vòng 2 phút liên tục.
- Ảnh hưởng tới người dùng: Người dùng liên tục nhận được thông báo lỗi, không thể lấy được câu trả lời từ AI.
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard Streamlit kiểm tra panel Error Rate xem số lượng request_failed tăng đột biến ở thời điểm nào.
  2. Mở file `data/logs.jsonl`, tìm các log có `event == "request_failed"` trong khoảng thời gian đó, xem `error_type` và copy `correlation_id`.
  3. Lên Langfuse tìm `correlation_id` đó, kiểm tra xem lỗi xuất phát từ span `retrieval` (vector DB sập) hay `generation` (LLM timeout).
- Mitigation tạm thời: Tạm thời tắt tính năng (feature flag) hoặc restart service. Nếu do LLM provider, cân nhắc chuyển sang provider dự phòng (fallback).
- Owner: `student-2A202602601`

## Alert 2

- Tên: `AnomalousCostSpike`
- Severity: `warning`
- Duration: `2m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: guardrail `daily_cost_usd_max`
- Điều kiện và thời gian duy trì: Tổng `cost_usd` tăng quá nhanh (ví dụ vượt 2.5 USD/phút) trong vòng 2 phút.
- Ảnh hưởng tới người dùng: Không ảnh hưởng trực tiếp đến người dùng, nhưng ảnh hưởng nghiêm trọng đến chi phí vận hành (có nguy cơ bị lạm dụng/DDoS).
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra panel Cost và Tokens trên Dashboard xem có sự gia tăng bất thường về lượng token output không.
  2. Mở `data/logs.jsonl` tìm request có `cost_usd` cao đột biến và lấy `correlation_id`.
  3. Mở Langfuse kiểm tra xem model có bị rơi vào vòng lặp sinh text dài vô hạn không, hoặc người dùng cố tình chèn prompt hacking.
- Mitigation tạm thời: Block IP người dùng spam, tạm thời giới hạn độ dài `max_tokens` của LLM, hoặc rollback prompt nếu prompt mới gây tốn token.
- Owner: `student-2A202602601`

## Alert 3

- Tên: `LowQualityProxy`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: guardrail `quality_score_avg_min`
- Điều kiện và thời gian duy trì: Điểm số trung bình `quality_score_avg < 0.75` duy trì trong 5 phút.
- Ảnh hưởng tới người dùng: Người dùng nhận được các câu trả lời kém chất lượng, lạc đề hoặc chứa thông tin không chính xác (hallucinations), làm giảm trải nghiệm.
- Ba bước kiểm tra đầu tiên:
  1. Nhìn vào panel Quality Proxy trên Dashboard để xác nhận xu hướng giảm.
  2. Tìm trong log các request có `quality_score < 0.75` và lấy `correlation_id`.
  3. Truy cập Langfuse để xem trực tiếp Prompt và Context lúc đó. Phân tích xem có phải do `retrieval` trả về tài liệu sai hay do LLM model sinh kết quả kém.
- Mitigation tạm thời: Khôi phục version Prompt trước đó trên Langfuse (bằng cách đổi label production) nếu phiên bản mới có vấn đề. Kiểm tra lại dữ liệu Retrieval.
- Owner: `student-2A202602601`
