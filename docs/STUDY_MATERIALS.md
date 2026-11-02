# Start here: Database Surgeon study packet

This packet answers: who the project serves; what it targets; where it runs;
how it was built; why its components can help; what actually improved; what a
frontier is; what remains unproved; and which avenues are worth testing next.

## Read in this order

1. **[End-to-end study guide](STUDY_GUIDE.md)** — concepts, SQL examples, actual
   pipeline, captured results, statistical interpretation, training, economics
   and alternative approaches.
2. **[Pipeline and delivery playbook](PIPELINE_PLAYBOOK.md)** — source map,
   ownership roles, current limits, milestone dependencies, acceptance evidence,
   commands and a release-decision template.
3. **[Presentation cheat sheet](STUDY_CHEATSHEET.md)** — 30-second and five-minute
   explanations, key numbers, twenty questions with answers and defensible wording.
4. **[Captured evidence](STUDY_EVIDENCE.json)** — exact trial-0 summaries, paired
   comparisons, source/trace hashes and the specialist split-overlap audit.

## Choose a study session

| Time available | Work through | You should be able to explain |
| --- | --- | --- |
| 15 minutes | Guide sections 1–5 and the cheat sheet's headline numbers | Problem, user, scope, frontier versus Pareto frontier, and the defensible claim. |
| One hour | Guide sections 6–13, especially the three SQL examples and McNemar table | How proposals become accepted rewrites, what failed, and why uncertainty matters. |
| Two to three hours | Full guide and pipeline playbook; open the linked source modules | How code, traces, training exports and UI evidence connect; which gaps block stronger claims. |
| Hands-on session | Rebuild the evidence packet offline, inspect a successful and incorrect SQL record, then rehearse the demo | Reproduce the artifact analysis without confusing it with a new model or database experiment. |

Start hands-on work with:

```sh
.venv/bin/python scripts/build_study_evidence.py
```

This writes a new dated study evidence snapshot. It makes no inference or
database calls and does not seed or modify the workload cache. Active runs can
change later counts; preserve the prior capture when comparing presentations.

## Important reading rules

- The main result table consistently uses **development trial 0**. An older
  frontier figure averaged several trials; those are different summaries.
- The current verifier uses **all eight** evaluator fixtures. Earlier material
  describing five system fixtures plus three independent hidden fixtures is
  historical. The held-out query split is a separate boundary.
- “Implemented,” “trained,” “deployed” and “demonstrated to improve SQL performance”
  are different states. Each is labeled separately in this packet.
- No universal best-model, zero-error SLA, customer-savings or independently
  validated production claim follows from this prototype.

## Present or inspect

See [DEMO.md](DEMO.md) for the walkthrough and [REPRO.md](REPRO.md) for the
reporting commands. The research UI uses saved traces; recorded replay does not
make fresh model calls. Live evaluation, training and workload-collector examples
have different resource and mutation implications, explained in the playbook.

External conceptual explanations are grounded in primary PostgreSQL,
statsmodels/CRAN and Stanford references linked beside the relevant passages.
Repository claims are grounded in code and the dated evidence, not those
external sources.
