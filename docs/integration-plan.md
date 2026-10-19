# Kế hoạch tích hợp các method NL2SQL vào test2sql-repro

## 1. Mục tiêu và phạm vi

`test2sql-repro` là repo chính, chịu trách nhiệm cung cấp CLI, chuẩn bị dữ liệu, gọi ba method, lưu predictions và đánh giá kết quả.

| Thành phần | Repository | Vai trò |
| --- | --- | --- |
| Repo chính | https://github.com/dleqhuy/test2sql-repro | Orchestration, cấu hình, quản lý run và report |
| Few-shot/DIN-SQL | https://github.com/dleqhuy/Few-shot-NL2SQL-with-prompting | Sinh SQL |
| MAC-SQL | https://github.com/dleqhuy/MAC-SQL | Sinh SQL |
| DAIL-SQL | https://github.com/dleqhuy/DAIL-SQL | Sinh SQL |
| Spider | https://github.com/taoyds/spider | Dataset và tài liệu về schema, splits |
| Test Suite SQL Eval | https://github.com/taoyds/test-suite-sql-eval | Đánh giá predictions độc lập |

Luồng thực thi mục tiêu:

```text
CLI repo chính
    → Chuẩn bị tập Spider dùng chung
    → Gọi CLI từng method qua subprocess
    → Lưu raw output và chuẩn hóa predictions
    → Gọi Test Suite SQL Eval
    → Xuất bảng so sánh
```

Phạm vi ban đầu là Spider dev, chạy tuần tự trên một tập nhỏ trước khi chạy toàn bộ split. Không triển khai web UI, distributed execution hoặc hệ thống experiment tracking trong MVP.

## 2. Trạng thái và những điểm cần xác nhận

- Tại thời điểm lập kế hoạch, workspace mới có `.gitignore`, chưa có implementation của orchestrator.
- Theo thông tin người dùng, ba fork đã được sửa để nhận cấu hình LLM qua environment.
- Đã khảo sát source và command của ba fork `dleqhuy` tại revision cụ thể ngày 2026-10-19; xem [contract và giới hạn runtime](method-contracts.md). Phase 1 đã hoàn thành ở mức kiểm tra source/parser, chưa chạy inference.
- README upstream của Few-shot/DIN-SQL có entry point `DIN-SQL.py --dataset ... --output ...`. Đây chỉ là tham khảo, không mặc định fork có cùng giao diện.
- Phase 2–3 đã triển khai `doctor`, `run --dry-run`, `prepare`, `check-evaluator` và `evaluate --predictions PATH`. Inference và report vẫn thuộc các phase sau.

## 3. Nguyên tắc tích hợp

1. Giữ nguyên source của các repo con. Adapter, config và xử lý output nằm trong repo chính.
2. Không copy implementation của method vào package orchestrator.
3. Dùng Git submodule cho ba method và evaluator, pin commit cụ thể. Không tự động pull hoặc đổi branch khi chạy benchmark.
4. Spider dataset và test-suite databases được tải riêng, không commit dữ liệu lớn vào repo chính. Clone repo Spider không thay thế bước tải dataset chính thức.
5. Mỗi method và evaluator có uv project/lockfile riêng, tạo venv riêng trong `.venvs/` theo Python đã khảo sát. Không dùng chung uv workspace; config chỉ rõ Python executable của từng method. Xem [hướng dẫn môi trường](../environments/README.md).
6. Gọi method qua subprocess bằng danh sách arguments, truyền working directory và environment rõ ràng.
7. Nếu method ghi file vào checkout, chuẩn bị thư mục chạy riêng bên ngoài checkout được pin. Không sửa source chỉ để đổi đường dẫn.
8. Lưu raw predictions trước khi đánh giá. Chạy inference và evaluation là hai bước độc lập.
9. Mọi method dùng cùng danh sách mẫu và thứ tự mẫu trong một thí nghiệm so sánh.
10. Giữ cấu hình đặc thù của từng method như prompt, demonstrations và retrieval; ghi lại để kết quả có thể được diễn giải.
11. Không ghi API key vào Git, logs, command hiển thị hoặc run manifest.

## 4. Cấu trúc repo mục tiêu

