# ADR 0003: Benchmark before detector selection

- **Status:** Accepted
- **Date:** 2026-09-16

## Decision

Keep detection behind an adapter and select the initial model only after a small documented benchmark. Consider accuracy, latency, hardware fallback, license, pretrained suitability, fine-tuning workflow, and export options.

## Consequences

- No model vendor or checkpoint is embedded in the foundation.
- Benchmark fixtures and decision criteria must be prepared before Milestone 2.
- Model and configuration versions must be recorded on every incident.

