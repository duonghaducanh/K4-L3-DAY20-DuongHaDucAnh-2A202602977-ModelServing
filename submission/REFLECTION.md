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
- **Accelerator:** NVIDIA GeForce RTX 3070 Laptop GPU, 8192 MiB — present but **unused** (`ngl=0`; the prebuilt build enumerates no CUDA device, so this lab ran CPU-only)
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
| Q4_K_M | 0.50 | 3627 | 794 / 1476 | 64.0 / 81.2 | 4636 / 5854 / 5854 | 15.6 |
| UD-Q2_K_XL | 0.39 | 4327 | 1155 / 1705 | 85.3 / 152.0 | 6531 / 10952 / 10952 | 11.7 |

**Quan sát** (≤ 60 chữ): 2-bit **không** nhanh hơn — nó **chậm hơn 1.33x** (11.7 vs
15.6 tok/s) dù nhỏ hơn 22%, vì máy này CPU-only (`ngl=0`), compute-limited: dequant
2-bit tốn hơn số byte tiết kiệm. Tôi cũng chạy cùng prompt (`--seed 42`): Q4_K_M trả
lời mạch lạc; UD-Q2_K_XL trả lời tự mâu thuẫn và sai. **Không đáng dùng 2-bit.**

---

## 3. Serving under load  *(rubric 8, 9, 10 — 20 điểm)*

> Từ `benchmarks/02-server-results.md` (`make load-report`).

| Users | RPS | P50 (ms) | P95 (ms) | P99 (ms) | Eff. concurrency | Failures |
|--:|--:|--:|--:|--:|--:|--:|
| 10 | 0.46 | 18000 | 25000 | 26000 | 7.5 | 0.0% |
| 50 | 0.46 | 31000 | 53000 | 56000 | 13.7 | 0.0% |

- **Offered load tăng 5×, throughput thực tăng:** _1.00×_ (26 reqs ở cả hai mức — 20% của linear)
- **P95 tăng:** _2.12×_
- **Effective concurrency ở 50 users:** _13.7_ so với `--parallel` = _4_ slots

**Peak `llamacpp:n_busy_slots_per_decode`** (từ `make metrics` khi `make load-50` đang
chạy): _3.88_ / _4_ slots (97%)

**Saturation reading** (≤ 80 chữ): Server bão hoà **tại hoặc trước 50 users**. Bằng
chứng thuyết phục nhất: **5× offered load → 1.00× throughput** (RPS đứng yên 0.46), trong
khi effective concurrency vọt 7.5 → 13.7 = 3.42× số slot. Latency thêm là **queue time,
không phải compute**: số request hoàn thành y hệt, nên compute không đổi; P95 tăng 2.12×
mà throughput không tăng, và gauge `requests_deferred` peak **46** xác nhận có hàng đợi.
Nâng goodput@SLO (chọn P95 ≤ 30s), tôi đổi **`--parallel` 4 → 8 trước**: nút cổ chai là
slot decode (busy 3.88/4), thêm slot cho nhiều request chia sẻ mỗi decode step. Không chọn
`-t` vì nó đổi tốc độ mỗi step, không đổi số request mỗi step.

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
- retrieve: _0.1 ms_
- llm: _8233.4 ms_
- **stage chiếm nhiều nhất:** _llm_ (_100%_ của total)

**Reflection** (≤ 60 chữ): N16–N19 đều **stub**, chỉ N20 real. Bottleneck đúng như kỳ
vọng nhưng cực đoan hơn: llm = 8233.4/8233.5 ms = **100%**; embed+retrieve chỉ 0.1 ms.
Muốn giảm 2×, chỉ tấn công **stage llm**: bật GPU offload (RTX 3070 đang idle ở `ngl=0`),
giảm `max_tokens`, hoặc rút ngắn prompt — sửa retrieval vô nghĩa.

---

## 5. The single change that mattered most  *(rubric 11 — 10 điểm)*

> **Phần quan trọng nhất của report.** Không cần bonus track: `make tune` đã cho bạn
> một before/after thật (`benchmarks/01-tuning-tg128.md`). Đổi quantization,
> `LAB_N_CTX`, hay `--parallel` rồi đo lại cũng được.

**Change:** hạ `-t` từ 8 (default theo physical cores) xuống 4

```
before:  12.0 tok/s   (tg128 decode, -t 8)
after:   20.2 tok/s   (tg128 decode, -t 4)
speedup: 1.68×
```

**Tại sao nó work** (1–2 đoạn — đây là phần grader đọc kỹ nhất):

