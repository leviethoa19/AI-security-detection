# Context-Aware Indoor Security AI

## Product, Architecture, and Delivery Plan

**Status:** Approved direction; milestones M0–M5 complete
**Primary goal:** Build a portfolio-quality, $0-first prototype that turns indoor video into explainable security incidents using computer vision, tracking, temporal reasoning, risk assessment, evaluation, a secure backend, and a simple mobile client.

## 1. Product definition

### Problem

Frame-level object detection is not a security product. A useful system must connect detections over time, understand protected areas, suppress transient false positives, create one incident instead of many duplicate alerts, preserve evidence, and explain why risk increased.

### Target user

For the prototype, the user is a homeowner or small-site operator monitoring one indoor camera.

### Core user outcome

The user can arm the system, define a protected polygonal zone, replay a video or use a local camera, and receive a single explainable incident when tracked activity crosses meaningful risk thresholds. The user can inspect a thumbnail or short clip, timeline, reason codes, model/configuration versions, and mark the incident as correct or incorrect.

### MVP scenario

1. The system is armed.
2. A person enters a configured protected zone.
3. The tracker preserves that person's identity over time.
4. Zone entry and dwell duration raise the incident risk.
5. Repeated high-risk-object visual evidence can raise it further.
6. The system creates or updates one incident, stores evidence, and exposes it to the mobile client.
7. The person leaves; after a grace period, the incident resolves.

### Explicit non-goals for the MVP

- Face recognition or identity claims
- Multi-camera re-identification
- Continuous cloud video storage
- Automatic police or emergency-service contact
- A generic anomaly-detection research project
- An LLM making the core danger decision
- Production-grade 24/7 deployment or purchased edge hardware
- Claims that a detected object is certainly a weapon

The UI and records will use language such as **potential high-risk object** or **weapon-like visual evidence**.

## 2. Product behavior

### Initial event types

- `person_observed`: a person is present; normally log only
- `zone_intrusion`: a tracked person enters a protected zone while armed
- `extended_presence`: that person remains in the zone beyond a configurable dwell threshold
- `high_risk_evidence`: persistent high-risk-object evidence is associated with the tracked person

### Risk levels

| Level | Meaning | Default action |
|---|---|---|
| 0 — Normal | No actionable activity | No incident |
| 1 — Observed | Person present outside an armed zone | Local log/telemetry |
| 2 — Intrusion | Tracked person enters an armed zone | Open incident and retain evidence |
| 3 — Elevated | Intrusion plus sustained dwell or other context | In-app alert |
| 4 — High | Persistent high-risk visual evidence associated with the person | Urgent in-app alert and highlighted evidence |

Risk is initially deterministic and explainable. A learned event classifier is an optional later comparison, not a dependency of the core product.

### Incident lifecycle

`OPEN -> ACTIVE -> ESCALATED (optional) -> RESOLVING -> RESOLVED`

One physical event should produce one incident. Cooldowns, track continuity, and a resolution grace period prevent alert floods.

### Evidence policy

- Keep a rolling local frame/video buffer.
- Save a short pre-event and post-event clip only when an incident opens.
- Store a representative thumbnail and structured timeline.
- Do not upload continuous video.
- Do not commit private footage, model weights, secrets, or generated evidence to Git.

## 3. Technical architecture

```text
Recorded video / local camera
              |
              v
      Python AI runtime
  decode -> preprocess -> detect
       -> track -> zone context
       -> temporal evidence
       -> risk + incident state
        |                  |
        v                  v
 local replay artifacts   authenticated incident API
                                |
                                v
                   Supabase / PostgreSQL / Storage
                  Auth + RLS + Edge Function as needed
                                |
                    Realtime/read API boundary
                                |
                                v
                 React Native + Expo + TypeScript
                 Expo Router incident client

Offline evaluation uses the same detector, tracker, temporal,
and risk modules as runtime inference—not a duplicate pipeline.
```

### Repository shape

```text
apps/
  mobile/                 Expo + React Native + TypeScript + Expo Router
services/
  ai/                     Python inference, replay, evaluation, training
supabase/
  migrations/             PostgreSQL schema, indexes, RLS policies
  functions/              trusted ingestion/notification orchestration
packages/
  contracts/              versioned event schema and generated TS types
docs/
  decisions/              architecture decision records
  architecture/           diagrams, data flow, threat/privacy notes
  experiments/            reproducible experiment reports
data/
  README.md                acquisition instructions; data itself ignored
```

### AI subsystem

