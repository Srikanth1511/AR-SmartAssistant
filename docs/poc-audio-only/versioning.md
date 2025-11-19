# Versioning & Config Logging

This file summarizes Section 4 of the requirements and must match
`requirements.md`.

## 4.1 Tables

- `model_versions`
  - Each row captures a stable combination of LLM model, ASR model/thresholds,
    speaker model/thresholds, primary classification prompt (hash), and a full
    config snapshot.
- `config_change_log`
  - Every time a relevant config or prompt changes, insert a row with the old
    hash, new hash, change summary, timestamp, and who triggered it.

## 4.2 Behavior

1. **Session start**
   - Determine the active `model_version_id` and store it in `sessions`.
2. **Session replay**
   - Load raw events.
   - Re-run LLM with a different `model_version_id` / config snapshot.
   - Compare resulting `memory_items` to understand differences.

All model/config changes must be logged—no silent drift.
