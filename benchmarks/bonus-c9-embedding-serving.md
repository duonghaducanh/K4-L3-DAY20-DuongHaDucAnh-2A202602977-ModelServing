# Bonus C9 — Embedding serving regime (prefill-bound)

Host `Windows-AMD64` · CPU `Intel Core i7-11800H` · llama.cpp `b10488` ·
`threads=8` · `ngl=0` · model `Qwen3.5-0.8B-Q4_K_M.gguf` served with
`--embedding --pooling mean` on `:8081` (chat GGUF reused as an embedding model —
see the limitation note below).

**Retrieval sanity check** (8-doc corpus, 1024-dim pooled vectors, cosine):

| rank | cosine | document |
|--:|--:|---|
| 1 | 0.897 | Embedding serving is prefill-bound: one forward pass, no KV cache, no decode loop. |
| 2 | 0.850 | RadixAttention reuses a shared prompt prefix across requests via a radix tree. |
| 3 | 0.822 | Speculative decoding drafts several tokens and verifies them in one forward pass. |

The query *"Does embedding serving use a KV cache and a decode loop like chat serving?"*
retrieves the correct doc first (0.897) — the demo is functional.

**Throughput vs static batch size** (one forward pass per text, no decode loop):

| batch | wall (ms) | texts/s | ms/text |
|--:|--:|--:|--:|
| 1 | 552 | 1.81 | 552 |
| 2 | 676 | 2.96 | 338 |
| 4 | 1396 | 2.87 | 349 |
| 8 | 2343 | 3.41 | 293 |
| 16 | 3111 | 5.14 | 194 |
| 32 | 7331 | 4.37 | 229 |

## Your finding

**Embedding serving is prefill-bound, and the batch curve proves it: per-text cost
falls as the static batch grows (552 → 194 ms/text, a 2.8× amortization), because one
forward pass over the weights is shared by every text in the batch — exactly the
opposite of the decode-bound chat endpoint, where batching does not reduce the
per-token cost and throughput is capped by the memory stream.**

**The mechanism, and why the two regimes need opposite batching.** The embedding
endpoint runs *one* forward pass per text and then stops — no KV cache, no autoregressive
decode loop. Every request is pure prefill: a high-arithmetic-intensity, vector-compute-
bound operation. When you send 16 texts at once, the weights are loaded once and reused
16×, so the cost per text drops sharply with batch size (552 ms → 194 ms). This is why
the right knob is a **large static batch** (token-sorted, fixed), not continuous
batching: there is no sequence of steps to interleave, so there is nothing for
continuous batching to schedule — just one big matmul to fill. Contrast the chat
endpoint in `02-server-results.md`: there, each request spends most of its life in the
decode loop, where every step re-streams the whole model from memory for a single token,
so batching helps *throughput* (more requests share a step) but does *not* cut the
per-token cost, and the system saturates when memory bandwidth runs out — which is what
`n_busy_slots_per_decode` and the flat RPS showed.

**Consequence for serving both behind one autoscaler.** A single autoscaler scaling on
CPU/RPS will size the wrong resource: the embedding fleet wants *few, large-batch*
replicas (maximize matmul occupancy per replica), while the chat fleet wants *many*
replicas each holding a few decode slots (hide the per-token memory latency). Sharing
one pool and scaling on a blended metric means one of the two is always mis-sized —
embeddings will look "idle" (low RPS, high batch) and chat will look "saturated" (high
concurrency) at the same CPU load. In production they are usually split into separate
deployments with separate SLOs precisely because their batch curves point in different
directions. The odd point at batch 32 (4.37 texts/s, *slower* per text than batch 16)
is a hint that the static batch has an optimum on this box too: past ~16 texts the
single forward pass's working set spills and one server slot becomes the serialization
point, so bigger is not monotonically better.

**Limitation (stated in the lab, and real).** This demo reuses the chat GGUF
(`Qwen3.5-0.8B`, mean-pooled) as the embedder to avoid an extra download. Mean-pooled
decoder states are a *weak* sentence encoder — the retrieval above works because the
corpus is tiny and lexically distinct. Real retrieval needs a dedicated embedding model
(Qwen3-Embedding, BGE-M3, EmbeddingGemma). The batch-scaling *shape* (prefill-bound,
amortizes with batch) is the general lesson and does not depend on embedder quality;
the absolute cosine values do.