- Python 3.11 target
- PyTorch-based detector behind a small adapter interface
- OpenCV for video I/O and visualization
- NumPy for frame and geometry operations
- Pandas and scikit-learn for analysis, metrics, threshold studies, and optional event-level baseline models
- A detector-agnostic tracker adapter, with ByteTrack as the leading baseline
- Typed configuration for model versions, thresholds, zones, sampling rate, and persistence windows
- `pytest` unit and integration tests
- A small local API boundary only when integration needs it; FastAPI is the default candidate

The exact detector is deliberately not locked in before a short benchmark. Selection will consider pretrained suitability, license, CPU/GPU speed, fine-tuning ergonomics, export path, and accuracy on the project evaluation set.

### Backend subsystem

- Supabase Auth for user identity
- PostgreSQL for cameras, zones, incidents, event observations, model/config versions, and feedback
- Private Supabase Storage bucket for thumbnails and short clips
- Row Level Security on all user-owned records
- Signed URLs for private media
- Edge Function where a trusted server-side ingestion or notification boundary is useful
- No heavyweight video inference in Edge Functions

### Mobile subsystem

- Existing choice retained: React Native, Expo, TypeScript, Expo Router
- Authentication
- Arm/disarm state
- Camera and zone configuration
- Incident list and detail
- Evidence preview and risk timeline
- Explanation/reason codes
- Correct/incorrect feedback
- In-app alerting first; push notification is a later vertical slice

### Core data contracts

Each incident/event record will include:

- Stable incident, camera, and track identifiers
- Event and risk level
- UTC timestamps plus source video time
- Zone and arm-state context
- Reason codes and human-readable explanation inputs
- Aggregated visual evidence, never just one frame score
- Detector, tracker, risk-engine, and configuration versions
- Evidence media references
- Feedback label and optional failure category

Contracts will be versioned so the Python runtime, database, and TypeScript client can evolve independently.

## 4. Evaluation plan

### Evaluation unit

The primary evaluation unit is an **incident**, not an individual frame. Frame/model metrics remain useful diagnostics.

### Metrics

**Detector level**

- Precision, recall, F1, mAP where labels permit
- Precision-recall curves and threshold analysis
- Performance by lighting, distance, occlusion, and object size

**Tracking level**

- ID switches and track fragmentation on annotated scenarios
- Optional IDF1/HOTA if the chosen dataset supports them

**Event level**

- Intrusion and high-risk event precision/recall/F1
- False alerts per camera-hour
- Missed incidents
- Duplicate alerts per physical incident
- Detection/escalation delay

**System level**

- Effective FPS
- Inference, pipeline, and end-to-end latency (median and P95)
- CPU/GPU and memory use

### Required experiment story

The final portfolio must compare at least:

1. Frame-level threshold baseline
2. Confidence smoothing/persistence
3. Tracking plus temporal reasoning
4. Baseline versus fine-tuned detector, if fine-tuning is justified by the baseline errors

Results will be stored as machine-readable tables and summarized with Pandas. The README will report real results and tradeoffs; no target will be presented as achieved before measurement.

### Initial success gates

These are engineering gates, not fabricated accuracy promises:

- Deterministic replay: the same input/config produces the same event output within documented tolerance.
- No duplicate incident for one continuous tracked intrusion in the controlled golden scenarios.
- Transient one-frame high-risk evidence does not trigger Level 4.
- Every alert exposes reason codes and component versions.
- RLS tests prove one user cannot read another user's incidents or media metadata.
- The full prerecorded-video path works before live camera or push notifications are attempted.

Numeric quality targets will be set after the baseline dataset is characterized.

## 5. Milestones and vertical slices

### M0 — Foundation and reproducibility

**Deliverable:** Runnable monorepo skeleton with documented contracts and quality gates.

- Create repository structure and environment setup
- Add decision records, secrets policy, data/model artifact policy, and contribution notes
- Establish Python formatting, typing, linting, and tests
- Establish TypeScript checks and mobile test baseline
- Define versioned event/incident schema
- Add CI for fast checks

**Exit gate:** Clean setup from documented instructions; sample contract validates in Python and TypeScript.

### M1 — Deterministic replay walking skeleton

**Deliverable:** A tiny end-to-end local slice using scripted detections rather than a real detector.

- Read a prerecorded video or synthetic timeline
- Feed scripted person boxes through zone, temporal, risk, and incident logic
- Produce JSON/CSV incident output and an annotated replay artifact
- Unit-test geometry and state transitions

**Why first:** It validates product semantics independently of model quality and makes later model swaps safer.

**Exit gate:** Golden scenarios produce expected incident lifecycle and no duplicates.

