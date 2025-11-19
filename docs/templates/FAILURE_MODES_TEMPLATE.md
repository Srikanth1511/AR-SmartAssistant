# Failure Modes Template

Copy this template into `FAILURE_MODES.md` (or the relevant PR section) when
documenting changes that touch GPU inference, the database, networking, file
I/O, or external services.

```markdown
## Component: <name>

### Happy Path
Input: <what goes in>
Output: <what comes out>
Latency: <expected metrics>

### Failure Modes

1. **<failure name>**
   - Trigger: <what causes it>
   - Observable: <how to detect>
   - Recovery: <how the system reacts>
   - User Impact: <what the user sees>
   - Mitigation: <how we reduce the risk>
```

Reference [`CONTRIBUTING.md`](../../CONTRIBUTING.md) for detailed examples and
rejection criteria.
