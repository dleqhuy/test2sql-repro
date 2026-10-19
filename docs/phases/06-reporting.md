# Phase 6 — Report và đánh giá lại

[Tổng quan](../integration-plan.md) · [Contract các method](../method-contracts.md)

**Trạng thái:** Chưa bắt đầu.

**Phụ thuộc:** [Phase 5](05-mac-dail.md).

**Mục tiêu:** Đánh giá lại và tạo báo cáo so sánh từ predictions đã lưu.

**Công việc:**

- [ ] Hoàn thiện `evaluate --run-id` để chấm predictions đã lưu.
- [ ] Thêm `report --run-id`, xuất `summary.json` và `summary.csv`.
- [ ] Báo cáo số mẫu yêu cầu, số prediction hợp lệ, số lỗi, metric và thời gian.
- [ ] Ghi evaluator commit, phiên bản dữ liệu, databases và evaluation flags.
- [ ] Không âm thầm loại mẫu lỗi khỏi mẫu số. Run chưa đầy đủ phải được đánh dấu rõ; nếu báo metric trên phần hoàn thành thì ghi rõ phạm vi và mẫu số.
- [ ] Chỉ so sánh trực tiếp các run có cùng tập mẫu và chính sách evaluation.
- [ ] Giữ nguyên stdout/stderr evaluator để kiểm tra khi bước trích xuất metrics thất bại.

**Đầu ra:** report so sánh ba method với thông tin đủ để kiểm tra cách chấm.

**Tiêu chí hoàn thành:** có thể tạo lại metrics và report từ predictions cũ mà không cần LLM. Không ghi metric thất bại thành giá trị 0 giả định.

## File/module dự kiến thay đổi

Đường dẫn dưới đây là dự kiến, điều chỉnh theo contract đã xác minh.

- `src/test2sql/evaluation/`: đánh giá lại và trích xuất metrics.
- `src/test2sql/reporting/`: tạo summary JSON/CSV khi cần.
- `src/test2sql/cli.py`: evaluate và report.
- `tests/`: kiểm tra mẫu số, run thiếu và lỗi evaluator.

## Cách kiểm tra

- [ ] Chạy evaluate/report từ một run đã lưu khi LLM không được sử dụng.
- [ ] Kiểm tra run đầy đủ, run thiếu prediction và evaluator lỗi.
- [ ] Đối chiếu summary với output evaluator; xác nhận không gán lỗi thành metric 0.

## Kết quả thực tế và bàn giao

- Chưa triển khai; chưa có kết quả kiểm tra.
- Khi thực hiện, ghi command/check đã chạy, kết quả, run ID hoặc đường dẫn bằng chứng và quyết định ảnh hưởng phase sau.
- Chỉ đánh dấu hoàn thành khi đạt tiêu chí và có bằng chứng kiểm tra.

## Vấn đề còn lại

- Chưa xác định; cập nhật trong quá trình thực hiện.
