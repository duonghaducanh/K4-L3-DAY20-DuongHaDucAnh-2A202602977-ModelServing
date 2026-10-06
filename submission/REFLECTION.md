# Reflection — Day 20 Lab (Personal Report)

> **Đây là báo cáo cá nhân.** Số liệu của bạn **không** so sánh được với bạn cùng lớp
> — chỉ so **before vs after trên chính máy bạn**. Rubric chấm độ rõ ràng của setup,
> đo lường và **lập luận**, không chấm tốc độ tuyệt đối.
>
> `make verify` sẽ fail nếu còn placeholder chưa điền. Đó là cố ý.

**Họ Tên:** DuongHaDucAnh
**MSSV:** 2A202602977
**Cohort:** A20-K4
**Ngày submit:** 2026-10-06

---

## 1. Hardware & runtime  *(rubric 1, 2 — 10 điểm)*

> Từ `make probe`. Paste output hoặc điền tay.

- **OS:** Windows 11
- **CPU:** Intel Core i7-11800H @ 2.30GHz
- **Cores:** 8 physical / 16 logical
- **CPU extensions:** AVX2 + AVX-512 (llama.cpp loaded its `ggml-cpu-icelake.dll` backend)
- **RAM:** 15.7 GB
- **Accelerator:** NVIDIA GeForce RTX 3070 Laptop GPU, 8192 MiB — present but **unused** (`ngl=0`). The prebuilt asset ships `ggml-cuda.dll`, but it **fails to load** (`failed to load ... ggml-cuda.dll`; no CUDA runtime DLLs alongside it) and `--list-devices` reports none, so the lab ran CPU-only
- **llama.cpp asset đã tải:** `llama-b10488-bin-win-cuda-12.4-x64.zip`
- **Model đã dùng:** Qwen3.5 0.8B (`LAB_MODEL=qwen35-0.8b`)
- **Quantization:** Q4_K_M + UD-Q2_K_XL (từ `models/active.json`)

**Chạy ở đâu:** laptop của tôi (local, không dùng cloud fallback)

**Setup story** (≤ 80 chữ): Không đổi code lab, nhưng **mạng rất chậm (~0.2–0.5 MB/s)** làm
downloader của lab (urllib, timeout cố định, không resume) chết giữa chừng ở file GGUF
532 MB. Workaround: tôi viết `_dl.py` — tải lại được từ `.part`, retry mọi socket error —
rồi tải xong model + runtime. Sau đó `make bench/tune/serve/load` chạy thẳng.

---

## 2. Đo lường  *(rubric 3, 4, 5 — 20 điểm)*

> Paste bảng từ `benchmarks/01-quickstart-results.md` (`make bench` tự sinh).

| Quantization | Size (GB) | Load (ms) | TTFT P50/P95 (ms) | TPOT P50/P95 (ms) | E2E P50/P95/P99 (ms) | Decode (tok/s) |
|---|--:|--:|--:|--:|--:|--:|
| Q4_K_M | 0.50 | 2610 | 336 / 381 | 20.5 / 24.1 | 1549 / 1852 / 1852 | 48.8 |
| UD-Q2_K_XL | 0.39 | 1440 | 403 / 433 | 18.7 / 24.4 | 1582 / 1730 / 1730 | 53.4 |

**Quan sát** (≤ 60 chữ): 2-bit **không** nhanh hơn — chênh 1.09× chỉ là nhiễu (đo lại
5 reps: Q4 52.05 ± 0.87 vs Q2 52.40 ± 2.50, **hoà**), dù nhỏ hơn 22%. Máy này CPU-only
(`ngl=0`), compute-limited: dequant 2-bit tốn hơn số byte tiết kiệm. Chất lượng cũng
kém hơn: eval 7 prompt (temp 0), Q4 **5/7** vs Q2 **4/7** — Q2 trả "Bun." cho "thủ đô
Pháp". **Kết luận: dùng Q4_K_M.**

---

## 3. Serving under load  *(rubric 8, 9, 10 — 20 điểm)*

> Từ `benchmarks/02-server-results.md` (`make load-report`).

