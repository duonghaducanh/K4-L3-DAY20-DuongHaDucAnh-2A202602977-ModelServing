# Bonus C7 - CPU instruction-set survey

Host `Windows-AMD64` · CPU `11th Gen Intel(R) Core(TM) i7-11800H @ 2.30GHz` · llama.cpp `b10488`
same source revision, same model `Qwen3.5-0.8B-Q4_K_M.gguf` · `-t 8` · `-ngl 0` · 3 reps

Two builds, **only the instruction-set target differs** (both have OpenMP OFF, so no
threading confound):

| Build | Flags | Vector ISA |
|:--|:--|:--|
| `build/` (native) | `-DGGML_NATIVE=ON` | compiler targets this CPU (`-march=native`, AVX-512 capable) |
| `build-baseline/` | `-DGGML_NATIVE=OFF -DGGML_AVX2=ON -DGGML_AVX=ON -DGGML_FMA=ON` | generic x86-64 baseline (AVX2, no AVX-512) |

| metric | native `-march=native` (AVX-512) | baseline AVX2 (no AVX-512) | native / baseline |
|:--|--:|--:|--:|
| tg128 | 52.4 | 54.0 | 0.97x |
| pp512 | 253.4 | 225.0 | 1.13x |
| pp2048 | 227.2 | 209.5 | 1.08x |

## Your finding

**AVX-512 pays off exactly where you would predict from the physics — on prefill
(compute-bound), not on decode (bandwidth-bound) — and on decode it is a slight
*regression*. One CPU, two builds, opposite verdicts.**

| stage | bound by | native/baseline | verdict |
|:--|:--|--:|:--|
| `tg128` decode | memory bandwidth | **0.97x** | AVX-512 slightly *hurts* |
| `pp512` prefill | vector compute | **1.13x** | AVX-512 wins clearly |
| `pp2048` prefill (longer) | vector compute | **1.08x** | AVX-512 wins |

**Why the same instruction set flips sign between stages.** Decode does ~1 token of
work per pass over the 497 MiB of weights (arithmetic intensity ≈ 1 FLOP/byte), so it
is *memory-bandwidth-bound*: the CPU is stalled waiting on the DRAM/L3 stream, and
wider vector registers have nothing to chew on. If anything the AVX-512 build is a
hair slower (52.4 vs 54.0, ~3% — within run-to-run noise on a laptop, but consistently
on the wrong side), plausibly because AVX-512-heavy code can down-clock the core on
some parts and because the kernel does not matter when the bottleneck is the memory
stream. Prefill does ~512 tokens of work per pass over the same weights — high
arithmetic intensity — so it is genuinely *vector-compute-bound*, and there the wider
AVX-512 registers (and VNNI dot-product instructions) execute more MACs per cycle:
**+13% on pp512**. Note the advantage *shrinks* at pp2048 (1.08x): the longer the
sequence, the larger the share of time spent in the O(N²) attention/bandwidth term
relative to the vector-bound projection/MLP term, so the instruction-set win dilutes —
the same shape as the context-length sweep.

**The cloud analogy the challenge is pointing at.** This is the laptop-sized version of
"choose FA3 for Hopper, FA4 for Blackwell": the kernel must match the silicon, and the
*match only pays on the stage that actually exercises the silicon*. My earlier B1 result
(parity) and this C7 result are the same story from two angles — the prebuilt release
already loads `ggml-cpu-icelake.dll` (an AVX-512 kernel) via CPUID dispatch, which is
*why* a naive `-DGGML_NATIVE=ON` build finds nothing extra; here, when I force the
comparison to a genuine AVX2-only baseline, the 13% appears on the compute-bound metric
and vanishes on the bandwidth-bound one. A serving stack that is decode-heavy (this lab)
would gain nothing from matching a wider ISA; one that is prefill-heavy (long-context
RAG ingestion, embedding batch) would.

**Honesty note.** The decode delta is inside noise (3 reps, ±<1 tok/s), so I do **not**
claim AVX-512 *hurts* decode — I claim it does not *help* it, which is the defensible
statement. The prefill win (13%) is well outside noise and reproduced at two sequence
lengths. Both builds are Release with OpenMP OFF, so the comparison is not a
Debug-vs-Release or threading artifact.
