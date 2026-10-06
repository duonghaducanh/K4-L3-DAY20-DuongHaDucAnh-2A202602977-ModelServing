# 01 - Tune: thread-count sweep

Model `Qwen3.5-0.8B-Q4_K_M.gguf` · host `Windows-AMD64` · llama.cpp `b10488`
CPU: **8 physical · 16 logical** cores · `ngl=0` · metric `pp512`

| threads (-t) | pp512 (tok/s) | vs best |
|:--|--:|--:|
| 1 | 63.9 | 27% |
| 4 | 165.7 | 70% |
| 8 | 228.3 | 96% |
| 16 | 237.9 | 100% |
| 32 | 231.7 | 97% |

**Best**: `-t 16` at 237.9 tok/s
**Slowest tested**: `-t 1` at 63.9 tok/s (3.73x spread)
**Against the physical-core default** (`-t 8`, 228.3 tok/s): 1.04x

Use this in your run:

```bash
LAB_N_THREADS=16 make bench
```

## Your explanation

This is the **prefill** counterpart to `01-tuning-tg128.md` (decode), run on the
same model and host to answer one question: *is the decode collapse at high thread
counts thermal throttling, or is it stage-specific?* Prefill keeps climbing to
`-t 16` and plateaus — it never collapses — so the CPU is not throttling under
thread load, and the decode drop must be about decode being memory/sync-bound while
prefill is compute-bound. Full reasoning is in `01-tuning-tg128.md`.

Absolute values here are noisier than the decode sweep (repeat runs spread a few
percent as the laptop's clocks settle); the *shape* — monotonic climb, plateau
around 8-16 threads, no collapse — reproduced on every repeat.
