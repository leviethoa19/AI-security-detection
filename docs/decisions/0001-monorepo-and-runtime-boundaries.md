# ADR 0001: Monorepo and runtime boundaries

- **Status:** Accepted
- **Date:** 2026-09-16

## Decision

Use one monorepo with a Python AI service, an Expo/TypeScript client, shared contracts, and Supabase infrastructure. Heavy video inference remains local for the $0 prototype; Supabase Edge Functions may perform trusted ingestion and notification orchestration but not model inference.

## Consequences

- Cross-system contracts must be explicit and versioned.
- Local replay works without cloud credentials.
- The AI environment can evolve independently from the client.
- Deployment packaging is deferred until runtime behavior stabilizes.

