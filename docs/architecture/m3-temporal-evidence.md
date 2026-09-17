# M3 temporal incident and evidence flow

For each sampled video frame:

```text
detect -> track -> annotate -> rolling frame buffer
                    |
                    v
             incremental risk engine
                    |
          new event(s) for this frame
             |                  |
             v                  v
      incident timeline   zone intrusion trigger
             |                  |
             v                  v
      current snapshot    pre/post evidence capture
                                |
                         clip + thumbnail + manifest
```

The rolling buffer is bounded by `evidencePreMs`. Opening an incident copies only buffered frames in that window and collects frames until `evidencePostMs` elapses. A set of previously triggered incident IDs makes the capture idempotent.

The incident snapshot is a projection of the append-only event stream. It records status, current and peak risk, deduplicated reason codes, the ordered timeline, component versions, and temporal configuration. The event stream remains the source of truth.
