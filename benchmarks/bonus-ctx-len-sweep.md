# Bonus - Context-length sweep (prefill cost)

Host `Windows-AMD64` · llama.cpp `b10488` ·
`threads=8` `ngl=0` · RAM 15.7 GB

| Prompt tokens | Prefill (tok/s) | TTFT contribution (ms) | vs linear scaling |
|:--|--:|--:|--:|
| 256 | 265.2 | 965.4 | 1.00x |
| 1024 | 235.5 | 4347.6 | 1.13x |
| 2048 | 223.3 | 9169.9 | 1.19x |
| 4096 | 209.1 | 19591.5 | 1.27x |
| 8192 | 193.4 | 42351.2 | 1.37x |

At 8192 tokens, prefill costs **42351 ms** --
1.37x what linear scaling from the smallest point would predict. That excess
is attention's O(N^2) term becoming visible, and every millisecond of it lands in TTFT
before the user sees a single token.

Either way, this is the number to remember when someone proposes stuffing more retrieved
context into a RAG prompt "because the context window allows it". Prefill is paid in full,
on every request, before the first token appears.

## Your finding

**Prefill dominates from ~1024 tokens up, and the quadratic bend is real but gentle here.**

The "vs linear" column climbs monotonically — 1.00 → 1.13 → 1.19 → 1.27 → **1.37x** — so
this is not a flat range: attention's O(N²) term is measurably present, adding 37% on top
of linear at 8192 tokens. But there is no sharp knee; the extra cost accrues steadily. On a
0.8B model the O(N) projection/MLP terms are still large enough that the quadratic term
only *gradually* overtakes them, so the curve looks like a slow bend rather than the
hockey-stick the deck's O(N²) shorthand implies. Doubling the prompt never doubles prefill
time exactly, but over 256→8192 it is nowhere near 32x either (it is 44x the smallest
point's *time* for 32x the tokens — i.e. 1.37x, not the ~1.0x a purely linear regime would
give).

**Where it dominates end-to-end:** decode on this host runs ~52 tok/s ≈ 19 ms/token, so a
100-token answer costs ~1.9 s. Prefill passes that at roughly **1024 tokens (4.3 s) and
leaves it far behind by 2048 (9.2 s)**. Past ~1K tokens of context, TTFT — not generation —
is the term you are paying for, and it is paid in full on *every* request before the first
token appears.

**What that means for the RAG pipeline:** at 2048 tokens a single query costs 9.2 s of
prefill alone; at 8192 it is 42.4 s. The pipeline in `03-integration-results.md` used six
tiny toy docs (~150-token prompts) and spent 100% of its 4.2 s in the LLM stage — and even
there, decode (not prefill) dominated, because the prompts were small. With realistic
chunks (~300–500 tokens each), I can afford **at most ~2–4 chunks** before prefill swamps
everything else on this CPU-only box — and that budget is a *latency* choice, not a
context-window one. The 8192-token window does not mean 8192 tokens of retrieved context
are free; it means each one is paid at 5.2 ms/token, super-linearly.
