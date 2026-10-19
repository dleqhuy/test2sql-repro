# Phase 3 — Chuẩn bị Spider và kiểm tra evaluator

[Tổng quan](../integration-plan.md) · [Contract các method](../method-contracts.md)

**Trạng thái:** Hoàn thành — dữ liệu chính thức, input/subset và evaluator đã kiểm chứng ngày 2026-10-19.

**Phụ thuộc:** [Phase 2](02-bootstrap.md).

**Mục tiêu:** xác nhận dữ liệu và cách chấm trước khi chạy inference nhiều lần.

**Công việc:**

- [x] Chuẩn bị Spider dev, schema và SQLite databases từ nguồn chính thức.
- [x] Tạo subset cố định 3–10 mẫu, lưu chỉ số gốc, `db_id`, thứ tự và checksum dữ liệu nguồn.
- [x] Tạo input phù hợp với từng method; không thay đổi dataset nguồn.
- [x] Tách đường dẫn database dùng cho inference và test-suite databases dùng cho evaluation.
- [x] Chuẩn bị gold file theo đúng subset.
- [x] Chạy kiểm tra evaluator bằng gold-as-prediction và prediction sai có kiểm soát.
- [x] Chốt chính sách metric, `plug_value`, `keep_distinct` và cách xử lý prediction lỗi.

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

- [x] Tạo lại cùng subset và đối chiếu ID, thứ tự, db_id và checksum.
- [x] Chấm gold-as-prediction và một prediction sai có kiểm soát; lưu command cùng output evaluator.
- [x] Kiểm tra input có cùng danh sách mẫu cho cả ba method và dataset nguồn giữ nguyên.

## Kết quả thực tế và bàn giao

- `scripts/setup_data.py`: tải/cài ZIP chính thức, pin SHA256, chống path traversal/symlink/duplicate member, ghi provenance từng file và không ghi đè dữ liệu đã có. Cài lại kiểm tra checksum dữ liệu hiện hữu.
- `src/test2sql/datasets/`: subset cố định theo chỉ số nguồn, ID/thứ tự/db_id/checksum; stage atomic, không để lại run dở khi validation lỗi. Kiểm tra checksum nguồn khi có provenance trước khi stage và xác nhận nguồn không đổi sau khi copy.
- `test2sql prepare --method all`: DIN nhận dev subset và tables đầy đủ; MAC có ID local và database copies; DAIL có dataset/process riêng, source links, đủ 166 database, train JSON và gold gốc. Merged training JSON được tạo theo đúng thứ tự train_spider rồi train_others. Source checkout và shared dataset không bị sửa.
- `test2sql evaluate`: validation số lượng/ID/mapping, gold/schema checksum, bộ test suites đầy đủ và checksum từng variant trước subprocess. Giữ raw prediction, SQL đã xếp thứ tự, stdout/stderr và result JSON. Không âm thầm sửa SQL hoặc bỏ mẫu lỗi; prediction SQL text chỉ được map theo vị trí nếu caller bảo đảm thứ tự.
- `test2sql check-evaluator`: gold, wrong và invalid smoke cases; subprocess có timeout cứng ở cấp process group trên POSIX. Lỗi/timeout/incomplete output không tạo metrics thành công.

### Dữ liệu đã chuẩn bị

