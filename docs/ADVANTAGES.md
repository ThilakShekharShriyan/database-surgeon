# All-round advantages — Database Surgeon

Sealed eval_v2 scoreboard across **quality · safety · cost · optimizer latency · cache · cascade**.
Accepted = equivalent on all eval fixtures (incl. null/skew) and ≥20% faster.

## Why we win (auto)

- **Safety cliff:** open-raw wrong=11 → open-harness wrong=0 (accept 46.9% → 57.1%).
- **Vs frontier:** open-harness accept 57.1% / wrong=0 vs frontier-raw 56.1% / wrong=0.
- **Harness > rules:** rules-only 14.3% → open-harness 57.1% (same 0-wrong gate).
- **Cost:** open-harness $0.0028/case vs frontier $0.0027/case.
- **Optimizer latency (open-harness):** p50=7.0s p95=28.3s · LLM p50=6.0s · verify p50=0.3s.
- **Workload cache:** hit-rate 62.2% → ~2.65× estimated LLM latency with warm fingerprints.
- **Flash harness:** fw-fast-harness accept 57.1% / 0 wrong ($0.0074/case).

## Dev (98 cases)

| System | Done | Accept | Wrong | $/case | opt p50 s | opt p95 s | LLM p50 s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| fw-nemotron-harness | 16/98 | 81.2% | 0 | $0.0040 | 1.7 | 76.8 | 0.0 |
| oss20b-harness | 39/98 | 76.9% | 0 | $0.0012 | 3.0 | 9.9 | 1.9 |
| ollama-gpt-oss-20b-harness | 53/98 | 62.3% | 0 | $0.0000 | 27.5 | 248.4 | 26.2 |
| cascade-open-fw | ✓ | 57.1% | 0 | $0.0028 | 7.0 | 28.3 | 6.0 |
| cascade-oss-fw | ✓ | 57.1% | 0 | $0.0028 | 7.0 | 28.3 | 6.0 |
| fw-fast-harness | ✓ | 57.1% | 0 | $0.0074 | 28.8 | 100.4 | 25.5 |
| fw-gpt-oss-harness | ✓ | 57.1% | 0 | $0.0028 | 7.0 | 28.3 | 6.0 |
| open-harness | ✓ | 57.1% | 0 | $0.0028 | 7.0 | 28.3 | 6.0 |
| frontier-raw | ✓ | 56.1% | 0 | $0.0027 | 3.8 | 12.0 | 3.7 |
| fw-nemotron-raw | ✓ | 50.0% | 3 | $0.0020 | 11.3 | 39.7 | 11.0 |
| fw-fast-raw | ✓ | 48.0% | 0 | $0.0011 | 11.7 | 30.8 | 11.7 |
| open-raw | ✓ | 46.9% | 11 | $0.0004 | 2.4 | 4.8 | 2.4 |
| rules-only | ✓ | 14.3% | 0 | $0.0000 | 0.0 | 0.4 | 0.0 |

## Held-out (73 cases)

| System | Done | Accept | Wrong | $/case | opt p50 s | opt p95 s | LLM p50 s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| rules-only | ✓ | 20.5% | 0 | $0.0000 | 0.0 | 2.5 | 0.0 |
| frontier-raw | 1/73 | 0.0% | 0 | $0.0032 | 9.2 | 9.2 | 9.0 |

## Cache A/B

```json
{
  "hit_rate": 0.6224,
  "positive_hits": 49,
  "negative_hits": 12,
  "misses": 37,
  "estimated_speedup_factor": 2.65,
  "open_harness_llm_p50_ms": 6035.4
}
```

## Reproduce

```bash
bash scripts/run_all_advantages_bench.sh
.venv/bin/python scripts/write_advantages_scoreboard.py
```

