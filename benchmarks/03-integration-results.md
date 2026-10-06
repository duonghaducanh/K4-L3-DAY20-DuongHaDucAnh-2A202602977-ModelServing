# 03 - Integrate: RAG pipeline run

Host `Windows-AMD64` · llama.cpp `b10488` ·
retrieval backend: **keyword overlap** · 3 queries

| Query | Contexts retrieved | embed (ms) | retrieve (ms) | llm (ms) | total (ms) |
|:--|--:|--:|--:|--:|--:|
| Why is goodput more useful than raw throughp... | goodput, paged, radix | 0.0 | 0.1 | 11193.0 | 11193.2 |
| What problem does PagedAttention actually so... | paged, radix, disagg | 0.0 | 0.1 | 5928.9 | 5929.0 |
| When does splitting prefill and decode help?... | disagg, radix, batching | 0.0 | 0.1 | 7578.2 | 7578.4 |

Mean per stage (ms): embed **0.0** · retrieve **0.1** ·
llm **8233.4** · total **8233.5**
Dominant stage: **llm** (100% of total)

## Answers returned

**Why is goodput more useful than raw throughput?**

> Based on the context provided, **Goodput** is more useful than raw throughput because it focuses on the specific metrics that define a system's reliability and performance under real-world conditions.

According to the text:
*   **Goodput** counts requests per second that met the **TTFT** (Total Throughput) and **TPOT** (Total Throughput with Overhead) targets.
*   It explicitly states that **thro

**What problem does PagedAttention actually solve?**

> PagedAttention solves the problem of **internal fragmentation in GPU memory** caused by storing key-value pairs in non-contiguous pages. By organizing the KV cache into separate pages, it removes the wasted space that would otherwise be consumed by the internal fragmentation of contiguous memory blocks.

**When does splitting prefill and decode help?**

> Splitting prefill and decode helps when **prefill is compute-bound and decode is memory-bound**.

This occurs because the context explicitly states that prefilling the model requires significant computation (often on GPU cores), while decoding requires significant memory bandwidth. By splitting these operations into separate pools (prefill and decode), the system can utilize different hardware res


## Which N16-N19 pieces are real

| Day | Piece | Real or stub? |
|---|---|---|
| N16 Cloud/IaC | **stub** — no cloud/IaC; everything ran locally on the laptop |
| N17 Data pipeline | **stub** — no ingestion pipeline; 6 hardcoded `TOY_DOCS` |
| N18 Lakehouse | **stub** — a Python list of dicts, not a lakehouse |
| N19 Vector + features | **stub** — retrieval backend is `keyword overlap` (token scoring), not a vector index; `embed = 0.0 ms` because no embedding server ran |
| N20 Serving | **real** — `llama-server` (`b10488`), OpenAI-compatible, continuous batching |

So of N16–N19, **none are real**; only N20 is. The pipeline proves the serving
endpoint end-to-end, but the retrieval half is a stub — the answers come from the
model plus six toy documents, not from an embedded/vector-retrieved corpus.

**Is the dominant stage what I expected?** Yes, but the margin is starker than I
expected. `llm` is **8233.4 of 8233.5 ms = 100%** of total; embed (0.0 ms) and
retrieve (0.1 ms) are rounding error — three orders of magnitude below generation.
I expected the LLM to dominate, but I did not expect retrieval to be *free*: on a
real vector backend with embeddings, embed + retrieve would move from ~0.1 ms to
tens of ms — still small next to 8.2 s of CPU decode.

**To halve this pipeline's latency I would attack `llm`, and only `llm`.** Shaving
retrieval by 100% saves 0.1 ms out of 8233.5 ms — invisible. The levers that
actually move `llm`: (1) **GPU offload** — this host has an RTX 3070 Laptop sitting
idle at `ngl=0`, the single biggest available win; (2) **cap `max_tokens`** — the two
long answers alone cost ~9-11 s; (3) a shorter prompt/context to cut prefill. I
would try (1) first, because it attacks the 100% stage at its root instead of
trimming around it.
