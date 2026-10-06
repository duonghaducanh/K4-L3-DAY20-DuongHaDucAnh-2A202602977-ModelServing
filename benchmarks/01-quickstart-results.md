# 01 - Measure: latency baseline

Model `Qwen3.5 0.8B` · host `Windows-AMD64` · llama.cpp `b10488`
Settings: `threads=8` `ngl=0` `ctx=2048`
`max_tokens=64` · warm-up discarded
Completed requests: `Q4_K_M` 10/10 · `UD-Q2_K_XL` 10/10

| Quantization | Size (GB) | Load (ms) | TTFT P50/P95 (ms) | TPOT P50/P95 (ms) | E2E P50/P95/P99 (ms) | Decode (tok/s) |
|:--|--:|--:|--:|--:|--:|--:|
| Q4_K_M | 0.50 | 2610 | 336 / 381 | 20.5 / 24.1 | 1549 / 1852 / 1852 | 48.8 |
| UD-Q2_K_XL | 0.39 | 1440 | 403 / 433 | 18.7 / 24.4 | 1582 / 1730 / 1730 | 53.4 |

- **TTFT** = prefill. Short prompts keep it small; long-context RAG is where it explodes.
- **TPOT** = per-output-token decode cost, bounded by memory bandwidth. `decode tok/s = 1000 / TPOT_p50`.
- `UD-Q2_K_XL` decodes **1.09x faster** than `Q4_K_M` here, for 0.11 GB less on disk.

## Your observation

**On this machine the smaller quantization is *not* worth it — the speed is a tie and
the quality is slightly worse.** This run shows Q4_K_M at 48.8 tok/s and UD-Q2_K_XL at
53.4 tok/s, i.e. Q2 *faster* by 1.09× — but that direction does not survive repetition.
A 5-rep `llama-bench` comparison gives **52.05 ± 0.87 (Q4) vs 52.40 ± 2.50 (Q2)**:
statistically equal. The two formats are within run-to-run noise of each other in both
directions, so the honest reading is **no speed difference**. The 2-bit model is 22%
smaller on disk and buys **no** decode speedup, while giving up quality.

**Which case is my machine?** The header says it: `ngl=0` — CPU-only, no GPU offload.
Fewer bits only buy speed when decode is limited by *memory bandwidth* (the bytes you
must stream per token). Here decode runs at ~52 tok/s either way, which tells me the
bottleneck is not the byte count — it is the per-token compute/dequantization work, and
a 2-bit format needs *more* dequant work per weight, not less. On a bandwidth-bound
machine (GPU offload, or a much larger model where weights dominate) the 2-bit version
would pull ahead; on this compute-limited laptop it does not.

**Quality check (my own, `--temp 0`, 7 prompts — arithmetic, JSON extraction,
instruction-following, a fact, a syllogism):** Q4_K_M scored **5/7**, UD-Q2_K_XL scored
**4/7**. The decisive one: asked "What is the capital of France? One word.", Q4 answered
`Paris` and Q2 answered `Bun.` — a confident non-answer. Both failed the arithmetic and
syllogism prompts (this 0.8B model is simply weak there), so the *marginal* damage from
2-bit is one extra confidently-wrong answer out of seven.

**Verdict:** deploy **Q4_K_M**. The 22% disk saving of UD-Q2_K_XL buys nothing on this
CPU-only box and costs measurable quality. Size and speed are measurable and here they
say "no"; usefulness — my call — agrees.
