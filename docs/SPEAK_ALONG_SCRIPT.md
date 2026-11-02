# Research talk — 120 seconds

Like walking someone through your paper: problem → method → results.  
Only the differentiators. Say the numbers out loud.

**Screen path:** `/research` (raw → harness → paired) → `/demo` Live surgery (one accept, one abstain) → back to scoreboard.

---

### I. Problem (0:00–0:25)

**Show:** Open · raw · Wrong = 11

> This work is about safe SQL rewriting for agent-generated PostgreSQL.
>
> The naive baseline is an open model on Fireworks rewriting queries with no check. On a sealed set of ninety-eight cases, that baseline accepts forty-seven percent of rewrites but returns **eleven incorrect** results. So the differentiator we care about is not “can a model propose SQL?” — it’s **can you return a rewrite without corrupting answers?**

---

### II. Method (0:25–0:70)

**Show:** Open · harness · then `/demo` Live surgery briefly

> Our system, Database Surgeon, is verify-or-abstain on Fireworks. Cascade: a fast model, gpt-oss-120b, then **NVIDIA Nemotron Ultra** on escalate — all behind the same gate.
>
> What makes it different from raw prompting:
>
> One — **strict verification** on the full fixture set, including null and skew cases, not a soft confidence score.
>
> Two — **accept only if** results match **and** median runtime improves by at least twenty percent; otherwise keep the original.
>
> Three — optional fingerprint cache for repeated shapes; fine-tune is optional. The contribution is the gate.
>
> In the live path: a correlated rewrite can accept after verify; a nullable NOT IN that would change rows is rejected and we abstain. That is the method, demonstrated.

---

### III. Results (0:70–0:115)

**Show:** system scoreboard → Paired statistics

> Same sealed judge for every system. Main comparison:
>
> Raw open model: **46.9% accept, 11 wrong.**  
> Our harness: **57.1% accept, 0 wrong.**  
> Closed frontier raw: **56.1% accept, 0 wrong.**
>
> So the differentiator on quality is: we match frontier safety and acceptance on an open Fireworks + Nemotron stack, while raw open fails the safety test.
>
> Tests, not just averages:
>
> McNemar on the same ninety-eight cases — harness versus raw accept: **ten to zero**, p ≈ **0.002**. Incorrect returns: **eleven to zero**.
>
> Template-cluster bootstrap on the accept gap: about **plus ten points**, confidence interval above zero.
>
> Versus frontier accept: paired test is a tie — we claim **parity**, not superiority.
>
> Cost about **$0.0028** per case, next to frontier; cache about **62%** hit / **~2.65×** on repeats.

---

### IV. Close (0:115–0:120)

> Contribution: a measured verify-or-abstain SQL rewriter — Fireworks, NVIDIA Nemotron, sealed eval — **eleven wrongs to zero**, frontier-level accepts. Database Surgeon.

---

### Differentiator checklist (say these, skip the rest)

1. Sealed bench, same judge for every system  
2. Full-fixture verify (incl. nulls) — not confidence  
3. Fireworks cascade + **NVIDIA Nemotron Ultra** escalate  
4. **57.1% / 0 wrong** vs raw **46.9% / 11** vs frontier **56.1% / 0**  
5. McNemar + template bootstrap (not vibes)  