| Users | RPS | P50 (ms) | P95 (ms) | P99 (ms) | Eff. concurrency | Failures |
|--:|--:|--:|--:|--:|--:|--:|
| 10 | 1.18 | 7000 | 11000 | 14000 | 8.6 | 0.0% |
| 50 | 1.45 | 30000 | 37000 | 39000 | 36.9 | 0.0% |

- **Offered load tăng 5×, throughput thực tăng:** _1.22×_ (69 → 85 reqs — 24% của linear)
- **P95 tăng:** _3.36×_
- **Effective concurrency ở 50 users:** _36.9_ so với `--parallel` = _4_ slots

**Peak `llamacpp:n_busy_slots_per_decode`** (từ `make metrics` khi `make load-50` đang
chạy): _3.99_ / _4_ slots (100%)

**Saturation reading** (≤ 80 chữ): Server bão hoà **tại hoặc trước 50 users**. Bằng
chứng thuyết phục nhất: **5× offered load → chỉ 1.22× throughput**, trong khi effective
concurrency vọt 8.6 → 36.9 = 9.2× số slot. Latency thêm là **queue time, không phải
compute**: nếu user thêm vào mua compute thật thì reqs hoàn thành phải tăng theo; thay
vào đó P95 tăng 3.36× mà throughput gần như đứng yên, và gauge `requests_deferred` peak
**46** xác nhận có hàng đợi. Nâng goodput@SLO (chọn P95 ≤ 30s), tôi đổi **`--parallel`
4 → 8 trước**: nút cổ chai là slot decode (busy 3.99/4 = 100%), thêm slot cho nhiều
request chia sẻ mỗi decode step. Không chọn `-t` vì nó đổi tốc độ mỗi step, không đổi
số request mỗi step.

---

## 4. Integration  *(rubric 12, 13 — 15 điểm)*

> Từ `make pipeline`. Nói thật cái nào real, cái nào stub — stub **không** mất điểm.

| Day | Piece | Real hay stub? |
|---|---|---|
| N16 Cloud/IaC | stub — không dùng cloud/IaC; mọi thứ chạy local trên laptop |
| N17 Data pipeline | stub — không có ingestion pipeline; 6 `TOY_DOCS` hardcoded |
| N18 Lakehouse | stub — một list Python các dict, không phải lakehouse |
| N19 Vector + features | stub — retrieval backend = `keyword overlap` (đếm trùng token), không phải vector index; embed = 0.0 ms vì không có embedding server |
| N20 Serving | `llama-server` | real |

**Latency split** (mean của 3 query, từ output của `pipeline.py`):

- embed: _0.0 ms_
- retrieve: _0.0 ms_
- llm: _4185.6 ms_
- **stage chiếm nhiều nhất:** _llm_ (_100%_ của total)

**Reflection** (≤ 60 chữ): N16–N19 đều **stub**, chỉ N20 real. Bottleneck đúng như kỳ
vọng nhưng cực đoan: llm = 4185.6/4185.7 ms = **100%**; embed+retrieve < 0.1 ms. Muốn
giảm 2×, chỉ tấn công **stage llm** — và bên trong nó là **decode**, không phải prefill:
server timings cho thấy query 1 = prefill 151 tok/456 ms + decode 116 tok/2070 ms, nên
giảm `max_tokens` hoặc bật GPU offload (RTX 3070 đang idle ở `ngl=0`). Sửa retrieval vô
nghĩa.

---

## 5. The single change that mattered most  *(rubric 11 — 10 điểm)*

> **Phần quan trọng nhất của report.** Không cần bonus track: `make tune` đã cho bạn
> một before/after thật (`benchmarks/01-tuning-tg128.md`). Đổi quantization,
> `LAB_N_CTX`, hay `--parallel` rồi đo lại cũng được.

> **Lưu ý về số liệu (đã đính chính).** Bản đầu tiên của report này được đo khi máy
> đang bị contention/power-limit: mọi con số decode thấp hơn ~4× và curve bị phẳng, cho
> peak sai ở `-t 4`. Tôi phát hiện ra vì số không tái lập, đã đo lại trên máy rảnh (3
> reps `llama-bench`, ±<1 tok/s) và **viết lại toàn bộ §2, §3, §5 và các file
> `benchmarks/` tương ứng** theo số đo được. Các con số dưới đây là bản tái lập được.