```text
test2sql-repro/
├── README.md
├── pyproject.toml
├── uv.lock
├── .python-version
├── environments/                # uv project + lockfile riêng cho từng method/evaluator
├── scripts/setup_environments.py
├── .env.example
├── .gitignore
├── .gitmodules
├── configs/
│   ├── default.yaml
│   └── methods.yaml
├── docs/
│   ├── integration-plan.md
│   ├── method-contracts.md
│   └── phases/                  # checklist và kết quả của từng phase
├── external/
│   ├── few-shot-nl2sql/
│   ├── mac-sql/
│   ├── dail-sql/
│   └── test-suite-sql-eval/
├── src/test2sql/
│   ├── cli.py
│   ├── config.py
│   ├── runner.py
│   ├── methods/
│   ├── datasets/
│   └── evaluation/
├── tests/
├── data/                         # ignored
│   ├── spider/
│   └── test-suite-databases/
├── .venv/                       # ignored: repo chính
├── .venvs/                      # ignored: các method/evaluator
└── results/                      # ignored
    └── runs/<run_id>/
        ├── manifest.json
        ├── subset.json
        ├── logs/
        ├── raw/
        ├── predictions/
        ├── evaluation/
        ├── summary.json
        └── summary.csv
```

Đây là layout mục tiêu. Chỉ tạo module khi phase tương ứng cần dùng, tránh xây dựng framework quá mức cho ba adapter.

## 5. Cấu hình LLM và runtime

`.env.example` dự kiến:

```dotenv
LLM_BASE_URL=http://localhost:20128/v1
LLM_API_KEY=
LLM_MODEL=cx/gpt-6-luna

SPIDER_DATA_DIR=./data/spider
TEST_SUITE_DB_DIR=./data/test-suite-databases
EVALUATOR_DIR=./external/test-suite-sql-eval
OUTPUT_DIR=./results
```

- Environment đã được người dùng thiết lập có ưu tiên cao hơn giá trị từ `.env`.
- Repo chính kiểm tra biến bắt buộc và truyền chúng xuống subprocess; không tạo thêm LLM client chung.
- Python executable, repo path và các tham số riêng của method nằm trong config. Cấu hình môi trường hiện có tại `environments/manifest.json`; setup bằng `uv run --locked python scripts/setup_environments.py`. Dependencies đã khóa trong từng `environments/<method>/uv.lock`; không sửa requirements upstream.
- Manifest chỉ lưu model và base URL đã loại credentials; không lưu API key hoặc toàn bộ environment.

## 6. Các phase triển khai và tiến độ

| Phase | Phạm vi | Phụ thuộc | Trạng thái |
| --- | --- | --- | --- |
| 1 | [Khảo sát và chốt contract](phases/01-audit.md) | — | Hoàn thành |
| 2 | [Dựng repo chính và môi trường](phases/02-bootstrap.md) | 1 | Hoàn thành |
| 3 | [Chuẩn bị Spider và kiểm tra evaluator](phases/03-dataset-evaluator.md) | 2 | Hoàn thành |
| 4 | [Chạy Few-shot/DIN-SQL qua CLI chính](phases/04-few-shot.md) | 3 | Chưa bắt đầu |
| 5 | [Tích hợp MAC-SQL và DAIL-SQL](phases/05-mac-dail.md) | 4 | Chưa bắt đầu |
| 6 | [Report và đánh giá lại](phases/06-reporting.md) | 5 | Chưa bắt đầu |
| 7 | [Hoàn thiện và chạy benchmark](phases/07-reproducibility.md) | 6 | Chưa bắt đầu |

**Mốc MVP:** hoàn thành Phase 5. Phase 6–7 hoàn thiện báo cáo và khả năng tái lập benchmark.

### Cách sử dụng kế hoạch

1. Trước khi implement, đọc nguyên tắc chung, file phase và [method-contracts.md](method-contracts.md).
2. Thực hiện checklist theo phụ thuộc; cập nhật kết quả và bằng chứng ngay trong file phase.
3. Cập nhật bảng tiến độ ở đây khi trạng thái phase thay đổi. Trạng thái dùng: Chưa bắt đầu, Đang thực hiện, Bị chặn, Hoàn thành.
4. Ghi contract đã xác minh tập trung trong `method-contracts.md`; các phase chỉ tham chiếu để tránh lặp và lệch thông tin.
5. Khi một phase cần dùng chức năng thuộc phase sau, chỉ triển khai phần tối thiểu cần cho tiêu chí hoàn thành và ghi rõ phần bàn giao.

## 7. CLI mục tiêu

