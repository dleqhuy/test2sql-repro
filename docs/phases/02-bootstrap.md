# Phase 2 — Dựng repo chính và môi trường

[Tổng quan](../integration-plan.md) · [Contract các method](../method-contracts.md)

**Trạng thái:** Đang thực hiện — đã dựng môi trường uv riêng; còn submodules và CLI.

**Phụ thuộc:** [Phase 1](01-audit.md).

**Mục tiêu:** Dựng nền tảng CLI, cấu hình và môi trường để gọi các repo con.

**Công việc:**

- [x] Thêm uv project/lockfile cho repo chính và từng method/evaluator.
- [x] Tạo venv riêng theo Python đã khảo sát, cài dependencies bằng uv.
- [x] Thêm script setup dùng `--locked`, tùy chọn từng method và dry-run cài đặt.
- [x] Cấu hình Ruff format/lint, loại trừ checkout con và môi trường.

- [ ] Thêm submodules và pin commit đã khảo sát.
- [ ] Tạo package CLI tối thiểu với `doctor` và `run --dry-run`.
- [ ] Thêm config đường dẫn, Python executable và `.env.example`.
- [ ] Kiểm tra repo, dependencies, dataset và biến môi trường bắt buộc.
- [ ] `--dry-run` hiển thị command, working directory và đường dẫn output, che credentials.
- [x] Bỏ qua `.venv/`, `.venvs/` và Ruff cache; `.env` đã được ignore.
- [ ] Hoàn thiện `.gitignore` cho dataset và run artifacts khi thêm các thành phần này.

**Đầu ra:** skeleton repo chính, config mẫu và kiểm tra môi trường.

**Tiêu chí hoàn thành:** máy mới có thể cài repo chính, khởi tạo submodules, kiểm tra cấu hình và xem command sắp chạy mà chưa gọi LLM.

## File/module dự kiến thay đổi

Đường dẫn dưới đây là dự kiến, điều chỉnh theo contract đã xác minh.

- `.gitmodules`, `external/`: submodules được pin.
- `pyproject.toml`, `src/test2sql/cli.py`, `src/test2sql/config.py`: package, CLI và config.
- `configs/`, `.env.example`, `.gitignore`: cấu hình và quy tắc bỏ qua artifacts.

## Cách kiểm tra

- [ ] Cài package và khởi tạo submodules theo hướng dẫn setup.
- [ ] Chạy doctor với cấu hình hợp lệ và cấu hình thiếu thành phần; kiểm tra thông báo cụ thể.
- [ ] Chạy dry-run; xác nhận không gọi LLM, không tạo prediction và không lộ credentials.

## Kết quả thực tế và bàn giao

Ngày 2026-10-19 đã thêm:

- Root `pyproject.toml`, `.python-version`, `uv.lock`: Python 3.10, Ruff đã pin, chưa đóng gói CLI.
- `environments/{few-shot,mac-sql,dail-sql,evaluator}/`: bốn project và lockfile độc lập, Python lần lượt 3.10/3.9/3.8/3.10. [manifest](../../environments/manifest.json) ghi source revision và venv path.
- `scripts/setup_environments.py`: cài vào `.venvs/<method>` bằng `uv sync --locked --no-dev --managed-python`; không thay source repo con. `--lock` phục vụ cập nhật có chủ ý; `--dry-run` ở script này chỉ preview cài dependencies, khác dry-run benchmark chưa triển khai.
- [README](../../README.md) và [hướng dẫn môi trường](../../environments/README.md): cách setup, gọi Python riêng, format/lint, nguồn requirements và tài nguyên cần tải riêng.

Dùng uv 0.12.19 trên macOS ARM64: đã tạo và cài `.venv/` cùng bốn venv method/evaluator. Python do uv quản lý được cài tại `.venvs/.python/` trên máy khảo sát bằng `UV_PYTHON_INSTALL_DIR`; cache dùng `/tmp/test2sql-uv-cache`. Đây là đường dẫn cục bộ phục vụ sandbox, không hard-code vào script; người dùng có thể dùng vị trí managed Python mặc định của uv.

[Bằng chứng kiểm tra runtime](evidence/02-environments.json) ghi phiên bản Python/packages, SHA lockfile, consistency check, imports và full help trên các checkout tạm của Phase 1. Không gọi LLM, không tải dataset/model weights, không chạy benchmark. Kết quả và cảnh báo cụ thể xem [hướng dẫn môi trường](../../environments/README.md#kết-quả-kiểm-tra).

Source method vẫn ở các checkout khảo sát `/tmp/test2sql-phase1-audit/`, không bị sửa. Chưa thêm submodules và chưa triển khai `test2sql doctor`/`test2sql run --dry-run`, nên Phase 2 chưa đạt toàn bộ tiêu chí hoàn thành.

## Vấn đề còn lại

- Torch 1.13.1 ARM64 chứa wheel metadata gắn nhãn x86_64: uv consistency check báo cảnh báo nền tảng và sync có thể cài lại Torch. File binary thực tế là ARM64, import được; giữ nguyên package đã pin, không sửa metadata trong venv để che cảnh báo.
- Cần phần bootstrap submodules, package CLI/config/.env.example và doctor/dry-run benchmark.
- Đã tải stopwords/punkt/punkt_tab vào venv DAIL để kiểm tra CLI. Java/CoreNLP, GloVe, embedding weights, NLTK data cho các môi trường khác và dataset/databases chưa được setup; imports/help không thay thế inference/preprocessing/evaluation thật.
- Chưa xác nhận cài đặt trên Linux hoặc máy benchmark đích.
