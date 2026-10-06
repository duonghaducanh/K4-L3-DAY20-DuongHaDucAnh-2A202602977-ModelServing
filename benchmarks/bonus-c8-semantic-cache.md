# Bonus C8 — Semantic cache diagnosis (weak embedder)

Host `Windows-AMD64` · llama.cpp `b10488` · chat server `:8090` (`Qwen3.5-0.8B-Q4_K_M`) ·
embedding server `:8081` (`--embedding --pooling mean`, same chat GGUF) ·
8-prompt stream, 1024-dim pooled vectors, cosine similarity.

The lab has **no dedicated embedding model**, so `make serve-embed` runs the chat model
in pooling mode. The docs warn this is a weak sentence encoder and ask for a
**diagnosis**, not a hit rate. Here it is.

## Pairwise cosine similarity matrix (rows/cols = prompts 1–8)

```
        #1     #2     #3     #4     #5     #6     #7     #8
#1 goodput 1.00   0.86   0.90   0.85   0.85   0.89   0.86   0.85
#2 ttft    0.86   1.00   0.86   0.77   0.83   0.84   0.77   0.87
#3 goodput 0.90   0.86   1.00   0.81   0.83   0.91   0.80   0.84
#4 ttft    0.85   0.77   0.81   1.00   0.79   0.76   0.86   0.77
#5 paged   0.85   0.83   0.83   0.79   1.00   0.78   0.81   0.95
#6 goodput 0.89   0.84   0.91   0.76   0.78   1.00   0.75   0.83
#7 prefix  0.86   0.77   0.80   0.86   0.81   0.75   1.00   0.81
#8 paged   0.85   0.87   0.84   0.77   0.95   0.83   0.81   1.00
```

True paraphrases: #3,#6 → #1; #4 → #2; #8 → #5. **#7 is a new topic (prefix caching).**

## Threshold sweep — no single threshold separates the two error types

| threshold | false hits (wrong answer returned) | false misses (true paraphrase not caught) |
|--:|--:|--:|
| 0.80 | 5 | 0 |
| 0.85 | 5 | 0 |
| 0.88 | 0 | 1 |
| 0.90 | 0 | 2 |
| 0.92 | 0 | 3 |

## Your finding

**A false hit.** At threshold 0.85, prompt **#5 "How does PagedAttention work?"** hits
the cached answer for **#1 "What is goodput at SLO?"** at similarity **0.85** — an
*unrelated* topic returning a *wrong* answer with zero compute. The same happens to #7
("What is prefix caching?", similarity 0.86 vs #1) and #2 ("Explain TTFT and TPOT.",
0.86 vs #1). The naive cache reports a **88% hit rate** — and 5 of those 7 "hits" are
wrong answers.

**A false miss.** The genuine paraphrase **#4 "What does time to first token mean?"**
should match **#2 "Explain TTFT and TPOT."**, but their similarity is only **0.77** —
below every threshold that suppresses the false hits.

**No single threshold fixes both.** This is the decisive part, and the matrix shows why
in one line:

> similarity(#4 → #2, a **true** paraphrase) = **0.77**
> similarity(#5 → #1, an **unrelated** prompt) = **0.85**

The unrelated pair scores **higher** than the genuine paraphrase. The two distributions
are *inverted*, not merely overlapping, so there is no cutoff `t` where "true
paraphrases score above `t`" and "unrelated prompts score below `t`" both hold. The
sweep confirms it mechanically: at t=0.80/0.85 you get 5 false hits and 0 false misses;
drop to t=0.88 and you get 0 false hits but start losing true paraphrases; by t=0.92 you
have 0 false hits and 3 false misses. You can buy either error rate down, never both.

**Why a next-token-prediction decoder is a bad sentence encoder.** A decoder LLM is
trained to predict the next token given a *causal* prefix, so its hidden state at the
last position is optimized to carry whatever the *next token* needs — not a
semantically-centered summary of the whole input. Mean-pooling those causal states
across tokens (as this demo does) mixes states that each saw a different amount of
context, and the result is dominated by surface features: token overlap, length,
generic "what/how" framing. That is why *every* pair here lands in a narrow band
(0.75–0.95) and why an unrelated question can outscore a real paraphrase. A dedicated
embedding model (Qwen3-Embedding, BGE-M3, EmbeddingGemma) is trained with a *contrastive*
objective — explicitly pulling paraphrases together and pushing unrelated pairs apart —
so it produces a wide gap (true paraphrases ~0.85–0.95, strangers ~0.1–0.4) that a
single threshold *can* separate. The failure above is not a tuning bug; it is the
predictable consequence of using a decoder as an encoder.

**Security note (the deck's timing side channel).** Sharing a semantic or prefix cache
across users leaks information: a cache HIT returns in ~0 ms while a MISS pays full
prefill+decode (here ~4.2 s on the first request), so response latency reveals whether
*another user* previously asked a similar question — a timing oracle over private
prompts (NDSS'25). Production caches salt the key per tenant so a user's hit can only be
driven by their own history.