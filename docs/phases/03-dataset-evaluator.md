# Phase 3 — Chuẩn bị Spider và kiểm tra evaluator

[Tổng quan](../integration-plan.md) · [Contract các method](../method-contracts.md)

**Trạng thái:** Chưa bắt đầu.

**Phụ thuộc:** [Phase 2](02-bootstrap.md).

**Mục tiêu:** xác nhận dữ liệu và cách chấm trước khi chạy inference nhiều lần.

**Công việc:**

- [ ] Chuẩn bị Spider dev, schema và SQLite databases từ nguồn chính thức.
- [ ] Tạo subset cố định 3–10 mẫu, lưu chỉ số gốc, `db_id`, thứ tự và checksum dữ liệu nguồn.
- [ ] Tạo input phù hợp với từng method; không thay đổi dataset nguồn.
- [ ] Tách đường dẫn database dùng cho inference và test-suite databases dùng cho evaluation.
- [ ] Chuẩn bị gold file theo đúng subset.
- [ ] Chạy kiểm tra evaluator bằng gold-as-prediction và prediction sai có kiểm soát.
- [ ] Chốt chính sách metric, `plug_value`, `keep_distinct` và cách xử lý prediction lỗi.

**Contract evaluator:** gold có dạng `SQL<TAB>db_id`; prediction có một SQL mỗi dòng theo cùng thứ tự. Test-suite accuracy cần bộ test-suite databases. Chỉ đánh giá trên database Spider gốc chưa đủ để gọi kết quả là test-suite accuracy.

**Đầu ra:** subset manifest, input đã chuẩn bị, gold file và smoke test evaluator.

**Tiêu chí hoàn thành:** evaluator chấm được subset xác định, phân biệt prediction đúng/sai và không làm lệch mapping giữa mẫu, database và prediction.

## File/module dự kiến thay đổi

Đường dẫn dưới đây là dự kiến, điều chỉnh theo contract đã xác minh.

- `src/test2sql/datasets/`: chuẩn bị subset và input.
- `src/test2sql/evaluation/`: wrapper evaluator tối thiểu để kiểm tra dữ liệu.
- `tests/`: kiểm tra mapping và smoke test evaluator.
- `data/`, `results/`: dữ liệu và artifacts local, không commit.

## Cách kiểm tra

- [ ] Tạo lại cùng subset và đối chiếu ID, thứ tự, db_id và checksum.
- [ ] Chấm gold-as-prediction và một prediction sai có kiểm soát; lưu command cùng output evaluator.
- [ ] Kiểm tra input có cùng danh sách mẫu cho cả ba method và dataset nguồn giữ nguyên.

## Kết quả thực tế và bàn giao

- Chưa triển khai; chưa có kết quả kiểm tra.
- Khi thực hiện, ghi command/check đã chạy, kết quả, run ID hoặc đường dẫn bằng chứng và quyết định ảnh hưởng phase sau.
- Chỉ đánh dấu hoàn thành khi đạt tiêu chí và có bằng chứng kiểm tra.

## Vấn đề còn lại

- Chưa xác định; cập nhật trong quá trình thực hiện.
