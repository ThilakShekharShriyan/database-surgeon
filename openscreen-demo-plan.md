# OpenScreen demo plan — Database Surgeon (launch)

**Goal:** ~45–60s launch demo MP4 for hackathon submit. One message: *open models + surgical harness → frontier-level accepts, 0 wrong returned.*

**Voice:** ElevenLabs (`ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID` in `.env.local`).
Generated at `.local/demo_video/DBSurgeon/voiceover/` (`full.mp3` / `full.m4a` ≈ **53s**).

**App under demo:** http://127.0.0.1:3100 (Chrome app window, no chrome)
- `/research` for beats 1–2
- `/demo` Live surgery for beat 3
- Code peek: `surgeon/eval/systems.py` Verifier (optional flash)

## Storyboard (launch · 16:9 · callouts carry muted viewing)

| # | ~s | Window / action | Callout (≤6 words) | VO beat |
| --- | ---: | --- | --- | --- |
| 1 | 0–3 | Title card `/demo/video-cards.html` beat 1 | Wrong SQL is worse | — |
| 2 | 3–18 | `/research` → system **open-raw** · highlight Wrong=11 | Open raw: 11 wrong | `01_problem` (trim to ~15s) |
| 3 | 18–35 | `/research` → **open-harness** vs frontier, then open-raw McNemar | 57% accept · 0 wrong | `02_stack` (trim) |
| 4 | 35–50 | `/demo` → Live surgery → correlated AVG → Replay | Verify or abstain | `03_demo` start |
| 5 | 50–58 | Nullable anti-join preset · show abstain/repair | Corruption stopped | `03_demo` end |
| 6 | 58–60 | End card / repo name | Database Surgeon | — |

## Recording settings

- `listSources` → Chrome app window titled for Database Surgeon research/demo
- `startRecording` with `window` matching that title
- `camera: false` (voiceover track, not talking-head) unless user asks for PiP
- `microphone: false` — import ElevenLabs `full.mp3` / beat files via `importMedia` + `addAudio`
- Drive UI with deliberate clicks; pause ~1s after each result
- First action after 2.5s so auto-zoom can engage

## Edit / export

- `setAspectRatio` `16:9`
- Trim dead time; `addAnnotation` per beat with callouts above
- `importMedia` absolute path to `.local/demo_video/DBSurgeon/voiceover/full.mp4` (convert mp3→wav/mp3 as OpenScreen accepts)
- Export → `.local/demo_video/DBSurgeon/DBSurgeon_submission.mp4` (do **not** commit video)

## Setup status

- [x] `npx skills add getopenscreen/openscreen --skill openscreen-demo -y`
- [x] OpenScreen 2.2.0 installed to `/Applications/Openscreen.app`
- [x] ElevenLabs VO generated
- [x] Cursor MCP (registered; tools need new chat) `openscreen` registered (`Openscreen` + `mcp` args)
- [~] New session: say **continue the OpenScreen demo** (MCP tools load on session start)
- [x] macOS Screen Recording + Accessibility for OpenScreen (and Cursor if agent-driven)

## Short VO script (regenerate if needed)

```
Problem: Open raw looks cheap — eleven wrong rewrites on ninety-eight sealed cases. Never ship that.
Stack: Fireworks cascade plus a surgical harness. Verify on all fixtures, including nulls. Fifty-seven percent accept, zero wrong — frontier parity.
Demo: Live surgery accepts only when equivalent and twenty percent faster. Wrong candidates abstain. Database Surgeon.
```

Regenerate: `.venv/bin/python scripts/generate_demo_voiceover.py`

## Continue from

Step 2–9 of `.agents/skills/openscreen-demo/SKILL.md` once MCP tools `startRecording`, `stopRecording`, `exportVideo`, `getFrames` are available.

## Latest export

- `.local/demo_video/DBSurgeon/DBSurgeon_submission.mp4` (≈54s, 20MB, ElevenLabs VO mixed)
- Project: `take_live.openscreen`
- Note: Chrome AppleScript JS was off during take — mostly URL navigation. Re-record after enabling *View → Developer → Allow JavaScript from Apple Events* for richer clicks.