Kết quả này **ngược với kỳ vọng của deck**. Deck nói decode tăng tới số *physical core*
(8 ở đây) rồi mới phẳng/giảm. Máy tôi: đỉnh nằm ở **`-t 4`, chỉ bằng nửa số physical
core**, và rơi rất sốc ở trên — 12.0 (`-t 8`), 8.5 (`-t 16`), 4.7 (`-t 32`), spread
4.34×. Vậy câu hỏi thật là: *tại sao 4 thread thắng, và tại sao thêm thread lại phá?*

Giả thuyết đầu tiên đáng kiểm tra là **thermal/power throttling** — i7-11800H là chip
laptop 45 W, 8–32 thread bận có thể làm tụt xung. Để tách "chip throttle" khỏi "stage này
không scale", tôi chạy lại **đúng sweep đó trên metric prefill `pp512`** (cùng model,
cùng `ngl=0`):

| threads | 1 | 4 | 8 | 16 | 32 |
|:--|--:|--:|--:|--:|--:|
| `tg128` decode (tok/s) | 12.3 | **20.2** | 12.0 | 8.5 | 4.7 |
| `pp512` prefill (tok/s) | 63.9 | 165.7 | 228.3 | **237.9** | 231.7 |

Hai stage có **hình dạng ngược nhau**. Prefill *vẫn leo* tới ~16 thread rồi mới phẳng,
**không hề sụp**. Nếu CPU throttle vì quá nhiều thread thì prefill cũng phải sụp — nó
không. Nên cú rơi của decode **không phải nhiệt**, mà do mỗi stage bị chặn bởi thứ khác
nhau:

- **Prefill là compute-bound.** Mỗi lượt nó làm việc cho ~512 token trên cùng bộ weight
  (arithmetic intensity cao), nên mỗi thread thêm vào là FLOPs thật → scale tới ~physical
  core rồi phẳng.
- **Decode thì không.** Mỗi lượt chỉ làm việc cho ~1 token trên cùng bộ weight
  (intensity ≈ 1 FLOP/byte), nên nó bị chặn bởi **memory latency/bandwidth và đồng bộ
  giữa các thread mỗi step**, không phải FLOPs. Bốn thread đã ăn hết băng thông mà memory
  subsystem của laptop này cấp nổi cho model 0.5 GB; vượt qua đó, mỗi decode step vẫn phải
  trả **barrier đồng bộ cho *tất cả* thread**, nên chi phí sync tăng trong khi việc hữu
  ích không tăng. Throughput tụt.

Điểm thực hành (và nó **phụ thuộc metric**): `-t 4` cho serving nặng decode (đúng loại
lab này phục vụ — `make serve` chạy `-t 4`), còn `-t 8…16` nếu bạn quan tâm prefill nặng
như nạp long-context RAG. Default `-t 8` là thỏa hiệp mà **không tốt ở stage nào**. Đây là
lý do một kết quả "sai deck" lại hữu ích: nó buộc phải giải thích bằng cơ chế, và cơ chế
đó dự đoán được hành vi của cả hai stage.

---

## 6. Bonus  *(optional — tối đa 10 điểm)*

> Bỏ trống nếu không làm. Xem `docs/bonus/README.md`. Đừng làm hết — **một** finding sâu
> ăn điểm hơn năm bảng nông.

**Đã làm:** _<B1 build-compare / B2 sweep nào / B4 challenge nào / B5 lựa chọn nào>_

**Numbers:**

```
before:  <số>
after:   <số>
speedup: <X.Y>×
```

**Điều này nói lên gì mà deck chưa nói:**

_(để trống nếu bạn không làm phần này)_

---

## 7. Điều làm bạn ngạc nhiên nhất  *(optional)*

_(1–2 câu. Không bắt buộc, nhưng grader đọc hết.)_

Ngạc nhiên nhất: **decode và prefill có hình dạng thread-sweep ngược nhau trên cùng một
máy** — decode sụp 4.34× từ `-t 4` lên `-t 32`, còn prefill *leo tới `-t 16` rồi mới
phẳng*. Điều này biến "máy tôi bị throttle" (giả thuyết đầu tiên của tôi) thành sai, và
cho thấy `-t` tối ưu phụ thuộc vào *stage nào đang chạy*, không phải một con số cố định.

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
- **Chạy lại phép đo prefill** (`--metric pp512`) để kiểm chứng giả thuyết throttling.

**Toàn bộ số liệu trong báo cáo này do tôi đo trên máy thật của mình** (`make probe/bench/
tune/serve/load/metrics/pipeline`); AI không tạo số. Phần lập luận và kết luận là của tôi,
có đối chiếu lại với output thật đã lưu trong `benchmarks/` và `submission/screenshots/`.
