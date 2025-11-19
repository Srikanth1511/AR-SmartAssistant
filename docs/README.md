# Documentation Index

The AR-SmartAssistant proof of concept is documented under `docs/poc-audio-only/`.
Each markdown file maps to a major requirement section so you can quickly drill
into the details that matter.

| File | Purpose |
| --- | --- |
| `requirements.md` | End-to-end requirements document with all sections combined. |
| `README.md` | Quick overview of the audio-only POC. |
| `architecture.md` | Scope, constraints, and supervised learning clarifications. |
| `audio-pipeline.md` | Glass-to-PC signal flow and YAML baseline configuration. |
| `database-design.md` | Logical schema for the two SQLite databases. |
| `versioning.md` | Rules for model/config versioning and logging. |
| `llm-orchestrator.md` | Event classification JSON contracts and tagging logic. |
| `debug-ui.md` | Flask debug UI expectations, including live metrics and review flow. |
| `roadmap.md` | Phase-by-phase implementation plan. |

Need another POC or subsystem? Create a sibling folder inside `docs/` and mirror
this pattern so contributors can find things easily.
