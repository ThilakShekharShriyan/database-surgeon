# Overnight / LaunchAgents

| Agent | Script | Notes |
|-------|--------|-------|
| `com.databasesurgeon.gptoss` | `ollama_gptoss_only.sh` | gpt-oss:20b raw → 5-family harness smoke → kicks `finish_wave_a` |
| `com.databasesurgeon.vast` | `vast_train_now.sh` | Ampere+ only, 1-epoch LoRA, destroy with `-y` |
| `com.databasesurgeon.finish` | `finish_wave_a.sh` | Waits for gpt-oss raw ≥90 cases → router/cascades/RESULTS/site |
| `com.databasesurgeon.rest` | `build_rest.sh` | Broader overnight; usually unloaded while gptoss/vast run |

```bash
launchctl bootout gui/$(id -u)/com.databasesurgeon.<name>
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.databasesurgeon.<name>.plist
```

See `docs/REPRO.md`.
