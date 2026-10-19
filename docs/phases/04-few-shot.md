# Phase 4 — Chạy Few-shot/DIN-SQL qua CLI chính

[Tổng quan](../integration-plan.md) · [Contract các method](../method-contracts.md)

**Trạng thái:** Chưa bắt đầu.

**Phụ thuộc:** [Phase 3](03-dataset-evaluator.md).

**Mục tiêu:** Hoàn thành luồng inference và evaluation đầu tiên bằng Few-shot/DIN-SQL.

**Công việc:**

- [ ] Viết adapter đầu tiên để dựng command, truyền env, chạy subprocess và thu output.
- [ ] Lưu command, revision, cấu hình, thời gian, exit code và logs.
- [ ] Giữ raw output; tạo prediction chuẩn hóa có ID ánh xạ về subset.
- [ ] Phát hiện thiếu, thừa, trùng hoặc sai thứ tự prediction. Không ghép hai danh sách bằng cách âm thầm cắt phần thừa.
- [ ] Chạy 3 mẫu, sau đó 10 mẫu và chấm kết quả.
- [ ] Kiểm tra checkout repo con vẫn giữ nguyên sau khi chạy.

**Đầu ra:** một run hoàn chỉnh từ CLI đến predictions và metrics.

**Tiêu chí hoàn thành:** Few-shot/DIN-SQL chạy xuyên suốt qua repo chính và có thể đánh giá lại từ predictions đã lưu mà không gọi LLM.

## File/module dự kiến thay đổi

Đường dẫn dưới đây là dự kiến, điều chỉnh theo contract đã xác minh.

- `src/test2sql/methods/few_shot.py`: adapter Few-shot/DIN-SQL.
- `src/test2sql/runner.py`: subprocess, logs và trạng thái run.
- `src/test2sql/cli.py`, `configs/methods.yaml`: nối adapter với CLI.
- `tests/`: kiểm tra command, mapping và lỗi output.

## Cách kiểm tra

- [ ] Kiểm tra command/env, exit code khác 0 và prediction thiếu/thừa.
- [ ] Chạy thực tế 3 mẫu, rồi 10 mẫu; lưu run ID và metrics.
- [ ] Chấm lại predictions đã lưu và kiểm tra working tree repo con sau khi chạy.

## Kết quả thực tế và bàn giao

- Chưa triển khai; chưa có kết quả kiểm tra.
- Khi thực hiện, ghi command/check đã chạy, kết quả, run ID hoặc đường dẫn bằng chứng và quyết định ảnh hưởng phase sau.
- Chỉ đánh dấu hoàn thành khi đạt tiêu chí và có bằng chứng kiểm tra.

## Vấn đề còn lại

- Chưa xác định; cập nhật trong quá trình thực hiện.
