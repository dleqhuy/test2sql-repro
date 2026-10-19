# Môi trường Python riêng bằng uv

Mỗi thư mục ở đây là một **uv project độc lập**, không phải thành viên uv workspace. Mỗi project có `pyproject.toml`, `.python-version` và `uv.lock`; requirements của các method không được gom vào project root.

## Cấu trúc và cách dùng

| Thành phần | Python minor | Project / lockfile | Venv do script tạo |
| --- | --- | --- | --- |
| Repo chính | 3.10 | Root repo | `.venv/` |
| Few-shot/DIN-SQL | 3.10 | `environments/few-shot/` | `.venvs/few-shot/` |
| MAC-SQL | 3.9 | `environments/mac-sql/` | `.venvs/mac-sql/` |
| DAIL-SQL | 3.8 | `environments/dail-sql/` | `.venvs/dail-sql/` |
| Evaluator | 3.10 | `environments/evaluator/` | `.venvs/evaluator/` |

`requires-python` giới hạn đúng minor; `.python-version` chọn minor đó. Patch Python thực tế được ghi trong evidence kiểm tra, không cố định bởi `uv.lock` (lockfile khóa dependencies). Không thay Python hệ thống hoặc dùng chung site-packages. Python 3.8/3.9 được giữ để tương thích code nghiên cứu tại revision khảo sát; đây không phải lựa chọn mặc định cho code mới.

Chạy từ root repo:

```bash
uv sync --locked
uv run --locked python scripts/setup_environments.py
uv run --locked python scripts/setup_environments.py --method few-shot
uv run --locked python scripts/setup_environments.py --method evaluator --dry-run
```

`--method all` là mặc định. Cài đặt dùng `uv sync --locked --no-dev` trên từng project, không tự thay lockfile. Script cố định `UV_PROJECT_ENVIRONMENT` thành đường dẫn tuyệt đối tương ứng trong `.venvs/`, bỏ `VIRTUAL_ENV` kế thừa và yêu cầu `--managed-python`; do đó không cài nhầm vào venv đang activate. Nếu một môi trường lỗi, script tiếp tục những môi trường còn lại và kết thúc khác 0, liệt kê môi trường lỗi. `--dry-run` không cài packages nhưng uv vẫn có thể đọc/tải metadata hoặc interpreter cần thiết.

Khi chạy method, gọi executable của venv tương ứng và truyền cwd/env theo contract, ví dụ sau khi source đã được chuẩn bị:

```bash
.venvs/mac-sql/bin/python external/mac-sql/run.py --help
.venvs/dail-sql/bin/python external/dail-sql/ask_llm.py --help
.venvs/evaluator/bin/python external/test-suite-sql-eval/evaluation.py --help
```

Không có `test2sql run` ở giai đoạn này. Chưa thêm submodules vào repo; `external/` trong ví dụ là đường dẫn sẽ được tạo trong phần bootstrap source. Không chạy `uv run` ngay trong checkout con vì uv có thể tìm nhầm project root; cũng không gọi `uv sync --project environments/...` trực tiếp mà quên đặt `UV_PROJECT_ENVIRONMENT`, nếu muốn giữ đúng layout `.venvs/`.

## Nguồn dependencies và chính sách pin

[manifest.json](manifest.json) ghi repository, revision, Python, project và đường dẫn môi trường cho từng thành phần. Revision khớp [contract Phase 1](../docs/method-contracts.md). Không sửa source/requirements upstream, không cài upstream như một editable package.

- **DIN-SQL:** giữ tất cả requirements đang hoạt động trong `requirements.txt` tại commit đã khảo sát, gồm các gói không trực tiếp dùng trong Spider entry point. Dependencies bắc cầu được uv khóa trong lockfile.
- **MAC-SQL:** giữ requirements đang hoạt động, bỏ dòng comment `transformers`; khóa phiên bản thực resolve trong lockfile.
- **DAIL-SQL:** giữ requirements nhưng giới hạn một số gói chưa pin để tránh tự ghép các đời thư viện không tương thích. Chọn `torch==1.13.1` + `torchtext==0.14.1`, `transformers==4.26.1`, `sentence-transformers==2.2.2`, thêm `huggingface-hub==0.12.1`, `numpy<2`. Thêm `networkx==3.1` vì `utils/datasets/spider.py` import gói này nhưng requirements upstream bỏ sót. Các phiên bản này cũng phù hợp bộ thư viện cùng thời với DIN-SQL. Đây là quyết định của môi trường repo chính; không tuyên bố upstream đã cung cấp các pins này. Các imports và full help được kiểm tra riêng, chưa phải kiểm chứng chất lượng method.
- **Evaluator:** không có requirements upstream; khai báo từ imports thực tế: `nltk`, `sqlparse`, `tqdm`; uv khóa các phiên bản cụ thể.

