# DBSurgeon — demo video script

**Canonical <120s script:** [DEMO_SCRIPT_120.md](DEMO_SCRIPT_120.md) (problem → demonstrate → measured result).

---

## Older notes (~60–90s)

**Preferred path — OpenScreen + ElevenLabs** (see `openscreen-demo-plan.md`):

```sh
# Voiceover (uses ELEVENLABS_API_KEY + ELEVENLABS_VOICE_ID from .env.local)
.venv/bin/python scripts/generate_demo_voiceover.py
# → .local/demo_video/DBSurgeon/voiceover/full.mp3 (~50s)

# After OpenScreen MCP is live in a fresh chat ("continue the OpenScreen demo"):
# record Chrome app window → import VO → export MP4
```

Fallback ffmpeg PiP recorder:

```sh
./scripts/record_demo.sh --project="DBSurgeon"
./scripts/record_demo.sh --project="DBSurgeon" --pick
```

Upload: `.local/demo_video/DBSurgeon/DBSurgeon_submission.mp4`

**Layout while recording:** Chrome on demo + research · teleprompter http://127.0.0.1:3100/demo/teleprompter.html on a second display · camera PiP bottom-right.

**Exact click path**
1. Research → `open-raw` → wrong=11  
2. Research → `open-harness` vs frontier, then vs open-raw  
3. Demo → Live surgery → correlated AVG → Replay recorded trace  
4. Demo → nullable anti-join preset → show abstain/repair  
5. Cursor → `surgeon/eval/systems.py` `Verifier` (~L78) using `EVAL_SCHEMAS`

---

## Beat 1 — The Problem (~20s)

**On screen:** `/demo` pitch, or research overview with open-raw selected.

**Say:**
> Agent fleets dump SQL onto Postgres. Blind open models look cheap — then return **wrong** answers. On our sealed 98-case bench, Fireworks `gpt-oss-120b` raw accepts 47% but returns **11 incorrect** rewrites. FinOps can’t ship that. We need faster SQL **or** keep the original — never corrupt.

**Click:** show open-raw wrong count (11) on `/research`.

---

## Beat 2 — Tech Stack (~25s)

**On screen:** research scoreboard + briefly flash `docs/FORGE_RESEARCH.md` / ADVANTAGES.

**Say:**
> Stack is Fireworks serverless — `glm` flash, `gpt-oss-120b`, NVIDIA Nemotron Ultra on escalate — plus a surgical harness: EXPLAIN context, retrieve verified wins, **verify on all fixtures including nulls**, repair, abstain. Fingerprint cache makes repeats free. Fine-tune is optional; the product is verify-or-abstain.
>
> Without Fireworks + that gate, we’d either burn frontier dollars or ship wrong SQL. With them, open-harness hits **57% accept, 0 wrong** — matching frontier raw.

**Click:** open-harness vs frontier (parity) · then vs open-raw (McNemar).

---

## Beat 3 — Live Demo + Code (~30–40s)

**On screen:** `/demo` → Live surgery → correlated-AVG preset (or a known accepted case). Then code.

**Say:**
> Live: same query through raw vs harness. Raw can ship a broken rewrite. Harness verifies — if it fails null/skew checks, we **keep the original**. Accepted means ≥20% faster and row-equivalent.
>
> Code that makes it real: the verifier over full `EVAL_SCHEMAS`, and the registry that swaps raw / harness / cascade without changing the judge.

**Click / show:**
1. Demo surgery result (accepted or abstain — both are wins)
2. Editor: `surgeon/eval/systems.py` (strict verify) · `surgeon/eval/registry.py`
3. Optional one-liner: `python -m surgeon.eval run open-harness --split dev`

**Close:**
> Database Surgeon — open models, surgical harness, 0 wrong returned. Repo: database-surgeon.

---

## Shot checklist (before Record)

- [ ] `http://127.0.0.1:3100/demo` and `/research` load (servers already healthy)
- [ ] Research system = **open-harness**, baseline switch ready to **open-raw**
- [ ] Demo preset pre-selected; prefer **replay** if live latency is slow
- [ ] Cursor/IDE open on `surgeon/eval/systems.py` (verifier) and `registry.py`
- [ ] Notifications off · large font · hide bookmarks bar
- [ ] One clean take; stop talking at 90s max

## NullMotion (title cards — not the recorder)

[NullMotion](https://github.com/blixvip/NullMotion) previews motion drafts under a film — it does **not** record screen+camera. That is `scripts/record_demo.sh`.

Already staged for this project:
- Local NullMotion: http://127.0.0.1:4343 — pick **DBSurgeon · Demo beats**
- In-app cards (faster for the take): http://127.0.0.1:3100/demo/video-cards.html (← / → or 1/2/3)

Use either as a 3–5s intro before each spoken beat, then cut to `/demo` / `/research` / code.
