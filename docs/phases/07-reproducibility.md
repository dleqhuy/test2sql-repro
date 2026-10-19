# Phase 7 — Hoàn thiện và chạy benchmark

[Tổng quan](../integration-plan.md) · [Contract các method](../method-contracts.md)

**Trạng thái:** Chưa bắt đầu.

**Phụ thuộc:** [Phase 6](06-reporting.md).

**Mục tiêu:** Hoàn thiện khả năng chạy lại và xác minh quy trình tái lập benchmark.

**Công việc:**

- [ ] Hỗ trợ chạy lại method thất bại và bỏ qua output đã hoàn chỉnh sau khi kiểm tra manifest tương thích.
- [ ] Chỉ hỗ trợ resume từng mẫu khi xác nhận được mapping và khả năng của method; nếu chưa hỗ trợ thì báo rõ và chạy lại method theo chính sách đã ghi.
- [ ] Kiểm thử các điểm quan trọng: command/environment, ánh xạ prediction, thiếu output, subprocess lỗi và trích xuất metrics.
- [ ] Viết README hướng dẫn setup trên môi trường sạch.
- [ ] Chạy lần lượt 10 mẫu, subset lớn hơn, rồi toàn bộ dev.
- [ ] Lưu manifest, logs và metrics của benchmark hoàn chỉnh.

**Đầu ra:** hướng dẫn tái lập và bộ kết quả benchmark.

**Tiêu chí hoàn thành:** clone repo, cấu hình môi trường và làm theo README là thực hiện được toàn bộ luồng chạy; revisions và dữ liệu sử dụng được ghi nhận đầy đủ.

## File/module dự kiến thay đổi

Đường dẫn dưới đây là dự kiến, điều chỉnh theo contract đã xác minh.

- `src/test2sql/runner.py`, `src/test2sql/cli.py`: chạy lại, skip và resume đã xác minh.
- `tests/`: các kiểm tra cần thiết cho luồng hoàn chỉnh.
- `README.md`: hướng dẫn setup và tái lập.
- `results/`: benchmark artifacts local; ghi vị trí lưu trong kết quả phase.

## Cách kiểm tra

- [ ] Làm theo README trong môi trường sạch và ghi lại kết quả.
- [ ] Kiểm tra chạy lại method lỗi, skip output tương thích và từ chối output không tương thích.
- [ ] Chạy theo thứ tự 10 mẫu → subset lớn hơn → toàn bộ dev; lưu bằng chứng từng mốc.

## Kết quả thực tế và bàn giao

- Chưa triển khai; chưa có kết quả kiểm tra.
- Khi thực hiện, ghi command/check đã chạy, kết quả, run ID hoặc đường dẫn bằng chứng và quyết định ảnh hưởng phase sau.
- Chỉ đánh dấu hoàn thành khi đạt tiêu chí và có bằng chứng kiểm tra.

## Vấn đề còn lại

- Chưa xác định; cập nhật trong quá trình thực hiện.
