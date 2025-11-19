# Contributions Guide

Thank you for helping document and implement the AR-SmartAssistant proof of concept (POC).
Read [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full engineering
requirements, then use this short guide to keep the documentation tree easy to
navigate:

1. **Documentation-first workflow**  
   - Update the appropriate markdown file inside `docs/` before adding new code.  
   - Each major subsystem (architecture, audio, database, etc.) already has a dedicated file under `docs/poc-audio-only/`. Extend those files instead of creating duplicates.
2. **Consistent naming**  
   - Use lowercase hyphenated filenames (e.g., `audio-pipeline.md`).  
   - Mirror the folder structure outlined below whenever you add a new area of work.
3. **Single source of truth**  
   - `docs/poc-audio-only/requirements.md` aggregates the complete requirements document. If you update any section file, reflect that change in the main requirements file as well.
4. **Traceable edits**  
   - Reference the relevant section (e.g., “see `docs/poc-audio-only/database-design.md`”) inside your commit messages or pull requests.
5. **Keep it simple**  
   - Prefer short paragraphs, bullet lists, and tables so the documentation stays approachable.

## Repository Structure

```
AR-SmartAssistant/
├── CONTRIBUTIONS.md          # You are here
├── README.md                 # High-level project intro
└── docs/
    ├── README.md             # Documentation index
    └── poc-audio-only/
        ├── README.md         # POC overview
        ├── requirements.md   # Full merged requirements doc
        ├── architecture.md   # Section 1: Architecture constraints
        ├── audio-pipeline.md # Section 2: Audio pipeline specification
        ├── database-design.md# Section 3: Database design
        ├── versioning.md     # Section 4: Versioning & config logging
        ├── llm-orchestrator.md # Section 5: LLM orchestration
        ├── debug-ui.md       # Section 6: Debug UI requirements
        └── roadmap.md        # Section 7: Implementation roadmap
```

When in doubt, add context to the documentation before coding. This keeps the team aligned and makes pull requests easier to review.
