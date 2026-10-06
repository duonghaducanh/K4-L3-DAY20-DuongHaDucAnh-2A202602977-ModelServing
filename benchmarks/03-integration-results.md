# 03 - Integrate: RAG pipeline run

Host `Windows-AMD64` · llama.cpp `b10488` ·
retrieval backend: **keyword overlap** · 3 queries

| Query | Contexts retrieved | embed (ms) | retrieve (ms) | llm (ms) | total (ms) |
|:--|--:|--:|--:|--:|--:|
| Why is goodput more useful than raw throughp... | goodput, paged, radix | 0.0 | 0.0 | 4766.0 | 4766.0 |
| What problem does PagedAttention actually so... | paged, radix, disagg | 0.0 | 0.0 | 3633.1 | 3633.2 |
| When does splitting prefill and decode help?... | disagg, radix, batching | 0.0 | 0.0 | 4157.7 | 4157.8 |

Mean per stage (ms): embed **0.0** · retrieve **0.0** ·
llm **4185.6** · total **4185.7**
Dominant stage: **llm** (100% of total)

## Answers returned

**Why is goodput more useful than raw throughput?**

> Goodput is more useful than raw throughput because it **only counts requests that met the Target Time-to-Fullness (TTFT) and Target Time-to-Poll (TPOT) targets**, while ignoring requests that do not meet these targets.

In contrast, raw throughput often suffers from "saturation," where the system becomes so full that it ignores SLOs (Service Level Objectives) and only counts requests that are acti

**What problem does PagedAttention actually solve?**

> PagedAttention solves the problem of **internal fragmentation in GPU memory** caused by storing the key-value cache (KV cache) in non-contiguous pages.

By doing so, it removes the wasted space that would otherwise be occupied by the internal fragmentation of contiguous memory blocks.

**When does splitting prefill and decode help?**

> Based on the context provided, splitting prefill and decode helps when **prefill is compute-bound and decode is memory-bandwidth-bound**.

The context explicitly states that prefill is compute-bound and decode is memory-bandwidth-bound. By splitting them, the system allows the engine to skip prefill entirely when a shared prefix exists (as in RadixAttention), thereby improving performance.


## Which N16-N19 pieces are real

| Day | Piece | Real or stub? |
|---|---|---|
| N16 Cloud/IaC | **stub** — no cloud/IaC; everything ran locally on the laptop |
| N17 Data pipeline | **stub** — no ingestion pipeline; 6 hardcoded `TOY_DOCS` |
| N18 Lakehouse | **stub** — a Python list of dicts, not a lakehouse |
| N19 Vector + features | **stub** — retrieval backend is `keyword overlap` (token scoring), not a vector index; `embed = 0.0 ms` because no embedding server ran |
| N20 Serving | **real** — `llama-server` (`b10488`), OpenAI-compatible, continuous batching |

**Is the dominant stage what I expected?** Yes, and more extreme than expected: the LLM
stage is **4185.6 ms of a 4185.7 ms total — 100%** — while embed (0.0) + retrieve (0.0)
together are under 0.1 ms. The retrieval half is a pure stub, so of course it costs
nothing. What *was* worth seeing: the server's own timings show the split *inside* the
LLM stage — e.g. query 1 is **prefill 151 tok / 456 ms** + **decode 116 tok / 2070 ms**,
so decode dominates even at a ~150-token prompt, and the total (4.8 s) tracks the
generated-token count (200 `max_tokens`) far more than the prompt.

**If I had to halve the latency, I would attack the LLM stage — specifically the decode
side.** Nothing else is on the table: fixing retrieval cannot help a stage that costs
0.1 ms. Within the LLM stage the lever is `max_tokens` / output length (decode is
~18 ms/token here, so the 200-token cap is ~3.6 s of the 4.2 s), then GPU offload — the
RTX 3070 is idle at `ngl=0` because the prebuilt CUDA backend fails to load on this
machine (missing CUDA runtime DLLs), which is the single largest untapped speedup. Short
of that, shortening retrieved context does little here because the prompts are already
tiny (~113–151 tokens of prefill); the cost is generation, not context.
