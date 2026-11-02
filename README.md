# Database Surgeon

**Agents ask models to “make this SQL faster.” Without a check, that ships wrong answers.**

Database Surgeon is a verify-or-abstain harness for agent SQL rewrites. A model proposes a rewrite; the harness accepts it only if it returns the same rows on 8 test databases **and** runs at least 20% faster. Otherwise the original query is kept.

📄 **Research paper:** [thilakshekharshriyan.github.io/database-surgeon](https://thilakshekharshriyan.github.io/database-surgeon/)

## Results

Same open model (Fireworks `gpt-oss-120b`), 98 locked PostgreSQL cases:

| System | Accept | Wrong answers | $/case | Median latency |
| --- | ---: | ---: | ---: | ---: |
| Open model, raw | 46.9% | **11** | $0.0004 | 2.4s |
| Frontier model, raw | 57.1% | 0 | $0.0027 | 3.7s |
| **Open model + harness** | **62.2%** | **0** | **$0.0020** | **2.9s** |

- The gain over raw is statistically real (McNemar p = 0.0015; template bootstrap 95% CI +5 to +27 points).
- With the harness, all five models we tested return 0 wrong answers (raw: 0 to 28 wrong).
- The lead over the frontier model is **not** statistically significant; we report it, not claim it.
- The harness has not yet been run on the 73-case held-out split.

Full tables, tests, case studies and limitations are in the [paper](https://thilakshekharshriyan.github.io/database-surgeon/).

## Why it matters

Agent fleets keep multiplying queries through retries, tool loops and scheduled jobs. A rewrite that looks faster but returns wrong rows costs database time, API spend, tokens and trust all at once. The harness puts a correctness and speed gate in front of every rewrite.

## Quick start

```sh
cp .env.example .env              # add FIREWORKS_API_KEY (optional: OPENAI_API_KEY)
docker compose up -d --wait
python3 -m surgeon seed
python3 -m surgeon doctor
python3 -m unittest discover -s tests -v
```

Database-only check, no model calls: `bash scripts/check_local.sh`

Demo UI: `cd web && npm run dev`, then open http://127.0.0.1:3100

## Reproduce the benchmark

```sh
.venv/bin/python -m surgeon.eval run open-raw --split dev --trials 1
.venv/bin/python -m surgeon.eval run open-harness --split dev --trials 1
.venv/bin/python -m surgeon.eval report --split dev
.venv/bin/python scripts/compute_paired_stats.py
bash scripts/site/sync.sh         # refresh data for the paper site
```

Cases and freeze hashes: `benchmarks/eval_v2/`. Run traces: `benchmarks/eval_v2/runs/<system>/`.

## Repository layout

| Path | Contents |
| --- | --- |
| `surgeon/` | Harness, verifier, eval runner and system registry |
| `benchmarks/eval_v2/` | Locked cases, traces and results |
| `site/` | Research paper (GitHub Pages) |
| `web/` | Live demo UI |
| `docs/` | Write-ups and design notes |
| `tests/` | Unit and database integration tests |

## Further reading

- [Forge write-up](docs/FORGE_RESEARCH.md): problem, baseline, harness and statistics
- [Results](docs/RESULTS.md) and [scoreboard](docs/ADVANTAGES.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Demo workbench](docs/WORKBENCH.md)

---

Built during the Nov 2, 2026 Forge × Fireworks × NVIDIA hackathon, with material use of a Cursor agent. See [docs/HACKATHON.md](docs/HACKATHON.md).