Doctor/dry-run đã triển khai ở Phase 2; prepare/check-evaluator và evaluate với --predictions đã triển khai ở Phase 3. Các command inference/report và tự tìm prediction dưới đây là giao diện mục tiêu cho các phase sau:

```bash
# Kiểm tra môi trường
test2sql doctor

# Kiểm tra command trước khi chạy
test2sql run --method few-shot --split dev --limit 3 --dry-run

# Chạy method đầu tiên
test2sql run --method few-shot --split dev --limit 3

# Chạy cả ba method trên cùng subset
test2sql run --method all --split dev --limit 10

# Đánh giá và tổng hợp từ output đã lưu
test2sql evaluate --run-id <run_id> --predictions <prediction-file>
test2sql report --run-id <run_id>
```

Các option chung gồm `--config`, `--method`, `--split`, `--limit` và `--run-id` theo command phù hợp. `--resume` và `--skip-existing` được bổ sung khi semantics đã được xác minh, không hứa hỗ trợ trước cho mọi method.

## 8. Contract dữ liệu và run artifacts

Một prediction chuẩn hóa dự kiến:

```json
{
  "example_id": "spider-dev-0000",
  "source_index": 0,
  "db_id": "concert_singer",
  "predicted_sql": "SELECT COUNT(*) FROM singer",
  "method": "few-shot",
  "run_id": "example-run",
  "status": "success"
}
```

ID dựa trên split và chỉ số nguồn, đi kèm checksum dataset trong manifest. Không mặc định Spider đã cung cấp `example_id` theo format này. Nếu output method chỉ có SQL theo dòng, adapter phải xác nhận method giữ thứ tự trước khi gán ID.

Manifest cần lưu:

- Run ID, trạng thái tổng thể và trạng thái từng method.
- Thời gian bắt đầu/kết thúc, command, working directory và exit code.
- Main repo commit, submodule commits và trạng thái working tree liên quan.
- Split, checksum, danh sách/thứ tự mẫu và số mẫu yêu cầu.
- Model, base URL đã loại credentials, các tham số inference và cấu hình method.
- Môi trường Python cùng phiên bản dependencies hoặc lockfile tương ứng.
- Evaluator revision, database provenance/checksum và evaluation flags.
- Đường dẫn raw output, predictions, logs và metrics.

Giữ raw output riêng với output chuẩn hóa. Chuẩn hóa không được âm thầm sửa ý nghĩa SQL hoặc che mất lỗi của method.

## 9. Definition of Done

- [ ] Có hướng dẫn setup repo chính và submodules với revision được pin.
- [ ] Cấu hình LLM qua environment, không sửa source repo con.
- [ ] Kiểm tra được dependencies, Spider và test-suite databases.
- [ ] Chạy riêng từng method từ CLI repo chính.
- [ ] Chạy cả ba method trên cùng danh sách mẫu và thứ tự.
- [ ] Mỗi method có raw output, predictions, logs và trạng thái riêng.
- [ ] Phát hiện được prediction thiếu, thừa, trùng hoặc sai mapping.
- [ ] Đánh giá độc lập từ predictions đã lưu.
- [ ] Report ghi đúng metric, flags, mẫu số và trạng thái run.
- [ ] Lưu revisions, cấu hình và provenance của dataset/databases.
- [ ] Không lưu API key vào Git hoặc run artifacts.
- [ ] Source checkout của các repo con giữ nguyên sau khi chạy.
- [ ] Luồng chạy được kiểm tra theo README trên môi trường sạch.

## 10. Nguồn tham khảo

- [Few-shot/DIN-SQL upstream README](https://github.com/MohammadrezaPourreza/Few-shot-NL2SQL-with-prompting): tham khảo entry point ban đầu; không thay thế việc kiểm tra fork của người dùng.
- [Spider](https://github.com/taoyds/spider): schema, định dạng dữ liệu và liên kết tới dataset chính thức.
- [Test Suite SQL Eval](https://github.com/taoyds/test-suite-sql-eval): thiết lập test-suite databases, định dạng gold/prediction, evaluation modes và flags.

Trong evaluator này, `--etype exec` dùng cho test-suite accuracy khi cung cấp đúng bộ test suites; `match` dùng cho exact set match; `all` chạy cả hai. `--plug_value` và `--keep_distinct` phải được chốt và ghi lại để kết quả so sánh có cùng điều kiện.
