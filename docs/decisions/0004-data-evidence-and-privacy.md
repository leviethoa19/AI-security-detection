# ADR 0004: Data, evidence, and privacy

- **Status:** Accepted
- **Date:** 2026-09-16

## Decision

Use licensed public data and later, if needed, consented controlled recordings. Keep a local rolling buffer and retain only short incident evidence. Do not implement face recognition, continuous cloud upload, or automated emergency contact in the MVP.

## Consequences

- Dataset licenses and provenance must be recorded.
- Private media, generated evidence, model weights, and datasets stay outside Git.
- User-facing language reports potential high-risk visual evidence, not certainty.

