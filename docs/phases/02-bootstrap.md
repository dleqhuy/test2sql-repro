# Phase 2 — Dựng repo chính và môi trường

[Tổng quan](../integration-plan.md) · [Contract các method](../method-contracts.md)

**Trạng thái:** Hoàn thành — submodules, môi trường, CLI/config và diagnostics đã được kiểm tra.

**Phụ thuộc:** [Phase 1](01-audit.md).

**Mục tiêu:** Dựng nền tảng CLI, cấu hình và môi trường để gọi các repo con.

**Công việc:**

- [x] Thêm uv project/lockfile cho repo chính và từng method/evaluator.
- [x] Tạo venv riêng theo Python đã khảo sát, cài dependencies bằng uv.
- [x] Thêm script setup dùng `--locked`, tùy chọn từng method và dry-run cài đặt.
- [x] Cấu hình Ruff format/lint, loại trừ checkout con và môi trường.

- [x] Thêm submodules và pin commit đã khảo sát.
- [x] Tạo package CLI tối thiểu với `doctor` và `run --dry-run`.
- [x] Thêm config đường dẫn, Python executable và `.env.example`.
- [x] Kiểm tra repo, dependencies, dataset và biến môi trường bắt buộc.
- [x] `--dry-run` hiển thị command, working directory và đường dẫn output, che credentials.
- [x] Bỏ qua `.venv/`, `.venvs/` và Ruff cache; `.env` đã được ignore.
- [x] Hoàn thiện `.gitignore` cho dataset và run artifacts khi thêm các thành phần này.

**Đầu ra:** skeleton repo chính, config mẫu và kiểm tra môi trường.

**Tiêu chí hoàn thành:** máy mới có thể cài repo chính, khởi tạo submodules, kiểm tra cấu hình và xem command sắp chạy mà chưa gọi LLM.

## File/module dự kiến thay đổi

Đường dẫn dưới đây là dự kiến, điều chỉnh theo contract đã xác minh.

- `.gitmodules`, `external/`: submodules được pin.
- `pyproject.toml`, `src/test2sql/cli.py`, `src/test2sql/config.py`: package, CLI và config.
- `configs/`, `.env.example`, `.gitignore`: cấu hình và quy tắc bỏ qua artifacts.

## Cách kiểm tra

- [x] Cài package và khởi tạo submodules theo hướng dẫn setup.
- [x] Chạy doctor với cấu hình hợp lệ và cấu hình thiếu thành phần; kiểm tra thông báo cụ thể.
- [x] Chạy dry-run; xác nhận không gọi LLM, không tạo prediction và không lộ credentials.

## Kết quả thực tế và bàn giao

Ngày 2026-10-19 đã thêm:

- Root `pyproject.toml`, `.python-version`, `uv.lock`: Python 3.10, Ruff và dependencies cấu hình đã pin; package `src/test2sql` cung cấp console script.
- `environments/{few-shot,mac-sql,dail-sql,evaluator}/`: bốn project và lockfile độc lập, Python lần lượt 3.10/3.9/3.8/3.10. [manifest](../../environments/manifest.json) ghi source revision và venv path.
- `scripts/setup_environments.py`: cài vào `.venvs/<method>` bằng `uv sync --locked --no-dev --managed-python`; không thay source repo con. `--lock` phục vụ cập nhật có chủ ý; `--dry-run` ở script này chỉ preview cài dependencies, khác dry-run benchmark chỉ preview commands.
- [README](../../README.md) và [hướng dẫn môi trường](../../environments/README.md): cách setup, gọi Python riêng, format/lint, nguồn requirements và tài nguyên cần tải riêng.

Dùng uv 0.12.19 trên macOS ARM64: đã tạo và cài `.venv/` cùng bốn venv method/evaluator. Python do uv quản lý được cài tại `.venvs/.python/` trên máy khảo sát bằng `UV_PYTHON_INSTALL_DIR`; cache dùng `/tmp/test2sql-uv-cache`. Đây là đường dẫn cục bộ phục vụ sandbox, không hard-code vào script; người dùng có thể dùng vị trí managed Python mặc định của uv.

[Bằng chứng kiểm tra runtime](evidence/02-environments.json) ghi phiên bản Python/packages, SHA lockfile, consistency check, imports và full help trên các checkout tạm của Phase 1. Không gọi LLM, không tải dataset/model weights, không chạy benchmark. Kết quả và cảnh báo cụ thể xem [hướng dẫn môi trường](../../environments/README.md#kết-quả-kiểm-tra).

Phần bootstrap đã hoàn tất:

- Thêm bốn Git submodules trong `external/`, pin đúng SHA ở `environments/manifest.json`; `.gitmodules` dùng URL remote, không phụ thuộc checkout khảo sát tạm. Source các method giữ nguyên.
- Package CLI `test2sql doctor` và `test2sql run --dry-run`, có `--method`, `--config`, JSON output; run thêm `--split dev`, `--limit`, `--run-id`. Chưa chạy inference.
- `configs/default.yaml`, `configs/methods.yaml`, `.env.example`: resolve path từ root cấu hình, giữ Python path trong venv, environment ưu tiên hơn `.env`.
- Doctor kiểm tra repo/revision/dirty status, entry points, Python và runtime dependencies theo lockfile, gồm platform markers/extras; không yêu cầu package chỉ dành cho platform khác hoặc build isolation. Kiểm tra biến LLM và presence/format cơ bản của Spider/schema/database; không kết nối provider.
- Dry-run preview một command DIN, một MAC và năm stage DAIL. Không stage file, không chạy subprocess/LLM; che API key và loại userinfo/query/fragment khỏi URL hiển thị. Kiểm tra run ID, limit, run trùng và output nằm trong source/dataset.
- Dataset, results và các biến thể `.env` được ignore, ngoại trừ `.env.example`.

Kiểm tra bằng `uv sync --locked`, `uv run --locked python -m unittest discover -s tests -v` (**13 tests đạt**), `ruff check .`, `ruff format --check .`, doctor và dry-run trên checkout thật. Fixture kiểm chứng cả doctor thành công và lỗi thiếu/sai prerequisite. [Evidence bootstrap](evidence/02-bootstrap.json) ghi kết quả thực tế: cả bốn revision/checkout/Python/runtime package checks đạt; doctor exit 1 do chưa có Spider/test-suite data. Dry-run cả ba method exit 0, không tạo results và không thay source checkout. Không gọi LLM, không tải dữ liệu/model hoặc chạy evaluation.

Bàn giao Phase 3: stage subset/mapping/gold từ dataset thật, xác minh provenance test suites và chạy smoke evaluator. Command preview là template dành cho bước staging này, chưa phải artifacts sẵn để chạy thủ công.

## Vấn đề còn lại

- Torch 1.13.1 ARM64 chứa wheel metadata gắn nhãn x86_64: uv consistency check báo cảnh báo nền tảng và sync có thể cài lại Torch. File binary thực tế là ARM64, import được; giữ nguyên package đã pin, không sửa metadata trong venv để che cảnh báo.
- Đã tải stopwords/punkt/punkt_tab vào venv DAIL để kiểm tra CLI. Java/CoreNLP, GloVe, embedding weights, NLTK data cho các môi trường khác và dataset/databases chưa được setup; imports/help không thay thế inference/preprocessing/evaluation thật.
- Chưa xác nhận cài đặt trên Linux hoặc máy benchmark đích.