Đổi dependencies có chủ ý bằng cách sửa project của đúng method rồi tạo lại lockfile:

```bash
uv run --locked python scripts/setup_environments.py --method dail-sql --lock
uv run --locked python scripts/setup_environments.py --method dail-sql
```

`uv lock` giữ những phiên bản đang khóa khi có thể; không tự nâng tất cả dependencies. Review diff của cả `pyproject.toml` và `uv.lock`, chạy lại kiểm tra rồi cập nhật evidence/docs. Không sửa lockfile thủ công hoặc dùng `uv pip install` thêm gói vào môi trường đã khóa để che lỗi; lần sync sau có thể xóa các gói đó.

## Tài nguyên bên ngoài môi trường

Cài venv không cung cấp Spider, database, API credentials, NLTK data, CoreNLP/Java, GloVe hoặc embedding weights. Đặt các tài nguyên/cache ngoài source checkout; truyền `CORENLP_HOME`, `CACHE_DIR`, `NLTK_DATA` và cache Hugging Face theo vị trí thực tế khi chạy.

DAIL đọc `stopwords` ngay khi import code linking, nên preprocess/generate cần tài nguyên NLTK kể cả khi gọi `--help`. Sau khi setup venv, tải vào chính venv đó để không ảnh hưởng các môi trường khác:

```bash
.venvs/dail-sql/bin/python -m nltk.downloader \
  -d .venvs/dail-sql/nltk_data stopwords punkt punkt_tab
```

NLTK tự tìm `<venv>/nltk_data`; không cần biến môi trường khi dùng vị trí này. Lệnh tải chỉ thực hiện khi người dùng chạy riêng, không nằm trong script setup dependencies. Trên máy khảo sát đã tải ba tài nguyên này, lưu SHA-256 các file ZIP trong evidence. Với MAC/evaluator, tải tokenizer phù hợp phiên bản NLTK vào venv tương ứng khi kiểm chứng trên dataset ở Phase 3.

Source method có thể gọi LLM ngay khi khởi tạo runner (MAC có request ping), nên kiểm tra môi trường ở bước này chỉ import dependencies và gọi những CLI có help. DIN không hỗ trợ `--help`; kiểm tra bằng import và các provider tests phù hợp, không gọi `DIN-SQL.py` để thử help.

## Kết quả kiểm tra

Đã cài thành công bằng **uv 0.12.19** trên **macOS ARM64**, ngày 2026-10-19:

| Môi trường | Python thực cài | Imports | Full CLI help | `uv pip check` |
| --- | --- | --- | --- | --- |
| DIN-SQL | 3.10.21 | Pass, gồm pandas/OpenAI/LangChain/datasets/SentenceTransformers | Không hỗ trợ help, không chạy entry point | Cảnh báo metadata Torch |
| MAC-SQL | 3.9.25 | Pass | `run.py --help` pass | Pass |
| DAIL-SQL | 3.8.20 | Pass, gồm Torch/torchtext/SentenceTransformers/CoreNLP | Preprocess/generate/ask help pass sau khi cài NLTK data | Cảnh báo metadata Torch |
| Evaluator | 3.10.21 | Pass | `evaluation.py --help` pass | Pass |

**Cảnh báo thực tế:** wheel Torch 1.13.1 cho ARM64 chứa `WHEEL` tag x86_64. `uv pip check` exit 1 vì metadata nền tảng trong DIN/DAIL; `file` xác nhận extension là ARM64 và import thành công. Không sửa wheel/metadata trong venv để che cảnh báo. Lần `uv sync` sau có thể cài lại cùng Torch do tag sai; `--dry-run` đã thể hiện việc này. Đây là giới hạn package upstream tại revision đang giữ, cần ghi nhận khi kiểm tra reproducibility.

Xem [evidence môi trường](../docs/phases/evidence/02-environments.json) và [tiến độ Phase 2](../docs/phases/02-bootstrap.md). Evidence ghi phiên bản, SHA lockfile, imports, command và lỗi; không ghi environment đầy đủ hoặc API key. Kết quả help DAIL trong evidence là sau khi bổ sung networkx và tải NLTK data; ghi chú setup giải thích các yêu cầu này. Không có model weights, Spider, CoreNLP Java server hoặc LLM inference được chạy. Kết quả trên máy này không chứng minh lockfile cài thành công trên mọi hệ điều hành; cần kiểm tra lại trên máy benchmark đích.
