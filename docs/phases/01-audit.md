# Phase 1 — Khảo sát và chốt contract

[Tổng quan](../integration-plan.md) · [Contract các method](../method-contracts.md)

**Trạng thái:** Hoàn thành ngày 2026-10-19 (khảo sát source và parser; chưa chạy inference).

**Phụ thuộc:** Không có; đây là phase bắt đầu.

**Mục tiêu:** xác định chính xác cách chạy từng fork trước khi viết adapter.

**Công việc:**

- [x] Xác định commit của ba fork đã hỗ trợ biến môi trường.
- [x] Kiểm tra entry point, arguments, working directory, dependencies và output.
- [x] Xác định các bước preprocessing, retrieval và tài nguyên bổ sung của mỗi method.
- [x] Kiểm tra tên biến LLM thực tế, model được dùng và khả năng bị override trong source.
- [x] Kiểm tra các file method ghi ra trong quá trình chạy (đối chiếu source).
- [x] Xác nhận khả năng chọn subset, giữ thứ tự và resume (đối chiếu source; chưa kiểm chứng runtime).
- [x] Kiểm tra CLI của evaluator tại revision sẽ pin.

**Đầu ra:** [method-contracts.md](../method-contracts.md) ghi contract, command templates, revision, bằng chứng source và phương án adapter cho ba method cùng evaluator.

**Tiêu chí hoàn thành:** biết command, dependencies, input/output và phương án chạy cả ba method cùng evaluator mà không sửa source repo con. Đã ghi rõ các giới hạn chưa giải quyết; không đánh đồng khảo sát source với inference thành công.

## File đã thay đổi

- `docs/method-contracts.md`: contract tập trung tại revision khảo sát, chính sách evaluator và bàn giao.
- `docs/phases/01-audit.md`: checklist, kết quả và giới hạn.
- `docs/integration-plan.md`: cập nhật trạng thái Phase 1 và thông tin khảo sát.
- `docs/phases/evidence/01-audit.json`: revision, SHA-256 source/requirements, parser probes, command/exit code/stdout/stderr của các lần help và trạng thái checkout sau kiểm tra.
- `docs/phases/evidence/audit_phase1.py`: script thư viện chuẩn để tái kiểm tra evidence trên đúng revision, không tải dependencies hay gọi LLM.

## Cách kiểm tra và kết quả

- [x] Đối chiếu command và arguments trực tiếp với source tại commit đã ghi.
- [x] Kiểm tra dependencies và các đường dẫn đọc/ghi; thử help và kiểm tra tĩnh khi chưa có môi trường method.
- [x] Ghi riêng thông tin xác minh từ source và thông tin đã kiểm chứng bằng runtime.

Các checkout tạm được clone `--depth 1` từ đúng repository trong kế hoạch, đặt ở `/tmp/test2sql-phase1-audit/{few-shot,MAC-SQL,DAIL-SQL,test-suite-sql-eval}`. Không thêm submodule trong phase này; Phase 2 pin theo bảng revision trong contract. Clone ban đầu trong sandbox lỗi DNS; clone qua quyền network được cấp đã thành công, không còn bị chặn truy cập source.

Kiểm tra chạy bằng **Python 3.14.3** của máy khảo sát (không phải runtime được khuyến nghị cho method):

```bash
python3 docs/phases/evidence/audit_phase1.py /tmp/test2sql-phase1-audit \
  > docs/phases/evidence/01-audit.json
```

Muốn tái lập: clone bốn repo vào các thư mục trên, checkout đúng SHA trong contract rồi chạy script từ repo chính. Checkout phải sạch; nếu HEAD đã thay đổi sau thời điểm khảo sát cần fetch SHA đã ghi, không dùng HEAD mới thay thế. Script không tự fetch, install, đổi revision hoặc ghi vào repo con. Để kiểm tra mà giữ nguyên evidence đã lưu, redirect ra file tạm và đối chiếu kết quả.

