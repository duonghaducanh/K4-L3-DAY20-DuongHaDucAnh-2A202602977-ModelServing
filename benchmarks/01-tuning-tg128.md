# 01 - Tune: thread-count sweep

Model `Qwen3.5-0.8B-Q4_K_M.gguf` · host `Windows-AMD64` · llama.cpp `b10488`
CPU: **8 physical · 16 logical** cores · `ngl=0` · metric `tg128`

| threads (-t) | tg128 (tok/s) | vs best |
|:--|--:|--:|
| 1 | 12.3 | 61% |
| 4 | 20.2 | 100% |
| 8 | 12.0 | 60% |
| 16 | 8.5 | 42% |
| 32 | 4.7 | 23% |

**Best**: `-t 4` at 20.2 tok/s
**Slowest tested**: `-t 32` at 4.7 tok/s (4.34x spread)
**Against the physical-core default** (`-t 8`, 12.0 tok/s): 1.68x

Use this in your run:

```bash
LAB_N_THREADS=4 make bench
```

## Your explanation

**The knee sits at `-t 4` — *below* this CPU's 8 physical cores — and the curve
falls off a cliff above it.** From 20.2 tok/s at `-t 4`, throughput drops to 12.0 at
`-t 8` (the physical-core default), 8.5 at `-t 16`, and 4.7 at `-t 32` — a 4.34x
spread, worst case at the *most* threads. That is the opposite of the deck's
expected shape (climb to physical cores, then flatten).

First I checked the obvious explanation for a 45 W laptop part: **thermal/power
throttling** under 8-32 busy threads. To separate "the chip is throttling" from
"this stage doesn't scale", I re-ran the identical sweep on the **prefill** metric
(`pp512`, same model, same `ngl=0`):

| threads | 1 | 4 | 8 | 16 | 32 |
|:--|--:|--:|--:|--:|--:|
| `tg128` decode (tok/s) | 12.3 | **20.2** | 12.0 | 8.5 | 4.7 |
| `pp512` prefill (tok/s) | 63.9 | 165.7 | 228.3 | **237.9** | 231.7 |

The two stages have **opposite shapes**. Prefill *keeps climbing* to ~16 threads
and plateaus — it never collapses. If the CPU were throttling under thread load,
prefill would collapse too. It doesn't. So the decode drop is **not** thermal; it
is about what each stage is bound by:

- **Prefill is compute-bound.** It does ~512 tokens of work per pass over the
  weights (high arithmetic intensity), so every extra thread adds real FLOPs. It
  scales to ~physical cores, then flattens.
- **Decode is not compute-bound.** It does ~1 token of work per pass over the same
  weights (arithmetic intensity ≈ 1 FLOP/byte), so it is limited by memory
  latency/bandwidth and by per-step synchronization, not by FLOPs. Four threads
  already saturate what this laptop's memory subsystem can feed a 0.5 GB model;
  past that, every decode step still pays a barrier across *all* threads, so the
  synchronization cost grows while the useful work does not. Throughput falls.

Practical takeaway, and it is metric-dependent: **`-t 4` for decode-heavy serving**
(what this lab serves — `make serve` uses `-t 4`), and `-t 8…16` if you cared about
prefill-heavy work such as long-context RAG ingestion. The default `-t 8` is a
compromise that is best at neither. (Single runs on a laptop — absolute values
drift a few percent run to run, but both curve *shapes* reproduced on every repeat.)

Supporting artifact: `benchmarks/01-tuning-pp512.md`.
