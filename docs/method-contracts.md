# Contract các method và evaluator

[Tổng quan](integration-plan.md) · [Phase 1 — Khảo sát](phases/01-audit.md)

## Phạm vi và mức xác minh

Khảo sát ngày **2026-10-19**, trên các checkout tạm độc lập; không sửa source repo con, không gọi LLM, không đọc `.env` của repo chính. Các SHA dưới đây đã được **pin thành Git submodules ở Phase 2** trong `external/`, khớp `environments/manifest.json`.

Đã đối chiếu source, requirements, README và CLI. Đã parse AST 57 file Python và chạy 5 probe parser lấy trực tiếp các câu lệnh argparse trong source. Đây là kiểm tra parser cô lập, **không phải chạy thành công toàn bộ entry point**. Sáu lần gọi `--help` đều dừng ở import do máy khảo sát thiếu dependencies. Trong audit Phase 1 chưa cài môi trường method hoặc chạy inference, preprocessing, resume thực tế hay benchmark evaluator. Môi trường được bổ sung ở bước tiếp theo, ghi riêng bên dưới. [Bằng chứng JSON](phases/evidence/01-audit.json) lưu SHA nguồn, command, exit code, lỗi và working-tree status; [script tái kiểm tra](phases/evidence/audit_phase1.py) không cần dependencies ngoài thư viện chuẩn.

## Cập nhật môi trường sau khảo sát

Đã thêm uv project/lockfile độc lập cho từng method và evaluator, cùng script tạo `.venvs/<method>`; xem [hướng dẫn môi trường](../environments/README.md) và [evidence runtime](phases/evidence/02-environments.json). Python được chọn: DIN 3.10, MAC 3.9, DAIL 3.8, evaluator 3.10. Các command dùng `$PY_*` dưới đây tương ứng Python trong những venv này.

Dependencies đã cài trên macOS ARM64; các ghi chú “thiếu dependencies/chưa chạy help” trong phần **Runtime khảo sát** bên dưới mô tả audit Phase 1 trước setup, không thay thế evidence môi trường mới. Giữ evidence Phase 1 nguyên trạng để không xóa lịch sử kiểm tra. DAIL có pins bổ sung trong cấu hình repo chính cho cặp Torch/torchtext và các gói NLP; nguồn requirements/ngoại lệ được ghi ở `environments/README.md`. Chưa chạy inference hoặc đánh giá dataset.

## Revision chốt

