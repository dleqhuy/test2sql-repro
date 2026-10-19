# test2sql-repro

Repo tái lập và so sánh Few-shot/DIN-SQL, MAC-SQL và DAIL-SQL trên Spider. Hiện đã hoàn thành khảo sát Phase 1 và dựng môi trường uv riêng; CLI benchmark `test2sql` chưa được triển khai.

## Setup với uv

Cài [uv](https://docs.astral.sh/uv/getting-started/installation/), rồi chạy từ root repo:

```bash
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
