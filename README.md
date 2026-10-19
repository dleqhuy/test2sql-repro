# test2sql-repro

Repo tái lập và so sánh Few-shot/DIN-SQL, MAC-SQL và DAIL-SQL trên Spider. Đã hoàn thành Phase 1–2: submodules được pin, môi trường uv riêng, CLI `doctor` và `run --dry-run`. Chuẩn bị dữ liệu, inference và evaluation được triển khai ở các phase tiếp theo.

## Setup với uv

Cài [uv](https://docs.astral.sh/uv/getting-started/installation/), rồi chạy từ root repo:

```bash
git submodule update --init --recursive
uv sync --locked
uv run --locked python scripts/setup_environments.py
```

Lệnh đầu tạo `.venv/` cho công cụ repo chính. Lệnh sau dùng bốn uv project/lockfile độc lập để tạo `.venvs/few-shot`, `.venvs/mac-sql`, `.venvs/dail-sql`, `.venvs/evaluator`. Script yêu cầu Python do uv quản lý và có thể tự tải Python đúng phiên bản; không cần activate venv. Dependencies/Python được tải từ mạng trong lần cài đầu.

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

Dry-run chỉ dựng kế hoạch và có thể dùng trước khi tải dữ liệu: hiển thị argv, cwd, output và environment đã che key/credentials trong URL. Không tạo thư mục run, subset, log hay prediction; không chạy subprocess. `--limit` mô tả subset sẽ stage ở Phase 3, chưa lọc dữ liệu trong Phase 2. DAIL preview gồm preprocess và hai lượt generate/ask, `--n 1`, giữ model từ environment. Chạy `run` không có `--dry-run` trả lỗi rõ ràng; chưa hỗ trợ inference/resume/evaluate/report.

Đường dẫn cấu hình trong [configs/default.yaml](configs/default.yaml) được tính từ `root` (tương đối với file YAML), không phụ thuộc working directory. [configs/methods.yaml](configs/methods.yaml) chỉ rõ checkout/Python riêng. `SPIDER_DATA_DIR`, `TEST_SUITE_DB_DIR`, `EVALUATOR_DIR`, `OUTPUT_DIR` có thể override bằng environment hoặc `.env`; các path tương đối cũng tính từ root. Truyền `--config PATH` trước hoặc sau subcommand khi dùng file khác. Chỉ hỗ trợ Spider `dev`; `--run-id` phải là tên đơn, không ghi đè run cũ.

Các SHA chuẩn nằm trong [environments/manifest.json](environments/manifest.json), khớp Git submodule pointers. Sau clone có thể dùng `git submodule status` để đối chiếu. Không chạy `git submodule update --remote` khi tái lập benchmark. Dataset và `results/` được ignore; không commit các artifacts local.

## Kiểm tra bootstrap

```bash
uv run --locked python -m unittest discover -s tests -v
```

Tests kiểm tra config/environment precedence, doctor thành công trên fixture và lỗi prerequisite, marker/extra dependencies, command contracts, redaction, Python symlink trong venv và dry-run không có tác dụng phụ. Chúng không gọi LLM. [Bằng chứng Phase 2](docs/phases/evidence/02-bootstrap.json) ghi kiểm tra trên workspace thật; dataset chưa có nên doctor hiện trả `1`.

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
- [Contract và revision của các method](docs/method-contracts.md)