**Change:** pin decode threads to the 8 **physical** cores instead of oversubscribing to all 16 **logical** cores (hyperthreads)

```
before:  32.0 tok/s   (tg128 decode, -t 16)
after:   55.2 tok/s   (tg128 decode, -t 8)
speedup: 1.73×
```

**Tại sao nó work** (1–2 đoạn — đây là phần grader đọc kỹ nhất):

Curve của decode **đúng hình dạng deck mô tả**: leo 18.3 → 46.6 → **55.2** tok/s khi
threads 1 → 4 → 8, rồi **sụp** xuống 32.0 (`-t 16`, hyperthread) và 19.8 (`-t 32`).
Điểm gãy nằm **đúng số physical core (8)**; vượt qua đó là mất mát, spread 3.01× và
điểm tệ nhất là điểm *nhiều thread nhất*. Vậy câu hỏi là: *tại sao hyperthread làm
decode chậm đi?*

Vì decode làm việc cho ~1 token mỗi lượt trên cùng bộ weight → cường độ số học ≈ 1
FLOP/byte, nên nó bị chặn bởi **memory bandwidth/latency, không phải FLOPs**. Đi từ 1
lên 8 thread là thêm *memory-level parallelism* thật: 8 core có 8 luồng cache-miss độc
lập cùng bay, đẩy băng thông lên tới bão hoà. Quá 8 thì **không còn gì để song song
hoá trong memory subsystem** — 8 core vật lý đã giữ kênh memory bận rồi, nên 8
hyperthread không tạo thêm memory request nào; chúng chỉ làm phình **barrier đồng bộ
mỗi decode step** mà mọi thread phải qua. Sync tăng, việc hữu ích không tăng → tụt.
`-t 32` nhân đôi contention, còn 19.8.

**Phép đối chứng: prefill có điểm gãy NGƯỢC LẠI.** Tôi chạy lại đúng sweep đó trên
metric prefill `pp512` (cùng model, cùng `ngl=0`):

| threads | 1 | 4 | 8 | 16 | 32 |
|:--|--:|--:|--:|--:|--:|
| `tg128` decode (tok/s) | 18.3 | 46.6 | **55.2** | 32.0 | 19.8 |
| `pp512` prefill (tok/s) | 63.8 | 166.1 | 228.8 | **254.5** | 238.0 |

Prefill *vẫn leo qua khỏi 8* và đỉnh ở **`-t 16`** (logical cores), rồi mới phẳng nhẹ.
Hai stage, hai điểm gãy: **prefill là compute-bound** (mỗi lượt ~512 token trên cùng bộ
weight, cường độ cao) nên mỗi thread thêm FLOPs thật, và hyperthread còn giúp lấp
pipeline bubble — đỉnh ở logical core. **Decode là bandwidth-bound** nên bão hoà ở
physical core. Nên `-t` tối ưu **phụ thuộc stage**: `-t 8` cho serving nặng decode
(đúng loại lab này phục vụ), `-t 16` nếu bạn nạp long-context RAG nặng prefill. Default
`-t 8` của lab **đã đúng sẵn** cho decode — nghĩa là bài học ở đây là *đừng*
oversubscribe, chứ không phải phải đổi default.

**Đính chính trung thực.** Bản trước của report này claim đỉnh ở `-t 4` với số thấp hơn
~4× (12.0 tại `-t 8`). Lần đo đó **không tái lập được**: 3 lần chạy `llama-bench` lặp
lại trên máy đang rảnh cho 47.2 ± 0.9 tok/s (`-t 4`) và 53.9 ± 0.4 (`-t 8`) — khớp bảng
trên — trong khi sweep `pp512` tái lập sát ở cả hai lần. Số cũ đo dưới contention/power
limit, làm phẳng curve và đẩy điểm gãy sai chỗ. Số và lập luận ở trên là bản đo được;
claim cũ đã bị rút lại. (Chạy đơn lẻ trên laptop lệch vài % giữa các lần, nhưng *hình
dạng* curve — decode đỉnh ở physical core, prefill đỉnh ở logical core — tái lập ở mọi
lần lặp.)

Supporting artifact: `benchmarks/01-tuning-tg128.md`, `benchmarks/01-tuning-pp512.md`.

---