### M2 — Person detection, tracking, and zones

**Deliverable:** Real person detections become stable tracks and zone events in replay mode.

- Benchmark a small set of detector candidates and record the selection
- Implement detector and tracker adapters
- Add polygon zone configuration and entry/exit/dwell features
- Overlay boxes, track IDs, zones, and timestamps
- Record runtime benchmarks

**Exit gate:** Controlled videos generate reviewable tracks and zone transitions with reproducible outputs.

### M3 — Temporal risk and incident engine

**Deliverable:** Explainable event-level reasoning over real tracks.

- Sliding-window evidence aggregation
- Risk levels, reason codes, hysteresis, cooldowns, and resolution grace period
- Evidence buffer and incident clip/thumbnail generation
- Configuration snapshots and component versioning

**Exit gate:** Scenario suite covers enter, dwell, exit, re-entry, occlusion, transient detection, and duplicate suppression.

### M4 — High-risk-object evidence baseline

**Deliverable:** One narrowly defined high-risk-object class participates in temporal risk escalation.

- Establish dataset sources and class mapping
- Run pretrained/open baseline or train the minimum baseline if none is credible
- Associate object evidence with a tracked person
- Add persistence rules and hard-negative capture
- Use uncertainty-aware product language throughout

**Exit gate:** Baseline report identifies operating threshold, major failure groups, and whether fine-tuning is justified.

### M5 — Evaluation and error-analysis system

**Deliverable:** Batch replay, metrics, plots, and experiment comparison.

- Dataset manifest and leakage-aware train/validation/test grouping
- Event ground-truth schema
- Batch evaluator and experiment configuration snapshots
- Pandas/NumPy/scikit-learn analysis
- Confidence, latency, subgroup, and failure-category reports
- Baseline versus temporal-system study

**Exit gate:** A single documented command reproduces an experiment table and error report.

### M6 — Targeted fine-tuning and optimization

**Deliverable:** Evidence-based model improvement rather than fine-tuning for appearance's sake.

- Curate permitted public/controlled data and hard negatives
- Validate annotations and class balance
- Fine-tune in PyTorch if M4/M5 show a clear need
- Compare against the frozen baseline on an untouched test set
- Tune thresholds and sampling strategy

**Exit gate:** Keep the new model only if the event-level tradeoff improves and the result is reproducible.

### M7 — Secure backend integration

**Deliverable:** The local AI runtime securely publishes incidents and evidence to Supabase.

- Database migrations and generated types
- Auth and ownership model
- RLS policies and policy tests
- Private media storage and signed access
- Idempotent incident ingestion
- Optional Edge Function for trusted ingestion/notification orchestration

**Exit gate:** Retries do not duplicate incidents; cross-user access tests fail closed.

### M8 — Expo mobile client

**Deliverable:** A simple usable incident client.

- Auth, arm/disarm, and camera/zone settings
- Incident list, incident detail, evidence preview, and timeline
- Explainable risk reasons and model/config metadata
- Correct/incorrect feedback
- Realtime refresh or efficient polling

**Exit gate:** A replayed incident appears in the client, is inspectable, and accepts feedback.

### M9 — Portfolio hardening

**Deliverable:** Reproducible public demonstration and interview-ready evidence.

- Optimize model size/resolution/sampling and report tradeoffs
- Containerize the Python service after local behavior is stable
- Add end-to-end smoke test and robustness scenarios
- Threat/privacy limitations and responsible-use documentation
- Architecture diagrams, experiment results, demo video, and polished README
- Resume bullets and an interview walkthrough grounded in measured results

**Exit gate:** A reviewer can understand, run, and evaluate the project without private data or undocumented setup.

## 6. Testing strategy

- **Unit tests:** polygons, transitions, dwell time, temporal windows, risk scoring, cooldowns, schema validation
- **Golden scenario tests:** fixed detection timelines with exact expected incidents
- **Video integration tests:** short permitted clips with tolerant expected event windows
- **Model tests:** output shape/class mapping, checkpoint compatibility, device fallback
- **Evaluation regression tests:** metrics on a tiny fixture dataset
- **Backend tests:** migrations, idempotency, storage access, and RLS isolation
- **Mobile tests:** critical data mapping, state rendering, and feedback flows
- **End-to-end smoke test:** replay -> incident ingestion -> authenticated client visibility

Large, slow, GPU, and network tests will be explicitly separated from fast local/CI tests.

## 7. Git and delivery discipline