| Kiểm tra | Kết quả | Ý nghĩa |
| --- | --- | --- |
| HEAD, tracked Python source và working tree | Đúng bốn SHA; AST parse 5 + 23 + 23 + 6 = 57 file; cả bốn checkout sạch trước/sau | Xác minh revision và cú pháp trên Python khảo sát, không chứng minh dependencies tương thích |
| Parser cô lập từ source | 5 probe pass: MAC run, DAIL preprocess/generate/ask, evaluator | Command template và argparse defaults hợp lệ; bỏ qua imports và xử lý sau parse |
| `python3 -B DIN-SQL.py --help` | Exit 1, thiếu `pandas` | Chưa tới argv; source dùng kiểm tra positional thủ công, không có help |
| `python3 -B run.py --help` | Exit 1, thiếu `func_timeout` | Chưa chạy entry point MAC |
| `python3 -B data_preprocess.py --help` | Exit 1, thiếu `tqdm` | Chưa chạy preprocessing DAIL |
| `python3 -B generate_question.py --help` | Exit 1, thiếu `transformers` | Chưa chạy retrieval/prompt generation DAIL |
| `python3 -B ask_llm.py --help` | Exit 1, thiếu `openai` | Chưa chạy inference DAIL |
| `python3 -B evaluation.py --help` | Exit 1, thiếu `nltk` | Chưa chạy evaluator thực tế |

Help attempts dùng environment tối thiểu và credentials giả, không truyền `.env` hoặc key người dùng. Không có LLM request, dataset download, SQL evaluation hay run ID được tạo. Log từng attempt nằm trong [evidence](evidence/01-audit.json).

## Quyết định và bàn giao

Các command, SHA và dependencies chi tiết chỉ lưu trong [contract tập trung](../method-contracts.md) để tránh lệch thông tin.

- Giữ nguyên source repo con; DAIL dùng workspace chạy riêng vì hard-code dataset/output tương đối cwd.
- Một subset manifest chung; DIN và DAIL map theo thứ tự khi đủ dòng. MAC dùng `question_id` cục bộ liên tục và map JSONL theo `idx`, không tin file SQL export khi resume.
- Không dùng shell wrapper DAIL vì nó override model bằng `gpt-4` và nhận key qua arguments. Gọi Python trực tiếp với environment; baseline DAIL `n=1`, hai lượt sinh SQL/retrieval.
- Chốt evaluator `etype=all`, `plug_value=false`, `keep_distinct=true`; kiểm tra cardinality trước gọi evaluator. Phân biệt exact set match với execution; không báo test-suite accuracy khi chỉ có DB gốc.
- Chưa cung cấp `test2sql` CLI, cài dependencies hoặc thêm submodules; đó là Phase 2. Không đánh dấu các phase sau đã bắt đầu.

## Giới hạn còn lại và nơi xử lý

- **Phase 2:** cài/lock môi trường thật cho mỗi method, nhất là requirements cũ DIN và cặp torch/torchtext của DAIL; Python 3.14 máy khảo sát không thay thế các môi trường đó.
- **Phase 3:** tải dữ liệu, test-suite databases, NLTK resource phù hợp; kiểm thử evaluator gold/sai/invalid, validation số dòng và timeout process. `asyncio.wait_for` trong source không ngắt chắc chắn SQLite đồng bộ.
- **Phase 4:** kiểm chứng DIN trên 3 mẫu; method chỉ ghi output sau toàn batch và có retry vô hạn.
- **Phase 5:** kiểm chứng MAC skip lỗi/resume, request ping bổ sung, DAIL CoreNLP/GloVe/retrieval/mapping. DAIL đếm token bằng 0 và có nhánh lỗi `InvalidRequestError`; giữ nguyên source, ghi limitation và xử lý thất bại rõ ràng ở orchestrator. Chưa bật resume/self-consistency trước kiểm chứng riêng.

Các giới hạn này được xác định đủ để thiết kế adapter; không còn thiếu source hoặc chưa biết giao diện của method. Chưa có bằng chứng end-to-end và không tuyên bố benchmark đã chạy.
