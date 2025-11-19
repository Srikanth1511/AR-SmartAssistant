# Audio-Only Proof of Concept Overview

This folder captures every requirement for the manual-session, audio-only
remembrance agent POC. Start with `requirements.md` for the complete merged
spec, then use the section-specific files to dive deeper into architecture,
pipeline, database, and UI decisions.

## Files

- `requirements.md` — canonical requirements document.
- `architecture.md` — scope, approvals, event persistence, supervised learning.
- `audio-pipeline.md` — Android/Glass audio capture flow and config.
- `database-design.md` — logical schemas for `brain_main.db` and `system_metrics.db`.
- `versioning.md` — model/config version tracking and replay behavior.
- `llm-orchestrator.md` — event classification contract and tagging guidance.
- `debug-ui.md` — debug UI interactions for sessions, metrics, and approvals.
- `roadmap.md` — phased delivery plan.

Follow `CONTRIBUTIONS.md` when updating or extending these documents.
