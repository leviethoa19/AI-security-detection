# System context

## Runtime boundaries

```text
Recorded video or local camera
              |
              v
      Python AI runtime
  detection / tracking / context
  temporal evidence / incidents
        |                  |
        v                  v
 replay artifacts     trusted ingestion
                           |
                           v
                 Supabase + PostgreSQL
                    Auth / RLS / Storage
                           |
                           v
                 Expo mobile application
```

The AI runtime owns visual inference and event reasoning. Supabase owns authenticated application data, private evidence references, and authorization. The mobile client displays and configures the system but does not infer risk.

## Shared boundary

`packages/contracts` contains versioned JSON Schemas and TypeScript definitions. Python validates emitted events against the same schema. Supabase migrations will mirror the stable fields and preserve the full versioned payload for traceability.

## Offline-first path

Replay and evaluation use the same Python modules as runtime inference. This prevents an evaluation-only implementation from drifting away from product behavior.

