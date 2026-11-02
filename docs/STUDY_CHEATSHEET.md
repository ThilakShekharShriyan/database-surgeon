# Database Surgeon: presentation and study cheat sheet

Read [the guide](STUDY_GUIDE.md) first. Numbers here refer to the captured
**development trial 0** in [STUDY_EVIDENCE.json](STUDY_EVIDENCE.json), not a fresh
run or a claim about the newest source configuration.

## The 30-second explanation

Database Surgeon improves existing PostgreSQL SELECT queries. Open models propose
rewrites; the harness checks results and measures execution, then returns a
beneficial candidate or keeps the original. On 98 development cases, the saved
open harness accepted 56 rewrites versus 46 from open raw, with observed incorrect
returns falling from 11 to zero. It adds cost and latency. We have not established
global superiority over a frontier model or production correctness.

## The five-minute explanation

1. **Problem:** existing SQL can repeat expensive work; an incorrect optimization
   can silently change business results.
2. **Target:** engineers reviewing recurring PostgreSQL analytics/reporting queries.
3. **Mechanism:** cache/rules → model proposals → output checks → paired timing →
   accept or original. Repair and cascades spend additional budget when admitted.
4. **Evidence:** fixed synthetic microfixtures, saved traces, matched outcome tests,
   cost and optimizer-time measurements, with partial systems disclosed.
5. **Next proof:** independent instances, clean experiment/cache identity, complete
   matched held-out comparisons and a measured warm/cold efficiency experiment.

## The numbers to remember

| Item | Captured fact |
| --- | --- |
| Admitted SQL cases | 171: 98 dev + 73 held-out |
| Template IDs | 57 dev + 25 held-out |
| Open raw | 46/98 accepted; 11 incorrect; API $0.000424/case |
| Open harness | 56/98 accepted; 0 incorrect; API $0.002751/case |
| Configured frontier raw | 55/98 accepted; 0 incorrect; API $0.002673/case |
| Rules-only saved run | 14/98 accepted; 0 incorrect; zero API spend |
| Harness − raw acceptance | +10.2 percentage points; disagreements 10 vs 0; McNemar p≈0.002 |
| Harness vs frontier acceptance | Disagreements 7 vs 6; p=1.0; equivalence not established |
| Harness / frontier resources | Mean API cost 1.03×; mean optimizer latency 2.21× |
| Offline cache estimate | 62.24% fingerprint coverage; estimated 2.65× LLM-time factor; not an end-to-end A/B |
| SFT experiment | 5 steps; 69 train / 40 validation rows; SQL-string target match 5%→35% |
| Training qualification | 12 template groups overlap; no deployed specialist SQL benchmark win shown |

The earlier 57.1% frontier figure averaged multiple trials. This packet's 56.1%
is trial 0 only. State the trial policy before comparing numbers.

## Twenty questions you should be able to answer

**1. What is a frontier model?** A highly capable general-purpose model near the
leading edge of a time period. It need not win a specialized SQL task.

**2. What is a Pareto frontier?** The nondominated configurations among a declared
tested set and objectives. It depends on which systems and conditions were tested.

**3. Are we the best?** Not established. We have a measured harness-versus-raw
improvement and a research prototype, not a universal optimizer win.

**4. Why not just use the bigger model?** More capability can help proposals but
does not remove SQL semantic risk. Compare outputs, useful coverage and complete
resource costs. The current frontier raw result is faster than our full harness.

**5. Why not just use PostgreSQL's optimizer?** PostgreSQL still optimizes our
output. We explore alternative SQL expressions under the same physical design.

**6. Is this text-to-SQL?** No. Input SQL already exists; the goal is preserving
its observable result while improving execution.

**7. What does the harness add?** Context, optional examples, multiple proposals,
verification, repair and original-query fallback. Those additions consume budget.

**8. Why is NOT IN dangerous to rewrite?** A NULL on the right can make the
predicate unknown. Unconditional NOT EXISTS substitution can include different rows.

**9. Does execution success mean correctness?** No. A syntactically valid query
may change values, duplicates, NULLs, types or ordering.

**10. Do eight fixtures prove equivalence?** No. They test eight data instances.
Current verifier and judge use the same eight, so fresh independent instances
are needed to test correctness generalization.

**11. What does “accepted” mean?** Output checks pass and median execution time
falls by at least 20% on the designated fixture. It is not generic accuracy.

**12. Does 20% reduction mean 1.20× speedup?** No. Runtime becomes 0.8× original;
speedup is 1/0.8 = 1.25×.

**13. What does McNemar test?** A difference in paired binary outcome rates using
the two disagreement counts. It does not test continuous latency or dollars.

**14. Does p=1 prove parity?** No. It is failure to detect a difference under that
test. Noninferiority requires a separate prespecified margin and suitable analysis.

**15. Why resample templates?** Parameter variants share structure. Treating all
variants as independent can overstate precision. Repeated trials also need their
own uncertainty treatment.

**16. Is zero wrong a correctness SLA?** No. It is zero observed oracle failures
in a specified experiment. Broader guarantees need stronger contracts and evidence.

**17. Is local API cost zero total cost?** No. Hardware, energy, validation,
training, serving and engineering can still cost money.

**18. Did the cache make the product 2.65× faster?** Not demonstrated. The script
estimates LLM time from self-seeded fingerprint coverage and excludes verification.

**19. Did fine-tuning work?** It changed SQL-target string match in a small
experiment. Overlapping templates and absent SQL-performance evaluation limit
the claim. An adapter was trained; a useful deployed specialist is not yet proven.

**20. What is the next best experiment?** First fix experiment identity and fresh
correctness evaluation; then complete matched held-out and warm/cold efficiency
comparisons. Avoid choosing a weaker baseline simply to produce a win.

## Explain one query on a whiteboard

Choose the date-filter example from the guide. Draw the original indexed column
inside a date cast, then the half-open range on the bare column. Explain:

- Why an access path may improve without promising an index will be used.
- Which timestamp/timezone assumptions are required.
- Why output equivalence comes before timing.
- Why a 1 ms saving might need thousands of future executions to repay tuning.

Then explain the missing-department failure. That demonstrates you understand
why declared constraints matter more than a model's plausible assumption.

## Presentation language: use this, avoid that

| Use | Avoid |
| --- | --- |
| “Zero incorrect returns observed in this captured dev experiment.” | “We guarantee zero wrong SQL.” |
| “Similar observed acceptance; difference not established.” | “p=1 proves equal accuracy.” |
| “Recorded replay; no fresh inference.” | “The model just produced this” during replay. |
| “Estimated warm-cache LLM-time factor.” | “Measured 3× end-to-end speedup.” |
| “Open weights served through a remote API.” | “SQL never leaves the VPC” without local-only enforcement. |
| “SQL-string match improved in a small overlapping-template validation.” | “Fine-tuning proved better database optimization.” |
| “Cost and optimizer latency currently increase on the cold comparison.” | Hiding unfavorable resource results. |
| “The next experiment could falsify this hypothesis.” | “Every ingredient is responsible for the full gain.” |

## Finish a judge discussion with an experiment

“Our demonstrated improvement is the harness over the raw open model. The open
harness has not yet established a cost/latency advantage over the closed baseline.
The next release will freeze cache and evaluator state, use fresh independent
instances, and measure whether repeated-workload reuse improves total efficiency
under a declared quality threshold.”
