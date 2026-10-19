# Phase 5 — Tích hợp MAC-SQL và DAIL-SQL

[Tổng quan](../integration-plan.md) · [Contract các method](../method-contracts.md)

**Trạng thái:** Chưa bắt đầu.

**Phụ thuộc:** [Phase 4](04-few-shot.md).

**Mục tiêu:** Chạy và đánh giá đủ ba method trên cùng tập mẫu.

**Công việc:**

- [ ] Thêm hai adapter theo contract của Phase 1, dùng chung helper khi phù hợp.
- [ ] Chuẩn bị preprocessing và tài nguyên riêng bên ngoài source repo con.
- [ ] Dùng cùng subset, model và chính sách evaluation.
- [ ] Ghi rõ cấu hình riêng: prompt, số demonstrations, retrieval, sampling và các bước trung gian.
- [ ] Chạy tuần tự cả ba method.
- [ ] Lưu trạng thái riêng cho từng method để một method lỗi không làm mất kết quả của các method còn lại.

**Đầu ra:** chạy cả ba method và thu kết quả theo cùng một manifest tập mẫu.

**Tiêu chí hoàn thành:** ba method chạy và được chấm trên đúng cùng danh sách mẫu; mỗi method có raw output, predictions, logs, exit code và metrics riêng.

**Mốc MVP:** hoàn thành Phase 5.

## File/module dự kiến thay đổi

Đường dẫn dưới đây là dự kiến, điều chỉnh theo contract đã xác minh.

- `src/test2sql/methods/mac_sql.py`, `src/test2sql/methods/dail_sql.py`: hai adapter.
- `src/test2sql/datasets/`: chuẩn bị input riêng nếu cần.
- `src/test2sql/runner.py`, `configs/methods.yaml`: chạy tuần tự và trạng thái riêng.
- `tests/`: kiểm tra output và lỗi độc lập giữa các method.

## Cách kiểm tra

- [ ] Chạy từng adapter riêng trên subset nhỏ trước khi chạy method all.
- [ ] Đối chiếu danh sách/thứ tự mẫu, model và evaluation flags của cả ba method.
- [ ] Mô phỏng một method thất bại; xác nhận artifacts của các method còn lại vẫn được giữ.

## Kết quả thực tế và bàn giao

- Chưa triển khai; chưa có kết quả kiểm tra.
- Khi thực hiện, ghi command/check đã chạy, kết quả, run ID hoặc đường dẫn bằng chứng và quyết định ảnh hưởng phase sau.
- Chỉ đánh dấu hoàn thành khi đạt tiêu chí và có bằng chứng kiểm tra.

## Vấn đề còn lại

- Chưa xác định; cập nhật trong quá trình thực hiện.