Nguồn [Spider chính thức](https://yale-lily.github.io/spider) trỏ đến [spider_data.zip](https://drive.google.com/file/d/1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J/view). Đã tải và cài 1.034 dev examples, 166 schemas, 166 SQLite databases; train_spider 7.000 + train_others 1.659 examples. JSON/schema/gold nguồn được giữ byte-for-byte.

Nguồn [Test Suite SQL Eval](https://github.com/taoyds/test-suite-sql-eval) trỏ đến [testsuitedatabases.zip](https://drive.google.com/file/d/1mkCx2GOFIqNesD4y8TDAO1yX1QZORP5w/view). Đã tải archive đầy đủ; chỉ extract 20 database thuộc Spider dev, gồm 695 SQLite files. Không dùng dữ liệu của benchmark khác trong archive.

| Archive | SHA256 quan sát từ nguồn chính thức |
| --- | --- |
| spider_data.zip | `00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b` |
| testsuitedatabases.zip | `9ec24ea8debc6bd04abfe137b5f1a739b5a8836f32c0464e4dfc94eb7f41da96` |

Đây là pin tái lập cục bộ từ lần tải ngày 2026-10-19, không phải checksum độc lập do publisher công bố. `data/*/provenance.json` ghi source URLs, thời gian cài, archive record và member/file hashes. ZIP, dataset và run artifacts đều được ignore.

NLTK `punkt`/`punkt_tab` được tải vào `.venvs/evaluator/nltk_data`, tương ứng runtime evaluator đã khóa. Không tải CoreNLP, GloVe hay embedding weights trong Phase 3.

### Smoke đã chạy

```bash
uv run --locked python scripts/setup_data.py
uv run --locked test2sql prepare --method all --indices 0 2 100 --run-id phase3-verified
uv run --locked test2sql prepare --method few-shot --indices 0 2 100 --run-id phase3-subset-repeat
uv run --locked test2sql check-evaluator --run-id phase3-verified --timeout 120
uv run --locked test2sql doctor --json
```

Hai run có cùng subset/checksum, ID và thứ tự: `spider-dev-0000`, `spider-dev-0002`, `spider-dev-0100`; thuộc 2 database. Input ba method và gold có cùng mapping. Kiểm tra bằng SHA256 xác nhận shared datasets và cả bốn source checkouts không đổi.

| Prediction kiểm soát | Count | Test-suite execution | Exact set match |
| --- | --- | --- | --- |
| Gold-as-prediction | 3 | 1.000 | 1.000 |
| SQL hợp lệ SQLite, sai kết quả | 3 | 0.000 | 0.000 |
| SQL lỗi cú pháp | 3 | 0.000 | 0.000 |

Ngoài ba smoke cases, đã chấm JSONL gold đảo thứ tự: wrapper map lại bằng ID và đạt 1.000/1.000. Prediction thiếu bị chặn trước subprocess; không tạo thư mục evaluation label đó. Đây là kiểm chứng harness, chưa phải kết quả model. Raw logs và result nằm trong `results/runs/phase3-verified/evaluation/`; [evidence trong repo](evidence/03-dataset-evaluator.json) ghi metrics, checksum, revision, flags và đường dẫn log.

29 tests đạt, gồm live evaluator smoke trên SQLite synthetic, mapping/staging, archive/provenance/checksum, thiếu variant, thiếu/thừa/trùng/sai ID, blank SQL, parsing count và timeout/nonzero/incomplete output. `ruff check .` và `ruff format --check .` đạt. `doctor` exit 0 với cảnh báo runtime/tài nguyên DAIL; doctor không chứng minh inference chạy được.

### Chính sách metric

Dùng evaluator revision `e97acc546ecbee8fa27fa8dbf025ef61493a876c`, `--etype all --keep_distinct`, **không `--plug_value`**. Execution dùng đủ test suites đã xác minh. Exact set match theo upstream vẫn bỏ qua values/DISTINCT, không phải exact string match. Mẫu thiếu/rỗng bị validation chặn; SQL lỗi thực thi giữ trong mẫu số và nhận 0. Score giữ độ chính xác 3 số thập phân mà stdout upstream cung cấp.

Bàn giao Phase 4: chạy DIN-SQL thật trên subset nhỏ qua CLI chính, lưu raw output và chuẩn hóa prediction theo mapping đã tạo. Phase 3 chưa gọi LLM, chạy DAIL preprocessing hay inference của bất kỳ method nào.

## Vấn đề còn lại

- DAIL còn cần Java/CoreNLP, GloVe và embedding resources trước preprocessing/generation ở Phase 5.
- `train_gold.sql` chính thức khác JSON train ở một số literal/tab; giữ cả hai nguồn nguyên trạng và không dùng train gold để chấm dev subset.
- Smoke 3 mẫu xác nhận luồng và mẫu số, chưa thay thế validation full dev hoặc benchmark model.
- Chưa xác minh trên Linux/máy benchmark đích; timeout process group đã kiểm tra trên macOS POSIX.
