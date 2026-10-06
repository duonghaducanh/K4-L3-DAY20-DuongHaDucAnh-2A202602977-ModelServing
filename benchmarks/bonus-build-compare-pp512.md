# Bonus B1 - Prebuilt vs source build

Host `Windows-AMD64` · CPU `11th Gen Intel(R) Core(TM) i7-11800H @ 2.30GHz`
Vector extensions detected: none
llama.cpp `b10488` both sides · `threads=8` ·
**both pinned to `ngl=0`** so this isolates the compiler ·
metric `pp512`, 3 repetitions

| Binary | Built for | pp512 (tok/s) | Relative |
|:--|--:|--:|--:|
| prebuilt release | runtime CPU dispatch | 244.8 | 1.00x |
| your source build | this CPU (`-DGGML_NATIVE=ON`) | 235.6 | 0.96x |

On this machine, the prebuilt binary is **1.04x faster**.

before: 244.8 tok/s (prebuilt release)
after:  235.6 tok/s (source build, -DGGML_NATIVE=ON)
speedup: 0.96x

Same source revision, same model, same backend, same `-ngl` -- the only difference
is what the compiler was allowed to assume about the CPU.



## Your explanation

**On the more instruction-bound metric the prebuilt wins by 4% — the opposite of the
"compile it yourself for your CPU" story — and the reason is that my source build
traded away its instruction advantage to threading.**

The setup, verified rather than assumed: this i7-11800H (Tiger Lake) has a full AVX-512
stack plus AVX2/FMA. The prebuilt release ships one `ggml-cpu-*.dll` per
microarchitecture and selects the best match by CPUID at load — on this CPU it loads
`ggml-cpu-icelake.dll`, the AVX-512-VNNI kernel. My source build (`-march=native`, zig
clang) statically targets the same AVX-512 instructions, so **the two sides run the
same kernels** and the instruction-set question is a wash. (The header's "extensions:
none" is a Windows detection gap in `probe.py`, which parses Linux `/proc/cpuinfo`.)

Where they differ is **threading**. My build's CMake cache shows
`OpenMP_CXX_FLAGS=NOTFOUND` / `GGML_OPENMP_ENABLED=OFF`: zig's clang ships no `libomp`,
so ggml compiled its non-OpenMP threading path. The prebuilt release ships OpenMP with a
tuned thread pool. On `pp512` — which, unlike decode, does ~512 tokens of work per pass
over the weights and is therefore partly *compute*-bound — the quality of the thread
pool matters: more of the time is spent in parallel arithmetic, so a worse threading
layer costs a measurable few percent (244.8 → 235.6, 0.96x). Decode (`tg128`) is
bandwidth-bound, so the same threading difference barely shows (0.98x); see
`bonus-build-compare-tg128.md`.

**Why the naive expectation fails here.** The bonus assumes a generic prebuilt is slow
and a native build is fast. On a CPU that the release ships a *dedicated* kernel for,
runtime dispatch already delivers the native instructions, so `-DGGML_NATIVE=ON` adds
nothing on the instruction axis — and if the native build happens to be weaker on some
*other* axis (here, OpenMP), it can come out slightly *behind*. The prebuilt winning is
not a paradox; it is what happens when the release's runtime dispatch is as good as a
native build on the axis that matters, and the native build is worse on a second axis.
The actionable takeaway: on a Tiger Lake-class CPU, building from source buys you
nothing for speed; it is worth doing only if you need to change something the prebuilt
can't (a custom quant, a patch, a different backend) — not for raw throughput.