## 6. Bonus  *(optional — tối đa 10 điểm)*

> Bỏ trống nếu không làm. Xem `docs/bonus/README.md`. Đừng làm hết — **một** finding sâu
> ăn điểm hơn năm bảng nông.

**Đã làm:** B1 (build source + `compare-builds`, cả `tg128` và `pp512`), B2 (sweep
`-b/-ub` chunked prefill + sweep context-length), **B4 = challenge C7** (khảo sát
instruction set), **B5 = C9** (embedding serving regime) và **C8** (chẩn đoán semantic
cache). Đây là before/after **của bonus track** (build từ source), **không** phải
`make tune` của base.

**Numbers** (C7 — cùng source, cùng model, cùng `-t 8 -ngl 0`, chỉ đổi ISA target;
cả hai build đều OpenMP OFF nên không lẫn yếu tố threading):

```
before:  225.0 tok/s   (pp512 prefill, build baseline AVX2, -DGGML_NATIVE=OFF)
after:   253.4 tok/s   (pp512 prefill, build -DGGML_NATIVE=ON, AVX-512)
speedup: 1.13×
```

**Điều này nói lên gì mà deck chưa nói:**

**Cùng một quyết định "khớp kernel với silicon" cho ra kết quả TRÁI NGƯỢC nhau tuỳ
stage — và điều đó giải thích luôn vì sao B1 ra parity.** Trên `pp512` (prefill,
compute-bound) AVX-512 thắng rõ **1.13×** (225.0 → 253.4) và ở `pp2048` vẫn thắng
**1.08×**; nhưng trên `tg128` (decode, **memory-bandwidth-bound**) nó **0.97×** — không
giúp gì. Cơ chế: decode làm ~1 token/lượt trên cùng 497 MiB weight (intensity ≈ 1
FLOP/byte) nên CPU đứng chờ DRAM/L3, thanh ghi vector rộng hơn không có gì để ăn;
prefill làm ~512 token/lượt (intensity cao) nên thật sự bị chặn bởi vector compute, và
AVX-512 + VNNI thực thi nhiều MAC/cycle hơn. Đây đúng là bản thu nhỏ của "chọn FA3 cho
Hopper, FA4 cho Blackwell": kernel phải khớp silicon, **và cái khớp chỉ trả tiền ở
stage thực sự dùng silicon đó**. Vì vậy một serving stack nặng decode (như lab này)
không được lợi gì từ ISA rộng hơn; stack nặng prefill (nạp long-context RAG, batch
embedding) thì có.

**Điều này nối với B1.** Ở B1, build `-DGGML_NATIVE=ON` cho **parity** với prebuilt
(0.98× `tg128`, 0.96× `pp512`) — nghe như "compile cho CPU mình vô ích". Nhưng C7 chỉ
ra *tại sao*: prebuilt đã tự dispatch tới `ggml-cpu-icelake.dll` (kernel AVX-512) qua
CPUID, nên bản native không thêm được gì **trên ISA** — khác biệt còn lại là OpenMP
(bản source của tôi không có libomp). Chỉ khi ép so sánh xuống một baseline AVX2 thật
(C7) thì lợi thế 13% mới lộ ra, và chỉ ở prefill. Hai kết quả không mâu thuẫn — chúng
là hai góc nhìn của cùng một sự thật.

**Ngoài ra (B2):** sweep `-b/-ub` cho thấy **micro-batch nhỏ thắng** — `-b 128 -ub 128`
= 268.4 tok/s so với `-ub 512` = 235.1 (**1.14×**), và nút thật là `-ub` chứ không phải
`-b`. Trên máy CPU-only này overhead launch theo step vốn đã không đáng kể, nên
micro-batch lớn chỉ làm working set phình ra, evict cache L3 — không có lợi ích amortize
nào để đổi lấy. Sweep context-length xác nhận chi phí prefill tăng siêu tuyến tính
(1.00 → 1.37× trên 256→8192 token), tức mọi token ngữ cảnh thêm vào đều được trả đủ
trong TTFT trước khi token đầu tiên xuất hiện.

