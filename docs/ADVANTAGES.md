# All-round advantages — Database Surgeon

Sealed eval_v2 scoreboard across **quality · safety · cost · optimizer latency · cache · cascade**.
Accepted = equivalent on all eval fixtures (incl. null/skew) and ≥20% faster.

**Narrative + paired tests:** [FORGE_RESEARCH.md](FORGE_RESEARCH.md) · regenerate stats: `scripts/compute_paired_stats.py`

## Why we win (auto)

- **Safety cliff:** open-raw wrong=11 → open-harness wrong=0 (accept 46.9% → 62.2%).
- **Vs frontier:** open-harness accept 62.2% / wrong=0 vs frontier-raw 56.1% / wrong=0.
- **Harness > rules:** rules-only 14.3% → open-harness 62.2% (same 0-wrong gate).
- **Cost:** open-harness $0.0020/case vs frontier $0.0027/case.
- **Optimizer latency (open-harness):** p50=2.9s p95=55.7s · LLM p50=0.0s · verify p50=0.3s.
- **Workload cache:** hit-rate 65.3% → ~2.88× estimated LLM latency with warm fingerprints.
- **Flash harness:** fw-fast-harness accept 57.1% / 0 wrong ($0.0074/case).

## Dev (98 cases)

| System | Done | Accept | Wrong | $/case | opt p50 s | opt p95 s | LLM p50 s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cascade-surgeon | 86/98 | 65.1% | 0 | $0.0124 | 28.6 | 200.9 | 21.2 |
| oss20b-harness | 68/98 | 64.7% | 0 | $0.0007 | 0.3 | 8.6 | 0.0 |
| cascade-nemotron | 90/98 | 64.4% | 0 | $0.0091 | 8.4 | 121.3 | 5.7 |
| open-harness | ✓ | 62.2% | 0 | $0.0020 | 2.9 | 55.7 | 0.0 |
| open-harness-nocache | ✓ | 59.2% | 0 | $0.0027 | 7.0 | 28.4 | 5.9 |
| cascade-open-fw | ✓ | 57.1% | 0 | $0.0028 | 7.0 | 28.3 | 6.0 |
| cascade-oss-fw | ✓ | 57.1% | 0 | $0.0028 | 7.0 | 28.3 | 6.0 |
| fw-fast-harness | ✓ | 57.1% | 0 | $0.0074 | 28.8 | 100.4 | 25.5 |
| fw-gpt-oss-harness | ✓ | 57.1% | 0 | $0.0028 | 7.0 | 28.3 | 6.0 |
| frontier-raw | ✓ | 56.1% | 0 | $0.0027 | 3.8 | 12.0 | 3.7 |
| fw-nemotron-harness | 68/98 | 52.9% | 0 | $0.0114 | 24.2 | 108.3 | 23.8 |
| fw-nemotron-raw | ✓ | 50.0% | 3 | $0.0020 | 11.3 | 39.7 | 11.0 |
| ollama-gpt-oss-20b-harness | ✓ | 49.0% | 0 | $0.0000 | 21.3 | 257.8 | 20.5 |
| fw-fast-raw | ✓ | 48.0% | 0 | $0.0011 | 11.7 | 30.8 | 11.7 |
| open-raw | ✓ | 46.9% | 11 | $0.0004 | 2.4 | 4.8 | 2.4 |
| cache-rules | ✓ | 32.7% | 0 | $0.0000 | 0.2 | 0.8 | 0.0 |
| rules-only | ✓ | 14.3% | 0 | $0.0000 | 0.0 | 0.4 | 0.0 |

## Held-out (73 cases)

| System | Done | Accept | Wrong | $/case | opt p50 s | opt p95 s | LLM p50 s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| rules-only | ✓ | 20.5% | 0 | $0.0000 | 0.0 | 2.5 | 0.0 |
| frontier-raw | 1/73 | 0.0% | 0 | $0.0032 | 9.2 | 9.2 | 9.0 |

## Cache A/B

```json
{
  "hit_rate": 0.6531,
  "positive_hits": 52,
  "negative_hits": 12,
  "misses": 34,
  "estimated_speedup_factor": 2.88,
  "open_harness_llm_p50_ms": 6035.4
}
```

## Reproduce

```bash
bash scripts/run_all_advantages_bench.sh
.venv/bin/python scripts/write_advantages_scoreboard.py
```

