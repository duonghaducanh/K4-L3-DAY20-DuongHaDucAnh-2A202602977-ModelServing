# 01 - Tune: thread-count sweep

Model `Qwen3.5-0.8B-Q4_K_M.gguf` · host `Windows-AMD64` · llama.cpp `b10488`
CPU: **8 physical · 16 logical** cores · `ngl=0` · metric `pp512`

| threads (-t) | pp512 (tok/s) | vs best |
|:--|--:|--:|
| 1 | 63.8 | 25% |
| 4 | 166.1 | 65% |
| 8 | 228.8 | 90% |
| 16 | 254.5 | 100% |
| 32 | 238.0 | 94% |

**Best**: `-t 16` at 254.5 tok/s
**Slowest tested**: `-t 1` at 63.8 tok/s (3.99x spread)
**Against the physical-core default** (`-t 8`, 228.8 tok/s): 1.11x

Use this in your run:

```bash
LAB_N_THREADS=16 make bench
```

## Your explanation

**Prefill keeps climbing past the physical cores and peaks at `-t 16` — the opposite
of decode.** Throughput goes 63.8 → 166.1 → 228.8 → **254.5** → 238.0 as threads go
1 → 4 → 8 → 16 → 32. The knee is at the *logical* core count (16), not the physical
one (8), and the fall past it is gentle (238 vs 254, ~6%) — nothing like decode's
cliff.

**Why the knee is at 16 here.** Prefill processes ~512 tokens per pass over the
weights, so its arithmetic intensity is high (many FLOPs per byte loaded) — it is
**compute-bound, not bandwidth-bound**. Every thread adds real arithmetic work, so it
scales past the physical cores; the hyperthreads help because a memory-bound core
stalls on cache misses and its sibling can issue arithmetic in those bubbles. It
flattens (rather than dropping hard) at 32 because by then the memory subsystem is
finally the limit and the extra threads only add a little sync/contention overhead.

**Why this is worth reporting next to decode.** The same machine, same model, same
`ngl=0` gives two different optimal thread counts: `-t 8` for decode (`tg128` peaks
there, then collapses) and `-t 16` for prefill (`pp512` peaks there). Decode is
bandwidth-bound so it saturates at the physical cores; prefill is compute-bound so it
saturates at the logical cores. Tuning `-t` for "the model" is therefore the wrong
frame — you tune it for the *stage* that dominates your workload. This lab's serving
path is decode-heavy, so `-t 8` is the right default; a long-context RAG ingestion job
would want `-t 16`. Full reasoning in `benchmarks/01-tuning-tg128.md`.
