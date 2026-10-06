# 01 - Measure: latency baseline

Model `Qwen3.5 0.8B` · host `Windows-AMD64` · llama.cpp `b10488`
Settings: `threads=4` `ngl=0` `ctx=2048`
`max_tokens=64` · warm-up discarded
Completed requests: `Q4_K_M` 10/10 · `UD-Q2_K_XL` 10/10

| Quantization | Size (GB) | Load (ms) | TTFT P50/P95 (ms) | TPOT P50/P95 (ms) | E2E P50/P95/P99 (ms) | Decode (tok/s) |
|:--|--:|--:|--:|--:|--:|--:|
| Q4_K_M | 0.50 | 3627 | 794 / 1476 | 64.0 / 81.2 | 4636 / 5854 / 5854 | 15.6 |
| UD-Q2_K_XL | 0.39 | 4327 | 1155 / 1705 | 85.3 / 152.0 | 6531 / 10952 / 10952 | 11.7 |

- **TTFT** = prefill. Short prompts keep it small; long-context RAG is where it explodes.
- **TPOT** = per-output-token decode cost, bounded by memory bandwidth. `decode tok/s = 1000 / TPOT_p50`.
- `UD-Q2_K_XL` decodes **1.33x SLOWER** than `Q4_K_M` here, despite being 0.11 GB smaller. That is a real result, not a mistake: fewer bits only buys speed when decode is limited by memory bandwidth. On a machine that is compute-limited instead — few cores, no GPU offload — the extra dequantization work of a heavily-quantized format can cost more than the bytes it saves. Say which case yours is.

## Your observation

**No — the 2-bit model is not worth it on this machine.** `UD-Q2_K_XL` is 0.11 GB
(22%) smaller, but it is **1.33x slower to decode** (11.7 vs 15.6 tok/s), **1.45x
slower to first token** (TTFT P50 1155 vs 794 ms) and **1.41x slower end-to-end**
(E2E P50 6531 vs 4636 ms). Size fell 22%; speed fell 33%. That trade is strictly bad.

Why: this host runs `ngl=0` — **CPU-only, compute-limited**. Decode speed is set by
how fast the cores can dequantize-and-multiply each weight, not by how few bytes
cross the bus. A 2-bit format packs more values per byte, but unpacking it costs
more integer work per weight than the 4-bit K-quants, and there is no GPU to hide
that behind. The 0.11 GB saved buys nothing when bandwidth was never the wall.

I also ran the same prompt on both (`--seed 42`, reasoning off):

- **Q4_K_M** — coherent: *"Continuous batching processes large datasets in parallel,
  allowing the GPU to simultaneously process individual batches…"*
- **UD-Q2_K_XL** — degraded and self-contradictory: *"…reduces the load on GPU
  memory by grouping instances of the same data with a shared state buffer…"* and
  then *"However, continuous batching improves GPU utilization because it reduces
  the number of data points sent to GPU memory…"* — two sentences that contradict
  each other, and neither describes what continuous batching does.

Slower **and** worse. Recommendation: keep `Q4_K_M` as primary; revisit 2-bit only
if RAM is the hard constraint — and it is not (15.7 GB total).