- Preserve a working main branch and implement one milestone slice at a time.
- Use small, meaningful commits tied to observable behavior.
- Run proportional checks before each handoff.
- Record consequential decisions as short architecture decision records.
- Never commit secrets, private footage, large datasets, generated evidence, or model weights.
- Pin dependencies and record model/dataset/config versions.
- Tag portfolio milestones only after their exit gates pass.
- Docker is intentionally late; it packages stable behavior rather than defining it.

## 8. Decision log

| ID | Decision | Status | Rationale |
|---|---|---|---|
| D-001 | Build Scope B: one-camera temporal security-event intelligence | Decided | Best balance of depth, finishability, and JD alignment |
| D-002 | Product semantics and architecture precede model implementation | Decided | Prevents the detector from defining the product |
| D-003 | Keep Expo/React Native/TypeScript/Expo Router, Supabase/PostgreSQL/RLS/Edge Functions, and add Python | Decided | Preserves prior work and uses appropriate boundaries |
| D-004 | Run video inference locally for the $0 prototype | Decided | Avoids cloud inference cost and improves observability |
| D-005 | Use event-level metrics as primary product measures | Decided | False alerts and missed incidents matter more than frame accuracy alone |
| D-006 | Start with explainable rule-based risk and temporal logic | Decided | Testable, inspectable, and suitable before a learned risk model |
| D-007 | No face recognition, continuous upload, or automatic emergency contact in MVP | Decided | Controls privacy, safety, and scope |
| D-008 | Store only incident metadata and short private evidence media | Decided | $0-first and privacy-conscious |
| D-009 | Keep the detector replaceable and choose it by benchmark | Decided | Avoids premature license/performance lock-in |
| D-010 | Make replay/evaluation a first-class product mode | Decided | Creates reproducible ML engineering evidence |
| D-011 | Add Docker only after the local vertical slices stabilize | Decided | Keeps early iteration fast while still satisfying portfolio goals |
| D-012 | Initial high-risk class scope | User decision required | Directly changes dataset and model difficulty |
| D-013 | New monorepo here versus integrating an existing app repository | User decision required | Determines the safe implementation location |
| D-014 | Controlled demo-footage contribution | User decision required before M6 | Affects data diversity and the strongest fine-tuning story |
| D-015 | Push notifications in the portfolio target | Deferred/user decision before M8 | In-app incidents are sufficient for core proof; push adds setup complexity |

## 9. Decisions requiring user input

Only the first two should be resolved before substantive implementation.

### 1. Implementation location — required before M0

**Recommended:** Create a new monorepo in this current workspace and bring in existing app code only if the user later identifies a repository that must be preserved.

Alternative: integrate into an existing Expo/Supabase repository. If selected, the user must provide its exact local path or repository location.

### 2. First high-risk-object scope — required before M4, useful to settle now

**Recommended:** Firearm-like objects only for the first evaluated version; add knives only after the first class is measurable. Knives are smaller, more context-dependent, and likely to expand annotation and false-positive work.

Alternative: firearms and knives from the beginning, accepting higher schedule and data risk.

### 3. Controlled demo footage — required before M6

**Recommended:** The user records a small set of deliberately staged, consented, non-dangerous scenarios later, using harmless props or no object at all. Public/licensed and synthetic/controlled data remain the default. No real weapon is required or encouraged.

Alternative: use only appropriately licensed public datasets and generated/control scenarios, with no personal footage.

### 4. Notification target — required before M8

**Recommended:** In-app incident updates for the core portfolio; add Expo push notifications only if time and account setup permit.

Alternative: make push notifications part of the required portfolio release.

### Later access/permission checkpoints, not product decisions today

- Permission to create/use a Supabase project and provide local environment variables at M7
- Permission to download selected public datasets/model weights when their licenses and sizes are known
- Permission to publish a GitHub repository or deploy anything; local implementation does not imply publication
- Any account login, external upload, paid service, or public release

## 10. Recommended default mandate

Unless the user overrides it, proceed with:

- New monorepo in the current workspace
- Firearm-like evidence as the first narrow high-risk class
- Public/licensed data plus later consented controlled footage
- In-app alerting as required; push notification as optional
- Local, prerecorded-video replay first; webcam/live input later
- One camera and configurable polygon zones
- Measured model selection, rule-based explainable risk, and incident-level evaluation

## 11. Definition of portfolio completion

The project is complete when it has a reproducible prerecorded-video demonstration; real detection, tracking, zones, temporal reasoning, risk, incident evidence, secure backend integration, and an Expo client; an evaluation set and error analysis; a justified baseline-versus-improved comparison; tests for major components and RLS; versioned decisions and contracts; measured performance; and documentation that clearly separates demonstrated capability from future production claims.