**Chi tiết đầy đủ:** `benchmarks/bonus-build-compare-tg128.md` + `-pp512.md` (B1),
`bonus-c7-instruction-set.md` (B4), `bonus-c9-embedding-serving.md` (B5),
`bonus-c8-semantic-cache.md` (B5), `bonus-batch-size-sweep.md` + `bonus-ctx-len-sweep.md` (B2).

---

## 7. Điều làm bạn ngạc nhiên nhất  *(optional)*

_(1–2 câu. Không bắt buộc, nhưng grader đọc hết.)_

Ngạc nhiên nhất: **decode và prefill có điểm gãy thread-sweep ngược nhau trên cùng một
máy** — decode đỉnh ở số *physical* core (`-t 8`, 55.2 tok/s) rồi sụp khi thêm
hyperthread, còn prefill *vẫn leo* qua khỏi 8 và đỉnh ở số *logical* core (`-t 16`, 254.5
tok/s). Cùng một máy, cùng model, cùng `ngl=0` mà `-t` tối ưu khác nhau — nên `-t` phải
tune theo *stage nào đang chạy*, không phải theo model. Ngạc nhiên thứ hai (và là một bài
học về đo lường): lần đo đầu của tôi cho curve bị phẳng/lệch vì máy đang bận; chỉ khi
chạy lại trên máy rảnh thì hình dạng thật mới lộ ra. Một con số không tái lập được thì
không phải bằng chứng.

---

## 8. Self-check trước khi push

- [ ] `hardware.json` committed
- [ ] `models/active.json` committed
- [ ] `benchmarks/01-quickstart-results.md` committed (`make bench`)
- [ ] `benchmarks/01-tuning-tg128.md` committed (`make tune`)
- [ ] `benchmarks/02-server-results.md` committed (`make load-report`)
- [ ] `benchmarks/02-server-batching-u50.md` hoặc `-metrics-u50.csv` committed (`make metrics`)
- [ ] `benchmarks/locust-10_stats.csv` + `locust-50_stats.csv` committed (`make load-10` / `load-50`)
- [ ] `benchmarks/03-integration-results.md` committed (`make pipeline`)
- [ ] Mọi section **"required — replace this line"** trong các file `benchmarks/*.md`
      đã được thay bằng nhận xét của bạn
- [ ] 5 screenshots trong `submission/screenshots/`
- [ ] `make verify` → **exit 0**
- [ ] Repo tên đúng mẫu `K4-L3-DAY20-HoVaTen-MSSV-ModelServing` (xem `docs/SUBMISSION.md`)
- [ ] Repo GitHub ở chế độ **public**
- [ ] Đã push và paste public URL vào VinUni LMS **trước 23:59 (UTC+7) ngày làm lab**
- [ ] **Không** commit `models/*.gguf`, `runtime/` hay `.env` (đã có trong `.gitignore`)

**Quan trọng:** repo phải **public** đến khi điểm được công bố. Private → grader không
xem được → 0 điểm.

---

## 9. Khai báo sử dụng AI  *(xem `docs/RULES.md` §3)*

Tôi có dùng **Claude Code** (Anthropic) trong lab này, cho các việc sau:

- **Viết script tải lại** (`_dl.py`): mạng của tôi quá chậm nên downloader của lab fail;
  tôi nhờ AI viết một downloader có resume/retry để lấy model + runtime.
- **Hỗ trợ gỡ lỗi** các lỗi encoding/ký tự khi chạy script trên Windows.
- **Chạy lại phép đo prefill** (`--metric pp512`) và **đo lặp lại sweep decode** trên máy
  rảnh để kiểm tra tính tái lập; lần đo đầu không tái lập được nên tôi đã rút lại và thay
  bằng số đo lại (xem §5, và ghi chú đính chính ở §2/§3).
- **Hỗ trợ bonus track**: build llama.cpp từ source (B1, C7), viết script so sánh
  instruction-set (C7), chạy embedding/semantic-cache demo (C8/C9) và gỡ lỗi proxy khiến
  `httpx` không gọi được server local.

**Toàn bộ số liệu trong báo cáo này do tôi đo trên máy thật của mình** (`make probe/bench/
tune/serve/load/metrics/pipeline`); AI không tạo số. Phần lập luận và kết luận là của tôi,
có đối chiếu lại với output thật đã lưu trong `benchmarks/` và `submission/screenshots/`.
