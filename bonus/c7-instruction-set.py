#!/usr/bin/env python3
"""BONUS C7 - CPU instruction-set survey: does matching the kernel to the silicon pay?

C7 asks a cloud-scale question at laptop scale: choosing FA3 for Hopper vs FA4 for
Blackwell is the same decision as choosing AVX-512 vs AVX2 kernels for your own CPU.
The kernel must match the silicon.

Experiment: build llama.cpp twice from the same source revision, changing ONLY the
instruction-set target, then run the same llama-bench workload through both:

  build/           -DGGML_NATIVE=ON   -> compiler targets THIS CPU (Tiger Lake, AVX-512)
  build-baseline/  -DGGML_NATIVE=OFF -DGGML_AVX2=ON ... -> generic x86-64 baseline (AVX2, no AVX-512)

Both builds have OpenMP OFF (zig's clang ships no libomp), so the only axis that
differs is the vector instruction set -- no threading confound.

    .venv/bin/python bonus/c7-instruction-set.py
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import labkit  # noqa: E402

METRICS = ["tg128", "pp512", "pp2048"]


def bench_shape(metric: str) -> list[str]:
    return ["-p", metric[2:], "-n", "0"] if metric.startswith("pp") else ["-p", "0", "-n", metric[2:]]


def run(bench: pathlib.Path, model: str, threads: int, metric: str, reps: int) -> float:
    proc = subprocess.run(
        [str(bench), "-m", model, "-t", str(threads), "-ngl", "0",
         *bench_shape(metric), "-r", str(reps)],
        capture_output=True, text=True, check=False, timeout=1800,
    )
    return labkit.bench_metric(proc.stdout + proc.stderr, metric)


def main() -> int:
    ap = argparse.ArgumentParser(description="C7 CPU instruction-set survey (bonus).")
    ap.add_argument("--reps", type=int, default=3)
    args = ap.parse_args()

    root = labkit.repo_root()
    exe = "llama-bench.exe" if sys.platform == "win32" else "llama-bench"
    native = root / "bonus" / "llama.cpp" / "build" / "bin" / exe
    baseline = root / "bonus" / "llama.cpp" / "build-baseline" / "bin" / exe
    for label, p in (("native", native), ("baseline", baseline)):
        if not p.exists():
            labkit.die(f"{label} llama-bench not found: {p}",
                       "Build it first: `make build-llama` (native) and configure build-baseline.")

    hw = labkit.load_hardware()
    model = str(root / labkit.load_active()["primary_model"])
    threads = labkit.threads(hw)

    labkit.banner("C7 - CPU instruction-set survey")
    print(f"  model   : {pathlib.Path(model).name}")
    print(f"  threads : {threads}   ngl: 0 (CPU only, both)")
    print(f"  native  : {native.relative_to(root)}")
    print(f"  baseline: {baseline.relative_to(root)}")
    print("  (both OpenMP OFF -> the only axis that differs is the vector ISA)\n")

    rows = []
    for metric in METRICS:
        print(f"  {metric}: native ...", flush=True)
        n = run(native, model, threads, metric, args.reps)
        print(f"  {metric}: baseline ...", flush=True)
        b = run(baseline, model, threads, metric, args.reps)
        rows.append({"metric": metric, "native": n, "baseline": b,
                     "ratio": (n / b) if b else 0.0})
        print(f"    native {n:7.1f}   baseline {b:7.1f}   native/baseline {rows[-1]['ratio']:.2f}x\n")

    table = labkit.md_table(
        ["metric", "native `-march=native` (AVX-512)", "baseline AVX2 (no AVX-512)", "native / baseline"],
        [[r["metric"], f"{r['native']:.1f}", f"{r['baseline']:.1f}", f"{r['ratio']:.2f}x"] for r in rows],
    )

    md = f"""# Bonus C7 - CPU instruction-set survey

Host `{labkit.host_tag()}` · CPU `{hw.get('cpu', {}).get('model', '?')}` · llama.cpp `{labkit.LLAMA_CPP_BUILD}`
same source revision, same model `{pathlib.Path(model).name}` · `-t {threads}` · `-ngl 0` · {args.reps} reps

Two builds, **only the instruction-set target differs** (both have OpenMP OFF, so no
threading confound):

| Build | Flags | Vector ISA |
|:--|:--|:--|
| `build/` (native) | `-DGGML_NATIVE=ON` | compiler targets this CPU (`-march=native`, AVX-512 capable) |
| `build-baseline/` | `-DGGML_NATIVE=OFF -DGGML_AVX2=ON -DGGML_AVX=ON -DGGML_FMA=ON` | generic x86-64 baseline (AVX2, no AVX-512) |

{table}

## Your finding

_<replace this line>_
"""
    out = labkit.write_report("bonus-c7-instruction-set.md", md,
                              {"rows": rows, "threads": threads, "reps": args.reps})
    print(f"==> Wrote {out.relative_to(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
