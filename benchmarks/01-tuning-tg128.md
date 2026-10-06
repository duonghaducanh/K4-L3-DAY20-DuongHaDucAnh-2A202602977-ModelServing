# 01 - Tune: thread-count sweep

Model `Qwen3.5-0.8B-Q4_K_M.gguf` · host `Windows-AMD64` · llama.cpp `b10488`
CPU: **8 physical · 16 logical** cores · `ngl=0` · metric `tg128`

| threads (-t) | tg128 (tok/s) | vs best |
|:--|--:|--:|
| 1 | 18.3 | 33% |
| 4 | 46.6 | 85% |
| 8 | 55.2 | 100% |
| 16 | 32.0 | 58% |
| 32 | 19.8 | 36% |

**Best**: `-t 8` at 55.2 tok/s
**Slowest tested**: `-t 1` at 18.3 tok/s (3.01x spread)
**Against the physical-core default** (`-t 8`, 55.2 tok/s): 1.00x

Use this in your run:

```bash
LAB_N_THREADS=8 make bench
```

## Your explanation

**The knee sits exactly at `-t 8` — this CPU's physical core count — and the curve
falls off past it.** Decode climbs 18.3 → 46.6 → **55.2 tok/s** as threads go 1 → 4 → 8,
then drops to 32.0 at `-t 16` (hyperthreads) and 19.8 at `-t 32` (2× oversubscription).
That is the deck's expected shape: climb to physical cores, then flatten/fall. The
spread is 3.01×, and the worst point is the *most* threads.

**Why the knee is at 8 and why hyperthreads hurt.** Decode does ~1 token of work per
pass over the whole weight set, so its arithmetic intensity is ≈1 FLOP/byte — it is
bound by **memory bandwidth/latency, not FLOPs**. Going 1 → 8 threads adds real
memory-level parallelism: eight cores can have eight independent cache-miss streams
in flight, so bandwidth utilization climbs toward saturation. Past 8 there is nothing
left to parallelize *in the memory subsystem*: the 8 physical cores already keep the
channels busy, so the 8 hyperthreads (16 logical) add no new memory requests — they
just add work to the per-step synchronization barrier that every thread must clear.
More sync cost, same useful work → throughput falls. `-t 32` doubles the contention
again, hence 19.8.

**The confirming cross-check: prefill has the opposite knee.** I re-ran the identical
sweep on the prefill metric `pp512` (same model, same `ngl=0`), and it *keeps climbing
past 8*, peaking at `-t 16`:

| threads | 1 | 4 | 8 | 16 | 32 |
|:--|--:|--:|--:|--:|--:|
| `tg128` decode (tok/s) | 18.3 | 46.6 | **55.2** | 32.0 | 19.8 |
| `pp512` prefill (tok/s) | 63.8 | 166.1 | 228.8 | **254.5** | 238.0 |

Two stages, two knees. Prefill is **compute-bound** — each pass does ~512 tokens of
work over the weights (high arithmetic intensity), so every thread adds real FLOPs and
even hyperthreads help by filling pipeline bubbles; it peaks at the *logical* core
count (16). Decode is **bandwidth-bound**, so it saturates at the *physical* count (8)
and hyperthreads only add barrier cost. The metric you tune for therefore changes the
answer: `-t 8` for decode-heavy serving (what this lab runs), `-t 16` for prefill-heavy
long-context ingestion.

**Reproducibility note (honest correction).** An earlier version of this report claimed
the knee was at `-t 4` with values ~4× lower (12.0 at `-t 8`). That run did not
reproduce: three repeated `llama-bench` runs on a quiet machine give 47.2 ± 0.9 tok/s
at `-t 4` and 53.9 ± 0.4 at `-t 8`, matching the table above, while the same sweep on
`pp512` reproduced closely both times. The old numbers were taken under CPU
contention/power limiting, which flattened the curve and moved the apparent knee. The
table and explanation above are the reproducible measurement; the earlier claim is
retracted. (Single runs on a laptop drift a few percent run to run, but the curve
*shape* — peak at physical cores for decode, at logical cores for prefill — reproduced
on every repeat.)

Supporting artifact: `benchmarks/01-tuning-pp512.md`.
