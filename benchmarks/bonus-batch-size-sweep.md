# Bonus - Batch-size sweep (chunked prefill)

Host `Windows-AMD64` · llama.cpp `b10488` ·
`threads=8` `ngl=0` · metric `pp512`

| -b (logical) | -ub (micro) | pp512 (tok/s) | vs best |
|:--|--:|--:|--:|
| 128 | 128 | 268.4 | 100% |
| 256 | 256 | 264.8 | 99% |
| 512 | 256 | 262.3 | 98% |
| 512 | 512 | 235.1 | 88% |
| 1024 | 512 | 234.0 | 87% |
| 2048 | 512 | 235.7 | 88% |

Best: `-b 128 -ub 128` at 268.4 tok/s
(1.15x the slowest point tested).

This sweep only measures the throughput half of the trade. The cost it hides is
TTFT for queued requests: a larger micro-batch holds the device longer per step,
so anything waiting behind it waits longer. To see both halves, re-run
`make load-50` with your best and worst settings via
`.venv/bin/python labs/02-serve/serve.py -- -b N -ub M` and compare P95.

## Your finding

**I would run `-b 128 -ub 128`, and here the throughput-optimal point is also the
latency-optimal one — which is the opposite of what the deck's chunked-prefill slide
implies.**

The result inverts the expected trade. Chunked prefill is normally framed as "bigger
chunks amortize per-step overhead → more throughput, but worse TTFT for whatever is
queued behind the chunk." On this host, bigger chunks buy **no** throughput: the
smallest micro-batch (`-ub 128`) is the fastest at 268.4 tok/s, and `-ub 512` is ~12%
**slower** (235 tok/s). The knob that actually matters is `-ub` (the physical
micro-batch), not `-b` (the logical batch): rows 3 vs 4 differ only in `-ub` (256 vs
512) and that alone costs 262 → 235 tok/s, while widening `-b` 512→2048 at fixed `-ub
512` changes nothing (235.1 → 235.7, inside noise).

**Mechanism:** on a CPU-only box at these sizes the per-step launch overhead the deck
wants you to amortize is already negligible — there is no kernel-launch pipeline to
hide. What a larger micro-batch *does* cost is a wider working set: `-ub 512` streams
2× the activations per step through the same 24 MB of L3, so the layer weights and
activations evict each other and cache residency drops. And a bigger batch adds no
parallelism here, because prefill is *already* spread across all 8 threads — the batch
dimension is not free extra work in flight, it is more data competing for the same
bandwidth. So `-ub 512` is pure loss on this machine.

**What I would still need to measure before trusting this in production:** `llama-bench`
prefills one prompt in isolation, so it cannot see queueing. A smaller micro-batch also
means *more, shorter* prefill steps, which under `--parallel 4` interleave more finely
with ongoing decode steps — plausibly *helping* the P95 of a contended server, but the
sweep above does not prove it. The confirming experiment is to serve with the best and
worst settings and re-run `make load-50`:

```bash
.venv/bin/python labs/02-serve/serve.py -- -b 128 -ub 128     # then: make load-50
.venv/bin/python labs/02-serve/serve.py -- -b 512 -ub 512     # then: make load-50
```

and compare P95 and TTFT, not throughput. Only if P95 is flat or better do I get to
keep the throughput win for free. (Note the absolute spread is small — 1.15x — so the
honest headline is "micro-batch size is the real knob, and smaller wins here", not a
large speedup.)
