# Bonus B1 - Prebuilt vs source build

Host `Windows-AMD64` · CPU `11th Gen Intel(R) Core(TM) i7-11800H @ 2.30GHz`
Vector extensions detected: none
llama.cpp `b10488` both sides · `threads=8` ·
**both pinned to `ngl=0`** so this isolates the compiler ·
metric `tg128`, 3 repetitions

| Binary | Built for | tg128 (tok/s) | Relative |
|:--|--:|--:|--:|
| prebuilt release | runtime CPU dispatch | 53.8 | 1.00x |
| your source build | this CPU (`-DGGML_NATIVE=ON`) | 52.7 | 0.98x |

On this machine, **they are within 3% -- no meaningful difference**.

before: 53.8 tok/s (prebuilt release)
after:  52.7 tok/s (source build, -DGGML_NATIVE=ON)
speedup: 0.98x

Same source revision, same model, same backend, same `-ngl` -- the only difference
is what the compiler was allowed to assume about the CPU.
A gap this small usually means the prebuilt binary already dispatches to the right kernels at runtime (releases ship one libggml-cpu-*.so per microarchitecture and pick via CPUID), or that this workload is bandwidth-bound rather than instruction-bound. Both are real findings -- say which one you think it is.


## Your explanation

**The gap is ~0 because the prebuilt is *already* running AVX-512 kernels — there is
nothing left for `-march=native` to add — and what is left is a small threading
difference, not an instruction-set one.**

I verified both sides instead of guessing. This i7-11800H is a Tiger Lake part with a
full AVX-512 stack (`avx512f/dq/bw/cd/vl/vnni/vbmi2/bitalg/vpopcntdq/vp2intersect`)
plus AVX2 and FMA. (The report header says "Vector extensions detected: none" — that
is a Windows detection gap in `probe.py`, which reads Linux `/proc/cpuinfo`; the
instructions are definitely present, as confirmed directly below.)

- **Prebuilt side:** it prints which backend it picked at load time —
  `load_backend: loaded CPU backend from ...\ggml-cpu-icelake.dll`. The release ships
  one `ggml-cpu-*.dll` per microarchitecture (`alderlake`, `cannonlake`, `haswell`,
  `icelake`, `skylakex`, `zen4`, `sse42`, `x64`, …) and selects the best match via
  CPUID at runtime. Tiger Lake resolves to the **Ice Lake / AVX-512-VNNI** kernel.
- **Source side:** `compile_commands.json` shows my build was compiled with
  `-march=native` (I used zig's clang), so it statically targets that same AVX-512
  path — there is no `ggml-cpu-*.dll` in the source build at all; the kernels are baked
  into the binary.

So both binaries issue the *same* vector instructions over the *same* weights. The
prebuilt's runtime dispatch handed it exactly the "compiled for your CPU" advantage
this bonus is about — for free. That is why the two land within 3% (53.8 vs 52.7
tok/s, 0.98x).

**Why the decode metric can't show a compiler gap anyway.** Decode (`tg128`) is
memory-bandwidth-bound, not instruction-bound: ~1 token of work per pass over the 497
MiB of weights (arithmetic intensity ≈ 1 FLOP/byte), so it waits on the memory stream,
not on vector ALU throughput. Even a binary with *faster* SIMD would have no spare
instruction throughput to exploit — the DRAM/L3 stream is the bottleneck and it is
identical for both.

**The residual ~2–4% is a threading difference, not the compiler.** My source build's
CMake cache shows `OpenMP_CXX_FLAGS=NOTFOUND` and `GGML_OPENMP_ENABLED=OFF` — zig's
clang ships no `libomp`, so ggml fell back to its non-OpenMP threading path. The
prebuilt release ships with OpenMP enabled and a tuned thread pool. That, plus normal
run-to-run noise on a laptop, is the most likely source of the small edge — and it is
orthogonal to `-DGGML_NATIVE=ON`.

**When this bonus *would* pay off.** On a CPU whose extensions the release ships *no*
dedicated kernel for (CPUID falls back to `ggml-cpu-x64`/`sse42`), a native build would
win materially. Here, on Tiger Lake with a matching shipped kernel and a
bandwidth-bound metric, the honest answer is **parity** — and the interesting part is
*why*: runtime dispatch already closed the gap the "generic prebuilt is slow" story
predicts. The `pp512` companion (`bonus-build-compare-pp512.md`) tells the same story
on the more instruction-bound metric.
