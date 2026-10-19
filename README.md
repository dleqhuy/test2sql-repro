# test2sql-repro

Repo tái lập và so sánh Few-shot/DIN-SQL, MAC-SQL và DAIL-SQL trên Spider. Đã hoàn thành Phase 1–3: submodules được pin, môi trường uv riêng, subset Spider và evaluator đã kiểm chứng. CLI hỗ trợ diagnostics, dry-run, chuẩn bị input và đánh giá prediction có sẵn; inference được triển khai ở Phase 4–5.

## Setup với uv

Cài [uv](https://docs.astral.sh/uv/getting-started/installation/), rồi chạy từ root repo:

```bash
git submodule update --init --recursive
uv sync --locked
uv run --locked python scripts/setup_environments.py
```

`uv sync` tạo `.venv/` cho công cụ repo chính. Script setup dùng bốn uv project/lockfile độc lập để tạo `.venvs/few-shot`, `.venvs/mac-sql`, `.venvs/dail-sql`, `.venvs/evaluator`. Script yêu cầu Python do uv quản lý và có thể tự tải Python đúng phiên bản; không cần activate venv. Dependencies/Python được tải từ mạng trong lần cài đầu.

Chỉ cài một môi trường, hoặc xem trước thao tác cài:

```bash
uv run --locked python scripts/setup_environments.py --method mac-sql
uv run --locked python scripts/setup_environments.py --method dail-sql --dry-run
```

Sau khi setup, orchestrator sẽ gọi Python riêng của từng method, ví dụ `.venvs/mac-sql/bin/python`. Source checkout, Spider, test-suite databases, CoreNLP, GloVe/model weights và NLTK data được chuẩn bị riêng theo [hướng dẫn môi trường](environments/README.md) và [contract](docs/method-contracts.md). Setup môi trường không gọi LLM, không đọc `.env`, không tải dataset và không sửa source repo con. DAIL còn cần [bước tải NLTK data](environments/README.md#tài-nguyên-bên-ngoài-môi-trường) để chạy preprocess/generate, kể cả help.

## Cấu hình và CLI

Tạo `.env` từ `.env.example` nếu chưa có, rồi điền `LLM_API_KEY`, endpoint và model. Giữ `.env` hiện có nếu đã cấu hình. Environment được export có ưu tiên cao hơn `.env`; không nội suy `${...}` trong `.env`. Không đưa key vào command line.

```bash
uv run --locked test2sql doctor
uv run --locked test2sql doctor --method few-shot --json
uv run --locked test2sql run --method few-shot --split dev --limit 3 --dry-run
uv run --locked test2sql run --method all --split dev --limit 3 --run-id preview --dry-run --json
```

`doctor` kiểm tra biến LLM, revision/checkout, entry points, Python, phiên bản runtime dependencies theo lockfile và platform, JSON Spider/schema và sự hiện diện SQLite databases. Exit code: `0` khi các check bắt buộc đạt, `1` khi thiếu/sai prerequisite; cảnh báo ghi rõ phần chưa xác minh. Không gọi endpoint hay import entry point method. Metadata dependency đạt không thay thế kiểm tra imports, NLTK/CoreNLP/model weights hoặc inference. Khi chưa tải dataset, doctor trả `1` và chỉ rõ file cần chuẩn bị ở Phase 3. Test-suite provenance và evaluation chưa được xác nhận chỉ bằng file tồn tại.

Dry-run chỉ dựng kế hoạch và có thể dùng trước khi tải dữ liệu: hiển thị argv, cwd, output và environment đã che key/credentials trong URL. Không tạo thư mục run, subset, log hay prediction; không chạy subprocess. `--limit` trong dry-run mô tả subset dự kiến; lệnh `prepare` bên dưới mới stage dữ liệu. DAIL preview gồm preprocess và hai lượt generate/ask, `--n 1`, giữ model từ environment. Chạy `run` không có `--dry-run` trả lỗi rõ ràng; chưa hỗ trợ inference/resume/report. Lệnh `evaluate` cho prediction có sẵn được mô tả bên dưới.

Đường dẫn cấu hình trong [configs/default.yaml](configs/default.yaml) được tính từ `root` (tương đối với file YAML), không phụ thuộc working directory. [configs/methods.yaml](configs/methods.yaml) chỉ rõ checkout/Python riêng. `SPIDER_DATA_DIR`, `TEST_SUITE_DB_DIR`, `EVALUATOR_DIR`, `OUTPUT_DIR` có thể override bằng environment hoặc `.env`; các path tương đối cũng tính từ root. Truyền `--config PATH` trước hoặc sau subcommand khi dùng file khác. Chỉ hỗ trợ Spider `dev`; `--run-id` phải là tên đơn, không ghi đè run cũ.

Các SHA chuẩn nằm trong [environments/manifest.json](environments/manifest.json), khớp Git submodule pointers. Sau clone có thể dùng `git submodule status` để đối chiếu. Không chạy `git submodule update --remote` khi tái lập benchmark. Dataset và `results/` được ignore; không commit các artifacts local.

## Dữ liệu Spider và kiểm chứng evaluator

Tải từ các link chính thức được ghi trong [Phase 3](docs/phases/03-dataset-evaluator.md), cài vào hai thư mục riêng trong `data/`:

```bash
uv run --locked python scripts/setup_data.py --download
.venvs/evaluator/bin/python -B -m nltk.downloader -d .venvs/evaluator/nltk_data punkt punkt_tab
```

Script cần `curl` khi tải. Có thể tải ZIP thủ công rồi đặt `spider_data.zip` và `testsuitedatabases.zip` trong `data/downloads/`, sau đó chạy không có `--download`. Dùng `--archive-dir PATH` cho vị trí khác, hoặc `--kind spider`/`--kind test-suite` để cài riêng; test-suite cần Spider dev đã cài trước. ZIP được đối chiếu SHA256 đã khảo sát trong source; nguồn tải, checksum archive và từng file được ghi ở `provenance.json`. Đây là checksum quan sát tại lần tải chính thức, không phải chữ ký/checksum do tác giả công bố. Nếu bản phát hành chính thức đổi, cần xác minh rồi cập nhật pin có chủ ý.

Spider cài đủ 166 database và các JSON/gold files. Từ archive test-suite chứa nhiều benchmark, script chỉ cài 20 database thuộc Spider dev và toàn bộ 695 file SQLite tương ứng. Tổng ZIP khoảng 1,47 GB; cần thêm vài GB cho dữ liệu giải nén và các bản sao run. Thư mục đã có được kiểm tra checksum, không ghi đè. `setup_data` không cần API key và không gọi LLM. Tokenizer evaluator được cài riêng; có thể override `NLTK_DATA` bằng đường dẫn tương đối root hoặc danh sách đường dẫn phân cách bởi `:` trên macOS/Linux.

```bash
# Mặc định chọn 3 mẫu đầu; mọi method nhận cùng subset và thứ tự
uv run --locked test2sql prepare --method all --limit 3 --run-id smoke-dev
uv run --locked test2sql check-evaluator --run-id smoke-dev --timeout 120

# Chọn các chỉ số nguồn cụ thể, giữ đúng thứ tự đã truyền
uv run --locked test2sql prepare --method all --indices 0 2 100 --run-id selected-dev
uv run --locked test2sql check-evaluator --run-id selected-dev
```

`prepare` lưu `subset.json`, `manifest.json`, gold SQL, schema đầy đủ và input riêng từng method. ID là `spider-dev-<source_index>` với ít nhất 4 chữ số. MAC nhận `question_id=0..N-1`; mapping nguồn vẫn trong subset. DAIL có dataset/database bản sao, train đầy đủ và merged JSON, source links riêng; chưa chạy CoreNLP, embedding retrieval hay LLM. `--limit` và `--indices` loại trừ nhau, run cũ không bị ghi đè. Có thể stage riêng `--method few-shot` để tránh sao chép database; smoke ba trường hợp cần input database từ `--method all`, `mac-sql` hoặc `dail-sql`.

`check-evaluator` tạo ba bộ prediction có kiểm soát: gold, SQL hợp lệ SQLite nhưng sai kết quả, và SQL lỗi cú pháp. Lệnh đạt khi gold có execution/exact = 1, SQL sai và SQL lỗi có execution = 0, SQL lỗi có exact = 0. Kết quả này kiểm chứng bộ chấm, chưa phải benchmark model.

Để chấm prediction đã có:

```bash
uv run --locked test2sql evaluate --run-id smoke-dev \
  --predictions results/runs/smoke-dev/evaluation/smoke-inputs/gold.sql \
  --label gold-again --timeout 120
```

Prediction text phải có đúng N dòng SQL không rỗng, không tab và theo thứ tự subset. JSONL chuẩn hóa cần `example_id`, `source_index`, `db_id`, `run_id`, `status: success`, `predicted_sql`; wrapper kiểm tra ID/mapping và sắp về thứ tự subset. Prediction thiếu/thừa/trùng, SQL rỗng hoặc status lỗi bị chặn trước subprocess, không bị loại khỏi mẫu số. SQL lỗi cú pháp nhưng không rỗng được đưa vào evaluator và tính là sai.

Mặc định dùng test suites có provenance đúng và đủ toàn bộ variants đã ghi nhận; không tự fallback sang database gốc. `--database-mode spider` dùng riêng để smoke/debug execution trên database gốc, và result ghi nhãn metric khác. Evaluator chạy trên bản sao database riêng cho từng label, với `--etype all --keep_distinct`, không `--plug_value`. Exact set match vẫn theo upstream bỏ qua values/DISTINCT; score stdout được làm tròn 3 chữ số.

Mỗi lần chấm giữ `raw-predictions.*`, `pred.sql`, gold/schema, database copies, `stdout.log`, `stderr.log`, `result.json` trong `evaluation/<label>/`. Result lưu flags, revision, lock SHA, database checksums, count và exit code. Timeout toàn subprocess/process group (POSIX), exit code lỗi, output thiếu metrics hoặc sai count đều cho status failed và `metrics: null`; log được giữ lại. Không dùng lại label đã có.

## Kiểm tra bootstrap

```bash
uv run --locked python -m unittest discover -s tests -v
```

29 tests kiểm tra staging/mapping/provenance, prediction validation, parser metrics, timeout/nonzero exit, smoke evaluator thật trên SQLite synthetic, cùng config/environment precedence, doctor thành công trên fixture và lỗi prerequisite, marker/extra dependencies, command contracts, redaction, Python symlink trong venv và dry-run không có tác dụng phụ. Chúng không gọi LLM. [Bằng chứng Phase 2](docs/phases/evidence/02-bootstrap.json) giữ kết quả lịch sử trước khi tải dataset. [Bằng chứng Phase 3](docs/phases/evidence/03-dataset-evaluator.json) ghi smoke trên Spider/test suites thật; doctor hiện đạt các prerequisite bắt buộc, còn cảnh báo tài nguyên DAIL chưa xác minh. Live smoke test synthetic tự skip nếu chưa có evaluator venv hoặc tokenizer; các kiểm tra mapping còn lại cần submodules đã init.

## Format và lint

```bash
uv run --locked ruff format .
uv run --locked ruff check .
# Dùng trong CI, không sửa file:
uv run --locked ruff format --check .
```

Ruff loại trừ `external/` và `.venvs/`. Commit `pyproject.toml`, `.python-version`, các `uv.lock` và cấu hình môi trường; không commit `.venv/`, `.venvs/` hoặc credentials.

## Tiến độ

- [Kế hoạch tích hợp](docs/integration-plan.md)
- [Khảo sát Phase 1](docs/phases/01-audit.md)
- [Phase 2: bootstrap và môi trường](docs/phases/02-bootstrap.md)
- [Phase 3: dữ liệu và evaluator](docs/phases/03-dataset-evaluator.md)
- [Contract và revision của các method](docs/method-contracts.md)
