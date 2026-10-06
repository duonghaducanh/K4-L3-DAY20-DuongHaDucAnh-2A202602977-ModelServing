# 02 - Continuous batching under load (u50)

Host `Windows-AMD64` · `--parallel 4` · 18 samples over
75s at 2.0s intervals · raw CSV: `02-server-metrics-u50.csv`

| Gauge | Peak observed |
|:--|--:|
| `n_busy_slots_per_decode` (avg/decode) | 3.99 of 4 slots (100%) |
| `requests_processing` | 4 |
| `requests_deferred` | 46 |
| `kv_cache_usage_ratio` | n/a — not exported by llama.cpp `b10488` |
| `tokens_predicted_total` (final) | 16921 |

Highest sampled value was **3.99 of 4** slots. Note this gauge is llama.cpp's *average* busy slots per decode step, so the number below is the highest average we sampled, not an instantaneous maximum batch width. A peak near 1 means
requests were served one at a time -- either the load was too light to overlap, or
they arrived too far apart. A peak approaching `--parallel` means the scheduler was
genuinely packing concurrent requests into shared decode steps.
`requests_deferred` went above zero: more requests arrived than there were slots, so some waited. That wait is the queue time in your P95.

## Your observation

**Peak batch width: 3.99 of 4 slots (100%).** The scheduler was genuinely packing
concurrent requests into shared decode steps, and it was full for the whole sample.
`requests_processing` was pinned at its ceiling of 4, and `requests_deferred` peaked at
**46**, so there was always a queue behind the busy slots. This is continuous batching
working as intended — not one-at-a-time (a peak near 1), but a saturated batch.

**Does it match the effective concurrency (36.9) in `02-server-results.md`?** Yes — and
they are not equal because they measure different things:

- `n_busy_slots_per_decode` = **3.99** is the *actual batch width being decoded*: how
  many requests shared each decode step, measured by the server itself.
- effective concurrency = **36.9** is Little's Law occupancy (RPS × latency): every
  request in flight, *including* the ones parked in the queue.

They reconcile: ~3.99 requests decoding + ~33 waiting ≈ 36.9 in flight. If I had to
trust one, I trust the **server gauge (3.99)**: it is measured directly at the decode
step rather than inferred from latency, and it is bounded by a real limit (4 slots)
that the derived figure is not. The 36.9 is not "36.9 requests decoding at once" — it is
occupancy, and the gap between 36.9 and 3.99 is exactly the queue that shows up as P95.
