# 02 - Serve: load test + saturation reading

Host `Windows-AMD64` · llama.cpp `b10488` ·
`--parallel 4` · `ctx=2048` · `threads=8` ·
`ngl=0`

| Users | Reqs | RPS | P50 (ms) | P95 (ms) | P99 (ms) | Eff. concurrency | Failures |
|:--|--:|--:|--:|--:|--:|--:|--:|
| 10 | 69 | 1.18 | 7000 | 11000 | 14000 | 8.6 | 0.0% |
| 50 | 85 | 1.45 | 30000 | 37000 | 39000 | 36.9 | 0.0% |

*Effective concurrency = RPS x average latency (Little's Law) -- how many requests were
really in flight, regardless of how many users locust simulated. It counts queued requests
too, so the occupancy/slot ratio can legitimately exceed 1.0; it is occupancy, not
utilisation. For true slot utilisation use the server's own gauges (`make metrics`).*

## What these two runs say

| Going from 10 to 50 users | |
|:--|--:|
| Offered load | 5x |
| Throughput actually delivered | **1.22x** (24% of linear) |
| P95 latency | **3.36x** |
| Effective concurrency at 50 users | 36.9 vs `--parallel 4` slots (occupancy/slot ratio 9.23) |

**Saturated.** Throughput delivered only 1.22x for 5x the offered load, and effective concurrency (36.9) is at or above all 4 decode slots. Saturation sets in somewhere at or below 50 users; the load you added beyond that point became queue time rather than throughput.

Throughput moved 1.22x while P95 moved 3.36x. That gap is the goodput argument: past saturation you buy throughput by spending latency, and if your SLO is a P95 target then the requests you added are no longer being served within it. (This lab does not fix an SLO number for you -- pick one in your write-up and state how much goodput you keep at it.)

## Your reading

**Saturation evidence: 5× the offered load bought only 1.22× the throughput, while P95
tripled.** Ten users completed 69 requests at 1.18 RPS with P95 = 11 s; fifty users
completed only 85 requests at 1.45 RPS with P95 = 37 s. Five times the concurrency
produced 1.22× the completed work (24% of linear) — so the server was already at its
knee before 50 users. The single number that convinced me: **effective concurrency
rose 8.6 → 36.9 (4.3×) while throughput rose only 1.22×** — 36.9 requests were in
flight at 50 users, but only 4 decode slots exist. The other ~33 were queued.

That extra latency is **queue time, not compute time**. If the added users were buying
real compute, completed requests would have risen with them; instead P95 rose 3.36×
(11 s → 37 s) for a 1.22× throughput gain. The server's own gauges confirm the queue:
`requests_deferred` peaked at **46** while `requests_processing` sat pinned at its
ceiling of 4 and `n_busy_slots_per_decode` hit **3.99 of 4 (100%)** — the slots were
full, so every arrival past the fourth waited.

**SLO and goodput.** Take **P95 ≤ 30 s** as the target. At 10 users P95 = 11 s → within
SLO, goodput = 1.18 RPS. At 50 users P95 = 37 s → violated, and since P50 (30 s) already
sits at the line, roughly half the requests miss the SLO, so goodput at 50 users is far
below the raw 1.45 RPS. That gap is the point: "85 requests either way" hides that at 50
users most of them arrived too late to count.

**First knob to change: raise `--parallel` (4 → 8).** The bottleneck is decode-slot
occupancy, and I can see it directly: `n_busy_slots_per_decode` peaked at **3.99 of 4
(100%)** in the overlapping metrics run. The slots are full, so more users can only
queue. Extra slots let more requests share each decode step and raise goodput@SLO
without touching per-token speed. I would *not* start with `-t`: thread count changes
how fast each step runs, not how many requests fit in a step, so it cannot relieve a
slot-bound queue. Only after slots stop being the limit would I look at `-t`, prompt
length, or GPU offload.
