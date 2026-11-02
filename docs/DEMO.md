# Research demo

Visual direction: Data terminal, seed `844269793`, preserving the project's
Public Sans, IBM Plex Mono and neutral dark palette. Monospace is reserved for
measurements and SQL. The paired outcome table and fixture counterexamples are
the product's signature evidence, rather than decorative imagery. No sample
benchmark statistics are used.

The four screens answer: What is the quality/resource tradeoff? Does the paired
evidence support a difference? What happened to this SQL? What does the protocol
actually establish? Detailed graphs intentionally continue below the fold;
the opening view prioritizes the selected system and its principal comparisons.

Start the existing local app with `npm --prefix web run dev` and open
http://127.0.0.1:3100. The opening research screen reads saved evidence and
does not need the Python evaluator, a database connection or model access.

Judge narrative (Forge-inspired, original to this project): [FORGE_RESEARCH.md](FORGE_RESEARCH.md)
— also served at `/research/FORGE_RESEARCH.md` after `scripts/export_research.py`.

## Suggested walkthrough

0. **Write-up:** open `/research/FORGE_RESEARCH.md` (or `docs/FORGE_RESEARCH.md`) for the six-step story + McNemar tables.
1. **Benchmark overview:** select Open · harness against Frontier · raw. Explain
   acceptance, observed incorrect returns, API cost and optimizer p50/p95 together.
   Switch the scatter between cost and latency. Partial runs remain labeled.
2. **Paired statistics:** show the McNemar discordant cells, then change the
   comparator to Open · raw. Discuss the additional quality and correctness
   checks alongside their resource overhead. Template tests are sensitivity
   analyses; non-significance does not prove equivalent quality.
3. **Query evidence:** select Nemotron · harness and a query marked incorrect.
   Inspect its returned SQL and the evaluator's counterexample. Switch back to
   an accepted case and adjust the execution count in the elapsed-time payback
   calculator. The illustration excludes database cost and performance drift.
4. **Protocol & scope:** show split coverage, finite-fixture limits, training
   overlap, budget differences and the exact input hash. Download the snapshot
   or system CSV for follow-up.
5. **Live demo:** open `/demo`, choose Live surgery, then the correlated-AVG
   preset. Replay recorded trace uses the saved snapshot, with no inference or
   database request. An unknown replay returns an error and never falls through
   to a paid live call. Live and Run surgery are explicitly separate actions;
   model stages may make paid API calls and require the Python service on 8765.

The legacy experiment lab remains at `/lab`; it requires the Python service.
The research dashboard also appears inside the lab's Frontier view.

For an isolated production presentation when another process owns port 3100:

```sh
SURGEON_WEB_PORT=3101 npm --prefix web start
```

Open http://127.0.0.1:3101. For browser QA on this port, set
`RESEARCH_BASE_URL=http://127.0.0.1:3101` before the verification command.

## Refresh evidence deliberately

After new runs finish, from the repository root:

```sh
.venv/bin/python scripts/export_research.py
```

This reads the JSONL artifacts and writes matching credential-free snapshots to
`web/public/research/snapshot.json` and `site/data/research.json`. It recomputes
paired comparisons offline, without model or database calls. Use Refresh in the
research app to load that saved snapshot. Results do not change mid-presentation
unless the snapshot is exported and refreshed.

The separate static companion works with no Node or Python evaluator backend:

```sh
python3 -m http.server 8766 --bind 127.0.0.1 --directory site
```

Open http://127.0.0.1:8766. Its Local app links target the isolated production demo on port 3101.

## Verification

```sh
npm --prefix web run typecheck
npm --prefix web run build
.venv/bin/python -m unittest discover -s tests -v
# With the app on 3100 and static companion on 8766:
node scripts/verify_research.mjs
```

Browser QA writes its report and screenshots to `.local/research-qa/`.
It checks navigation, comparisons, query filters, counterexamples, responsive
layouts, recorded replay and missing-replay rejection. It makes no paid calls.
Run production builds with the dev server stopped, or use a separate build
directory, because both Next modes otherwise share `.next` artifacts.