| Thành phần | Repository / revision | Runtime dự kiến | Entry point |
| --- | --- | --- | --- |
| Few-shot/DIN-SQL | [fe9d2ea39711dafaba7e0f0621513b9ab9646187](https://github.com/dleqhuy/Few-shot-NL2SQL-with-prompting/tree/fe9d2ea39711dafaba7e0f0621513b9ab9646187) | Python 3.9 hoặc 3.10 theo README | `DIN-SQL.py` |
| MAC-SQL | [f8ca56f20192fe85b65a2542f917f820910e80d6](https://github.com/dleqhuy/MAC-SQL/tree/f8ca56f20192fe85b65a2542f917f820910e80d6) | Python 3.9 theo README | `run.py` |
| DAIL-SQL | [7df99e15d8916a35711ff13735fd5ee01262c10e](https://github.com/dleqhuy/DAIL-SQL/tree/7df99e15d8916a35711ff13735fd5ee01262c10e) | Python 3.8 theo README | `data_preprocess.py`, `generate_question.py`, `ask_llm.py` |
| Test Suite SQL Eval | [e97acc546ecbee8fa27fa8dbf025ef61493a876c](https://github.com/taoyds/test-suite-sql-eval/tree/e97acc546ecbee8fa27fa8dbf025ef61493a876c) | Đề xuất Python 3.10; upstream không pin | `evaluation.py` |

Branch clone khi khảo sát được lưu trong JSON; SHA là định danh contract. Các tham chiếu file bên dưới đều thuộc SHA trong bảng này.

## Quy ước cho adapter và command

Command dưới đây là **template đã đối chiếu source**, chưa kiểm chứng end-to-end. `$PY_*` là executable tuyệt đối của từng venv; `$SRC_*` là checkout được pin; `$RUN`, `$SPIDER`, `$TEST_SUITE_DB` là đường dẫn tuyệt đối. Tạo các thư mục cha trước khi gọi. Khi triển khai dùng `subprocess` với danh sách arguments, không dựng shell string.

- Repo chính nạp `.env` với `override=False`, kiểm tra ba biến `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` và truyền environment rõ ràng. Chỉ DIN-SQL tự nạp `.env`; MAC/DAIL cần environment được export từ cha.
- Dùng một manifest subset có thứ tự và `source_index`; mỗi method nhận cùng mẫu. Không dùng trường `question_id` của method làm ID toàn cục.
- Giữ raw output trước mọi chuẩn hóa; kiểm tra số lượng, ID thiếu/thừa/trùng, `db_id` và SQL rỗng trước khi tạo file evaluator. Lỗi một mẫu không được làm dồn ánh xạ mẫu sau.
- Đặt `PYTHONDONTWRITEBYTECODE=1` và cache ngoài checkout. DAIL cần workspace chạy riêng với source được symlink hoặc copy nguyên trạng; **không symlink cả dataset có thể ghi** vào dữ liệu dùng chung. Với method thực thi SQL, dùng bản sao database cho run nếu cần bảo đảm dữ liệu nguồn bất biến.
- Timeout toàn subprocess do orchestrator quản lý; source có retry vô hạn hoặc không bảo đảm timeout cứng. Không coi exit code 0 là đủ để xác nhận đủ prediction.

## Few-shot/DIN-SQL

### CLI, dữ liệu và dependencies

[Bằng chứng source: DIN-SQL.py](https://github.com/dleqhuy/Few-shot-NL2SQL-with-prompting/blob/fe9d2ea39711dafaba7e0f0621513b9ab9646187/DIN-SQL.py#L436): CLI dùng `sys.argv`, đúng 5 phần tử, bắt buộc thứ tự `--dataset` rồi `--output`. Không có `--help`, `--limit`, `--split` hoặc resume.

```bash
# cwd = thư mục run; script được gọi bằng đường dẫn tuyệt đối
"$PY_FEW" "$SRC_FEW/DIN-SQL.py" \
  --dataset "$RUN/input/few-shot/" --output "$RUN/raw/few-shot.sql"
```

**Dấu `/` cuối dataset là bắt buộc** vì source nối chuỗi với `tables.json` và `dev.json`. Stage `dev.json` bằng subset Spider, giữ `question`, `query`, `db_id`; giữ **tables.json đầy đủ**, bao gồm `college_2` dùng trong prompt hard-coded. Script đọc schema JSON, không mở SQLite trên luồng Spider. Demonstrations nằm trong source; không có bước retrieval hoặc preprocessing riêng.

[requirements.txt](https://github.com/dleqhuy/Few-shot-NL2SQL-with-prompting/blob/fe9d2ea39711dafaba7e0f0621513b9ab9646187/requirements.txt) pin `openai==0.27.0`, `pandas==1.5.3`, `python-dotenv==1.0.1`, `numpy==1.24.2`, `torch==1.13.1`, `transformers==4.26.1`, `langchain==0.0.200` và các gói khác. Spider entry point trực tiếp dùng pandas và provider; không mặc định toàn bộ bộ requirements cũ cài được trên Python mới/macOS ARM. Phase 2 cần venv riêng và ghi phiên bản thực cài.

### LLM, output và giới hạn

[llm_provider.py:17–55](https://github.com/dleqhuy/Few-shot-NL2SQL-with-prompting/blob/fe9d2ea39711dafaba7e0f0621513b9ab9646187/llm_provider.py#L17) nạp `.env` cạnh provider với `override=False`. Ưu tiên `LLM_*`, sau đó aliases `OPENAI_API_KEY`, `OPENAI_BASE_URL`/`OPENAI_API_BASE`, `OPENAI_MODEL`. Mặc định base URL OpenAI và model `gpt-4`; thiếu key gây lỗi. Model trong request lấy từ config, không bị prompt helper override. Chat Completions, temperature 0, max_tokens 600 cho generation/350 cho debug, stop riêng, request_timeout 120 giây.

[DIN-SQL.py:575–668](https://github.com/dleqhuy/Few-shot-NL2SQL-with-prompting/blob/fe9d2ea39711dafaba7e0f0621513b9ab9646187/DIN-SQL.py#L575): duyệt DataFrame theo thứ tự input; raw một SQL mỗi dòng, không có ID. Chỉ mở output mode `w` **sau khi hoàn tất toàn bộ vòng lặp**, không checkpoint. Source thay newline ở debug response và tự thêm `SELECT `; adapter không tự sửa lại SQL này. Stdout có question, gold, intermediate responses, SQL; phải lưu log run.

Các vòng gọi LLM retry vô hạn, sleep 3 giây khi có exception; parsing classification có nhánh có thể làm dừng cả run. Nếu timeout trước khi kết thúc có thể không có file prediction. Chính sách adapter: subset bằng staging input; mapping theo vị trí chỉ khi đủ số dòng; không hỗ trợ resume ban đầu, rerun vào run mới.

Runtime khảo sát: `python3 -B DIN-SQL.py --help` exit 1 do thiếu `pandas`, chưa đi tới kiểm tra argv; hợp đồng argv đã được đối chiếu tĩnh, không diễn giải lỗi import là kết quả help.

## MAC-SQL

### CLI và tài nguyên

[Bằng chứng: run.py](https://github.com/dleqhuy/MAC-SQL/blob/f8ca56f20192fe85b65a2542f917f820910e80d6/run.py#L206):

```bash
# cwd = thư mục run; giữ Selector mặc định
"$PY_MAC" "$SRC_MAC/run.py" \
  --dataset_name spider --dataset_mode dev \
  --input_file "$RUN/input/mac-subset.json" \
  --db_path "$RUN/input/database" --tables_json_path "$SPIDER/tables.json" \
  --output_file "$RUN/raw/mac/results.jsonl" \
  --log_file "$RUN/logs/mac/agent.log" --start_pos 0
```

Có `--use_gold_schema`, `--without_selector`; không bật hai flag này cho baseline. Input Spider cần `db_id`, `question`, `query`, **`sql`** để tính hardness; schema `tables.json`; DB layout `<db_path>/<db_id>/<db_id>.sqlite`. Selector đọc schema/giá trị và Refiner thực thi SQL. Không có bước retrieval model hoặc preprocessing ngoài Spider chuẩn.

[requirements.txt](https://github.com/dleqhuy/MAC-SQL/blob/f8ca56f20192fe85b65a2542f917f820910e80d6/requirements.txt): `openai==0.28.1`, `func_timeout`, `sqlparse`, `requests`, `pandas`, `tiktoken`, `tqdm`, `nltk`, `flask`. README dùng Python 3.9 và NLTK `punkt`; dependencies khác chưa pin, phải lock sau khi kiểm chứng môi trường.

### Environment, file ghi và mapping

[core/api_config.py](https://github.com/dleqhuy/MAC-SQL/blob/f8ca56f20192fe85b65a2542f917f820910e80d6/core/api_config.py), [core/llm.py](https://github.com/dleqhuy/MAC-SQL/blob/f8ca56f20192fe85b65a2542f917f820910e80d6/core/llm.py): chỉ đọc `LLM_*` từ environment lúc import, không nạp `.env`, không alias OpenAI. Mặc định URL `http://localhost:20128/v1`, model `cx/gpt-6-luna`, key rỗng; thiếu key lỗi trước request. Model lấy `MODEL_NAME`; Chat Completions không truyền temperature, max_tokens hay request_timeout, nên phải ghi nhận mặc định provider, không báo temperature 0. Retry 5 lần với sleep 20 giây.

`ChatManager.__init__` gọi LLM với `Hello world!` **trước khi chạy mẫu và trước init log** ([core/chat_manager.py:13–35](https://github.com/dleqhuy/MAC-SQL/blob/f8ca56f20192fe85b65a2542f917f820910e80d6/core/chat_manager.py#L13)). Đây là một request bổ sung; dry-run/doctor không được khởi tạo ChatManager.

File ghi:

- `--output_file`: JSONL append/flush từng mẫu; có `idx`, `db_id`, `query` (câu hỏi), `ground_truth`, `pred` và các trường agent. Exception có thể làm **bỏ hẳn một mẫu** nhưng vẫn tiếp tục và exit 0.
- Cạnh output tạo/ghi đè `pred_dev.sql`, xuất theo **thứ tự JSONL hiện có**, không sort khi resume Spider.
- `--log_file` append prompt/response; cùng thư mục có `api_trace.json` nhưng nội dung là **JSONL**, append usage/response/idx. Không dùng mặc định `--log_file ''` vì `os.makedirs('')` sẽ lỗi; phải truyền path có thư mục cha.

[run.py:72–134](https://github.com/dleqhuy/MAC-SQL/blob/f8ca56f20192fe85b65a2542f917f820910e80d6/run.py#L72): `finished_ids` từ output `idx`; `unfinished_ids` là vị trí `0..len(input)-1` sau `start_pos`, nhưng lọc mẫu bằng `question_id`. Vì vậy adapter phải gán lại `question_id=0..N-1` trong **bản staging** subset; lưu mapping về `source_index` riêng. Resume chỉ an toàn khi input, thứ tự, model/config giữ nguyên; map JSONL theo `idx` và sort theo manifest, không tin file `pred_dev.sql`. Chưa bật resume trên CLI chính trước kiểm chứng runtime.

Runtime khảo sát: parser cô lập chấp nhận template, defaults được lưu trong JSON; `run.py --help` exit 1 do thiếu `func_timeout`. Chưa chạy Selector/Refiner hoặc kiểm chứng resume.

## DAIL-SQL

### Môi trường, staging và preprocessing

README yêu cầu Python 3.8, Stanford CoreNLP bản `2018-10-05` + Java, NLTK `punkt`/`stopwords`, Spider dev/train/databases. [requirements.txt](https://github.com/dleqhuy/DAIL-SQL/blob/7df99e15d8916a35711ff13735fd5ee01262c10e/requirements.txt) gồm `openai>=0.27,<1`, `protobuf==3.20.*`, torch, torchtext, transformers, sentence_transformers, stanford-corenlp, sql_metadata, bpemb, attrs, nltk, numpy, tqdm. Các phiên bản torch/torchtext và dependency bắc cầu cần được khóa theo môi trường thực tế.

`generate_question.py` hard-code `PATH_DATA='dataset/'` và output `dataset/process/...` tương đối cwd. Chuẩn bị `$RUN/work/dail` với symlink **từng file/thư mục source** `data_preprocess.py`, `generate_question.py`, `ask_llm.py`, `prompt`, `utils`, `llm` trỏ checkout pin; dùng dataset/process/third_party riêng. Không chạy các shell script có sẵn: chúng truyền `--model gpt-4` override `LLM_MODEL` và nhận API key bằng positional argument.

Staging `$RUN/work/dail/dataset/spider/`:

- `dev.json`: subset theo manifest, giữ nguyên trường Spider như `question_toks`, `query`, `db_id`.
- `train_spider.json`, `train_others.json`, `tables.json`: dữ liệu đầy đủ cho demonstrations/schema; `database/` đủ DB mà `tables.json` và train/dev cần (không chỉ DB của subset).
- `dev_gold.sql`, `train_gold.sql` được khai báo trong dataset class; cần khi dùng helper đọc answers. Luồng template dưới đây chủ yếu đọc JSON/SQLite/schema-linking, không dùng mini index.

```bash
# cwd của toàn bộ pipeline = $RUN/work/dail
"$PY_DAIL" data_preprocess.py --data_type spider --data_dir ./dataset/spider
"$PY_DAIL" generate_question.py \
  --data_type spider --split test --tokenizer gpt-3.5-turbo \
  --max_seq_len 4096 --prompt_repr SQL --k_shot 9 --example_type QA \
  --selector_type EUCDISQUESTIONMASK
"$PY_DAIL" ask_llm.py \
  --question ./dataset/process/SPIDER-TEST_SQL_9-SHOT_EUCDISQUESTIONMASK_QA-EXAMPLE_CTX-200_ANS-4096 \
  --n 1 --batch_size 1
# PRE_SQL = kết quả bước trên; MODEL_FILE = LLM_MODEL với / và backslash đổi thành _
"$PY_DAIL" generate_question.py \
  --data_type spider --split test --tokenizer gpt-3.5-turbo \
  --max_seq_len 4096 --prompt_repr SQL --k_shot 9 --example_type QA \
  --selector_type EUCDISMASKPRESKLSIMTHR --pre_test_result "$PRE_SQL"
"$PY_DAIL" ask_llm.py \
  --question ./dataset/process/SPIDER-TEST_SQL_9-SHOT_EUCDISMASKPRESKLSIMTHR_QA-EXAMPLE_CTX-200_ANS-4096 \
  --n 1 --batch_size 1
```

[Bằng chứng: data_preprocess.py](https://github.com/dleqhuy/DAIL-SQL/blob/7df99e15d8916a35711ff13735fd5ee01262c10e/data_preprocess.py#L104) gộp train, tạo `train_spider_and_others.json` và `enc/{train,test}_schema-linking.jsonl` trong dataset. Dùng GloVe **42B**, cache `$CACHE_DIR/vector_cache` (mặc định cwd), lemmatize qua CoreNLP. Đặt `CORENLP_HOME` tuyệt đối tới bản cài bên ngoài checkout: fallback trong `utils/linking_utils/corenlp.py` dựa trên vị trí file có thể không trùng `third_party/` ở root như README mô tả.

[Bằng chứng: utils/data_builder.py](https://github.com/dleqhuy/DAIL-SQL/blob/7df99e15d8916a35711ff13735fd5ee01262c10e/utils/data_builder.py): `--split test` thực tế đọc **Spider dev.json**. Giữ tập train làm nguồn demonstrations, schema-linking test phải khớp thứ tự dev subset. Không tái sử dụng nguyên cache full dev sau khi lọc subset. [ExampleSelectorTemplate.py](https://github.com/dleqhuy/DAIL-SQL/blob/7df99e15d8916a35711ff13735fd5ee01262c10e/prompt/ExampleSelectorTemplate.py#L320) dùng `sentence-transformers/all-mpnet-base-v2` trên CPU, Euclidean distance trên masked questions, skeleton similarity threshold **0.85**, fallback khi thiếu 9 examples. Pre-SQL phải sinh từ cùng subset theo cùng thứ tự; không dùng kết quả full dev đóng sẵn trong repo.

### LLM, output, subset và giới hạn

[ask_llm.py:18–94](https://github.com/dleqhuy/DAIL-SQL/blob/7df99e15d8916a35711ff13735fd5ee01262c10e/ask_llm.py#L18), [llm/chatgpt.py](https://github.com/dleqhuy/DAIL-SQL/blob/7df99e15d8916a35711ff13735fd5ee01262c10e/llm/chatgpt.py): API key/model lấy `LLM_API_KEY`/`LLM_MODEL` làm argparse defaults; **CLI overrides environment**. URL lấy `LLM_BASE_URL`, mặc định OpenAI; model mặc định `gpt-3.5-turbo`. Không tự nạp `.env`. Custom model đi vào Chat Completions, batch_size phải 1; chỉ một số model legacy dùng Completion. Temperature mặc định 0, max_tokens **200**, không request_timeout, retry vô hạn trên exception. Provider cần trả usage có `total_tokens`.

`ask_llm.py` đọc `<question-dir>/questions.json`, giữ thứ tự bằng DataLoader `shuffle=False`. Ghi `RESULTS_MODEL-<MODEL_FILE>.txt` ngay trong question-dir; `start_index=0` ghi đè, khác 0 append. `--start_index` inclusive / `--end_index` exclusive đếm **batch**; template dùng batch_size 1. Có `--mini_index_path` nhưng nó chỉ lọc questions, không lọc db_ids tương ứng; tránh dùng, đặc biệt khi self-consistency.

Mặc định `--n=5` bật self-consistency và thực thi SQL chọn kết quả theo DB. **Chốt baseline DAIL-SQL thường với `--n 1` ở cả hai lượt**; nếu thêm self-consistency sau này phải đặt tên cấu hình riêng, `--db_dir` đúng DB và ghi thêm `n`/chi phí trong manifest. Adapter map raw theo thứ tự manifest khi đủ dòng; không suy luận đã resume chỉ từ file tồn tại. Append không kiểm tra số dòng/mapping nên ban đầu rerun stage trong thư mục mới.

Giới hạn phát hiện từ source:

- `utils/utils.py:170–182`: `get_tokenizer()` và `count_tokens()` đều **return 0**. Do đó `--tokenizer` không đổi tokenizer thực tế, budget context và ước lượng token/cost không hoạt động như tên flags. Không sửa source trong orchestrator; ghi rõ hành vi revision này trong manifest/report và kiểm tra context với provider khi chạy thật.
- `ask_llm.py` đặt `res=''` khi bắt `InvalidRequestError` rồi vẫn truy cập `res['total_tokens']`; nhánh lỗi này có thể crash thay vì ghi `SELECT` như thông báo.
- `llm/chatgpt.py` retry mọi exception vô hạn; cần timeout toàn stage. Runtime với local endpoint, CoreNLP, GloVe và các cặp torch/torchtext chưa được kiểm chứng.

Runtime khảo sát: ba parser cô lập chấp nhận các template. Full `--help` lần lượt lỗi thiếu `tqdm` (preprocess), `transformers` (generate), `openai` (ask). Các SHA nguồn và kết quả được lưu trong evidence; không có predictions được tạo.

## Test Suite SQL Eval

### CLI, input và dependencies

[Bằng chứng: evaluation.py:915–938](https://github.com/taoyds/test-suite-sql-eval/blob/e97acc546ecbee8fa27fa8dbf025ef61493a876c/evaluation.py#L915):

```bash
# cwd = $RUN/work/evaluator; source script gọi bằng absolute path
"$PY_EVAL" "$SRC_EVAL/evaluation.py" \
  --gold "$RUN/evaluation/gold.sql" --pred "$RUN/evaluation/pred.sql" \
  --db "$TEST_SUITE_DB" --table "$SPIDER/tables.json" \
  --etype all --keep_distinct
```

Upstream không có requirements lock; imports thực tế cần **nltk, sqlparse, tqdm** và thư viện chuẩn. `process_sql.py` dùng `nltk.word_tokenize`, cần tài nguyên tokenizer tương ứng NLTK đã cài (không mặc định chỉ `punkt` đủ với mọi phiên bản). Python 3.10 là đề xuất môi trường riêng, chưa xác nhận runtime.

Gold `SQL<TAB>db_id`, prediction một SQL mỗi dòng, cùng thứ tự; Spider không chèn dòng trống giữa mẫu. Parser coi dòng trống là ranh giới session. [evaluation.py:504–572](https://github.com/taoyds/test-suite-sql-eval/blob/e97acc546ecbee8fa27fa8dbf025ef61493a876c/evaluation.py#L504) kiểm tra số session nhưng dùng `zip` trên từng session, có thể âm thầm bỏ mẫu thiếu/thừa. Wrapper **bắt buộc** kiểm tra đủ N prediction trước khi gọi.

DB layout `<db_root>/<db_id>/<db_id>.sqlite` để đọc schema; `exec_eval.py:200–201` duyệt mọi file có `.sqlite` trong thư mục DB đó làm test suite. Cần test-suite databases tải riêng với provenance/checksum; chỉ có SQLite gốc thì không được báo test-suite accuracy. Không trộn file SQLite ngoài suite vào thư mục này.

### Chính sách đánh giá chốt cho MVP

- `--etype all` xuất execution + exact set match; `match`/`all` cần `--table`; source mặc định `exec`.
- **Không `--plug_value`**: ba method sinh SQL có values, đánh giá values của prediction. `--plug_value` chỉ dùng một thí nghiệm riêng, phải đổi nhãn metric/config.
- **Có `--keep_distinct`**: giữ DISTINCT trong execution. Exact set match vẫn theo evaluator với `DISABLE_VALUE=True`, `DISABLE_DISTINCT=True`; không mô tả nó là exact string match hay value-sensitive.
- SQL lỗi thực thi nhận exec=0; gold SQL lỗi có thể assert và dừng evaluator. Không lọc bỏ SQL lỗi khỏi mẫu số, không ghi prediction rỗng làm dòng blank; mẫu thiếu phải báo lỗi validation trước evaluation.
- Source có `TIMEOUT=60` và `asyncio.wait_for`, nhưng bên trong gọi SQLite đồng bộ, không nhường event loop. **Không coi đây là giới hạn cứng 60 giây**; orchestrator cần timeout subprocess và báo evaluation chưa hoàn tất nếu hết hạn.

[exec_eval.py](https://github.com/taoyds/test-suite-sql-eval/blob/e97acc546ecbee8fa27fa8dbf025ef61493a876c/exec_eval.py) và [evaluation.py](https://github.com/taoyds/test-suite-sql-eval/blob/e97acc546ecbee8fa27fa8dbf025ef61493a876c/evaluation.py) trên luồng CLI này trả metrics dạng bảng stdout (count/hardness/exec/exact/partial); không có JSON metrics hay output-path option. Wrapper phải giữ stdout/stderr và parse bảng tại revision pin, kiểm tra `all.count=N`, `exec`, `exact`, exit code; log debug mismatch có thể xen kẽ. Các biến tmp/subprocess trong file không đồng nghĩa CLI này chạy SQL trong process riêng.

Runtime khảo sát: parser cô lập chấp nhận template; full help exit 1 do thiếu `nltk`. **Chưa** chạy gold-as-prediction, prediction sai, SQL invalid hoặc test suites; đó là tiêu chí Phase 3. Có thể kiểm tra synthetic SQLite trước khi tải bộ test suites, nhưng không gọi kết quả synthetic là Spider test-suite accuracy.

## Bàn giao sang các phase sau

1. **Phase 2:** pin đúng bốn SHA trên, venv riêng và khóa dependencies thực cài; doctor chỉ kiểm tra cấu hình/tài nguyên, dry-run chỉ dựng argv/cwd/env đã che secrets, không import entry point method.
2. **Phase 3:** tải Spider/test suites riêng, dựng subset và mapping ổn định; kiểm chứng evaluator bằng gold/sai/invalid, số lượng prediction và timeout.
3. **Phase 4:** chạy DIN-SQL 3 mẫu, lưu stdout/raw, kiểm chứng thứ tự và checkout sạch.
4. **Phase 5:** MAC staging ID + JSONL mapping; DAIL workspace riêng, schema-linking theo subset, hai lượt retrieval với pre-SQL cùng subset. Kiểm tra thực tế các giới hạn đã nêu trước khi bật resume hoặc self-consistency.

Phase 1 hoàn tất ở mức khảo sát source cho phép trong kế hoạch. Chưa có cam kết dependency installation hay inference thành công trước các kiểm tra runtime ở phase tương ứng.
