# Database Surgeon — demo video script (< 120s)

**Target length:** 90–110 seconds · hard cap **120s**  
**One message:** Open models + surgical harness → frontier-level accepts, **0 wrong returned**.

**Screens:** http://127.0.0.1:3100/research · /demo · optional `/demo/video-tour.html`  
**Study packet:** [FORGE_RESEARCH.md](FORGE_RESEARCH.md) · [ADVANTAGES.md](ADVANTAGES.md)

---

## Timeline

| Time | Beat | On screen | You say (verbatim) |
| ---: | --- | --- | --- |
| **0:00–0:08** | Hook | `/demo` pitch or cold open | “Database Surgeon. Agentic apps dump SQL onto Postgres. Blind open models look cheap — until they return wrong answers.” |
| **0:08–0:28** | **Problem** | `/research` → system **open-raw** · point at **Wrong = 11** | “On a sealed ninety-eight case bench, Fireworks open raw accepts forty-seven percent but returns **eleven incorrect** rewrites. FinOps can’t ship corruption. We need faster SQL — or keep the original.” |
| **0:28–0:55** | **Demonstrate** | `/research` → **open-harness**; flash cascade chips / Live surgery correlated AVG → Replay | “Stack: Fireworks serverless — flash, gpt-oss-120b, Nemotron Ultra on escalate — behind a surgical harness. Explain, propose, **verify on every fixture including nulls**, measure, accept or abstain. Fine-tune is optional.” |
| | | Nullable anti-join preset · abstain/repair | “Live: accept only when the rewrite is row-equivalent and at least twenty percent faster. A nullable anti-join that would corrupt? The harness abstains.” |
| **0:55–1:25** | **Measured result** | Scoreboard + Paired statistics · open-harness vs open-raw | “Measured on the same sealed judge: open-harness **fifty-seven point one percent** accept, **zero wrong** — matches frontier raw. Versus open-raw: plus ten points accept, eleven wrongs to zero. McNemar p about zero point zero zero two — not luck.” |
| **1:25–1:40** | Close | End card / repo | “Database Surgeon — open models, surgical harness, zero wrong returned.” |
| **≤ 2:00** | Stop | — | Leave ~20s buffer; do **not** overrun. |

---

## Click path (practice twice)

1. `/research` → System **Open · raw** → Incorrect returned **11**  
2. System **Open · harness** → Accept **57.1%** · Wrong **0** · Compare **Frontier · raw** (parity)  
3. Tab **Paired statistics** → McNemar discordant **10 vs 0**  
4. `/demo` → **Live surgery** → correlated AVG → **Replay recorded trace** → ACCEPT  
5. Preset **nullable anti-join** → Replay → abstain / keep original  
6. End on pitch or title card  

---

## Numbers to say (locked)

| Claim | Number |
| --- | --- |
| Bench | 98 sealed dev cases (171 total with held-out) |
| open-raw | 46.9% accept · **11 wrong** · $0.0004/case |
| open-harness | **57.1% accept · 0 wrong** · ~$0.0028/case |
| frontier-raw | 56.1% accept · 0 wrong |
| Safety cliff | 11 → 0 wrong |
| McNemar (accept) | 10 vs 0 · p ≈ 0.002 |
| Accept rule | Equivalent on all fixtures + ≥20% faster |

---

## Voiceover (≤120s — paste to ElevenLabs if re-recording)

```
Database Surgeon. Agentic apps dump SQL onto Postgres. Blind open models look cheap — until they return wrong answers.

On a sealed ninety-eight case bench, Fireworks open raw accepts forty-seven percent but returns eleven incorrect rewrites. Never ship that.

We run Fireworks serverless — flash, open one-twenty-B, Nemotron Ultra on escalate — behind a surgical harness. Verify on every fixture including nulls. Repair or abstain. Fine-tune optional.

Live surgery: accept only when the rewrite is equivalent and twenty percent faster. Nullable anti-joins that would corrupt? The harness abstains.

Measured result: fifty-seven percent accept, zero wrong — frontier parity on an open stack. Versus raw: eleven wrongs to zero. McNemar says the lift is real.

Database Surgeon — verify or abstain.
```

Regenerate audio: edit `scripts/generate_demo_voiceover.py` beats to this copy, then  
`.venv/bin/python scripts/generate_demo_voiceover.py`

---

## Record checklist

- [ ] Cap export at **≤120s** (trim if needed)  
- [ ] Prefer Chrome **app window** (no tab bar) for `/demo/video-tour.html` or `/research`  
- [ ] Mix ElevenLabs VO · no dead air at end  
- [ ] Output: `.local/demo_video/DBSurgeon/DBSurgeon_submission.mp4`  
