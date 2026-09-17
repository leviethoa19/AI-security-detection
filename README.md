# Context-Aware Indoor Security AI

A $0-first portfolio project that turns indoor video into explainable security incidents using computer vision, multi-object tracking, protected-zone context, temporal evidence, risk assessment, and event-level evaluation.

The project is intentionally more than a detector demo. Its core question is whether tracking and temporal reasoning can reduce false alerts while preserving useful incident recall.

## Current status

Milestones 0–3 are complete. The system can replay scripted tracks and process prerecorded video with real person detection, ByteTrack identities, polygon zones, incremental temporal reasoning, incident deduplication, versioned incident snapshots, bounded evidence clips, overlays, and runtime measurements. Cloud credentials and private footage are not required.

## Planned system

```text
video -> detection -> tracking -> scene context -> temporal evidence
      -> risk engine -> incident lifecycle -> Supabase -> Expo client
```

- `services/ai`: Python inference, replay, evaluation, and later fine-tuning
- `packages/contracts`: versioned contracts shared across subsystem boundaries
- `apps/mobile`: Expo Router client (implemented in a later vertical slice)
- `supabase`: migrations, RLS policies, storage, and Edge Functions
- `docs`: architecture and decision records

See [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) for the approved scope and milestone gates.
Progress is tracked in [docs/MILESTONES.md](docs/MILESTONES.md).

## Foundation setup

Prerequisites:

- Node.js 22 or newer
- npm 10 or newer
- Python 3.11 or 3.12

Install JavaScript dependencies:

```sh
npm install
```

Create a Python virtual environment and install the AI workspace with development tools:

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -e "services/ai[dev,vision]"
```

On macOS/Linux, use `.venv/bin/python` instead.

Run the foundation checks:

```sh
npm run check
npm test
.venv/Scripts/python -m ruff check services/ai
.venv/Scripts/python -m mypy --config-file services/ai/pyproject.toml services/ai/src
.venv/Scripts/python -m pytest services/ai/tests
```

Run the deterministic walking skeleton:

```sh
.venv/Scripts/python -m security_ai.replay services/ai/tests/fixtures/entry_dwell_exit.json
```

The golden scenario emits a deterministic sequence: person observed, zone intrusion, extended presence, and incident resolution. Re-entry during the grace period remains part of the same incident; re-entry after resolution starts a new incident.

Run a real video:

```sh
python -m security_ai.video input.mp4 \
  --output-video artifacts/annotated.mp4 \
  --output-events artifacts/events.json \
  --output-incidents artifacts/incidents.json \
  --output-metrics artifacts/metrics.json \
  --evidence-dir artifacts/evidence
```

The evidence directory contains one short clip, trigger-adjacent thumbnail, and manifest per opened incident. It never contains continuous source video and is excluded from Git.

On Windows, clone to a short directory or create the virtual environment at a short path; large PyTorch wheels can exceed the legacy path-length limit in deeply nested directories.

## Data and safety

Do not commit datasets, weights, generated evidence, secrets, or private surveillance footage. The prototype makes uncertain visual-evidence claims; it does not identify people, confirm a weapon, or contact emergency services.
