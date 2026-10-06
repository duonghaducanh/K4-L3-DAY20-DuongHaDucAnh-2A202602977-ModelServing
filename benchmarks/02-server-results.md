# 02 - Serve: load test + saturation reading

Host `Windows-AMD64` · llama.cpp `b10488` ·
`--parallel 4` · `ctx=2048` · `threads=4` ·
`ngl=0`

| Users | Reqs | RPS | P50 (ms) | P95 (ms) | P99 (ms) | Eff. concurrency | Failures |
|:--|--:|--:|--:|--:|--:|--:|--:|
| 10 | 26 | 0.46 | 18000 | 25000 | 26000 | 7.5 | 0.0% |
| 50 | 26 | 0.46 | 31000 | 53000 | 56000 | 13.7 | 0.0% |

*Effective concurrency = RPS x average latency (Little's Law) -- how many requests were
really in flight, regardless of how many users locust simulated. It counts queued requests
too, so the occupancy/slot ratio can legitimately exceed 1.0; it is occupancy, not
utilisation. For true slot utilisation use the server's own gauges (`make metrics`).*

## What these two runs say

| Going from 10 to 50 users | |
|:--|--:|
| Offered load | 5x |
| Throughput actually delivered | **1.00x** (20% of linear) |
| P95 latency | **2.12x** |
| Effective concurrency at 50 users | 13.7 vs `--parallel 4` slots (occupancy/slot ratio 3.42) |

**Saturated.** Throughput delivered only 1.00x for 5x the offered load, and effective concurrency (13.7) is at or above all 4 decode slots. Saturation sets in somewhere at or below 50 users; the load you added beyond that point became queue time rather than throughput.

Throughput moved 1.00x while P95 moved 2.12x. That gap is the goodput argument: past saturation you buy throughput by spending latency, and if your SLO is a P95 target then the requests you added are no longer being served within it. (This lab does not fix an SLO number for you -- pick one in your write-up and state how much goodput you keep at it.)

## Your reading

**Saturation evidence: 5x the offered load bought 1.00x the throughput.** Both runs
completed 26 requests in the same ~60 s window (0.46 RPS at 10 users, 0.46 RPS at
50 users). Five times the concurrency produced *zero* extra completed work. The
single number that convinced me: **RPS flat at 0.46 while effective concurrency
rose 7.5 → 13.7** — 3.42x the four decode slots. Requests past the slots were not
being served faster; they were waiting.

That extra latency is **queue time, not compute time**. Per-request compute is
unchanged — the same 26 requests were generated, so the server did the same work;
if the added users were buying compute, throughput would have risen. Instead P95
rose 2.12x (25 s → 53 s) with no throughput gain. The server's own gauges confirm
the queue: `requests_deferred` peaked at **46** while `requests_processing` sat
pinned at 4.

**SLO and goodput.** Take **P95 ≤ 30 s** as the target. At 10 users P95 = 25 s →
within SLO, goodput = 0.46 RPS. At 50 users P95 = 53 s → violated; and since P50
(31 s) already exceeds 30 s, **fewer than half** the requests meet the SLO, so
goodput collapses toward 0 even though raw throughput is identical. That gap is the
whole point — "26 requests either way" hides that at 50 users most of them missed
the target.

**First knob to change: raise `--parallel` (4 → 8).** The bottleneck is decode-slot
occupancy, and I can see it directly: `n_busy_slots_per_decode` peaked at **3.88 of
4 (97%)** in the overlapping metrics run. The slots are full, so more users can
only queue. Extra slots let more requests share each decode step (the batch is
under-filled relative to what continuous batching allows) and raise goodput@SLO
without touching per-token speed. I would *not* start with `-t`: thread count
changes how fast each step runs, not how many requests fit in a step, so it cannot
relieve a slot-bound queue. Only after slots stop being the limit would I look at
`-t`, prompt length, or GPU offload.
