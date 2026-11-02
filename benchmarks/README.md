# Benchmark onboarding

Start with [the data/query inspection and protocol](../docs/BENCHMARKS.md).

manifest.template.json records inspected public SQL sources and known prerequisites. It is deliberately NOT_FROZEN and executable=false. It is a planning artifact, not an implemented importer or benchmark command.

Before deriving an executable manifest:

1. Resolve source commit SHAs and hash raw SQL/schema bytes.
2. Review code/data notices and preserve provenance.
3. Resolve structural/source lineage across repositories; keep variants together.
4. Import only original inputs and permitted metadata, excluding reference outputs.
5. Load the declared database and fingerprint its actual data, constraints and indexes.
6. Implement/admit the required result contract; count unsupported cases.
7. Set model IDs, rates, timeouts, repeated-run settings and hard budgets.
8. Freeze a versioned manifest; keep final sealed inputs out of this public template.
9. Run the same admitted population for each system and retain every terminal status.

The current surgeon CLI still uses its existing three-case pilot. No new public-workload command is implied by this file.
