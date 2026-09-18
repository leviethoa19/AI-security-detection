import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  validateEvaluationManifest,
  validateIncidentEvent,
  validateIncidentSnapshot,
} from "./index.js";

const fixturePath = fileURLToPath(
  new URL("../fixtures/incident-event.v1.valid.json", import.meta.url),
);
const snapshotFixturePath = fileURLToPath(
  new URL("../fixtures/incident-snapshot.v1.valid.json", import.meta.url),
);
const evaluationFixturePath = fileURLToPath(
  new URL("../fixtures/evaluation-manifest.v1.valid.json", import.meta.url),
);

test("validates the shared v1 incident fixture", () => {
  const value: unknown = JSON.parse(readFileSync(fixturePath, "utf8"));
  const result = validateIncidentEvent(value);
  assert.equal(result.valid, true, JSON.stringify(result.errors));
});

test("rejects out-of-range risk", () => {
  const value = {
    schemaVersion: "1.0",
    eventId: "7b2fb7ac-e074-4aaf-b73a-3128f914ef34",
    incidentId: "52d5c9db-e097-4656-af2e-84b96fc56b32",
    cameraId: "camera-demo-01",
    trackId: "track-7",
    eventType: "zone_intrusion",
    riskLevel: 5,
    occurredAt: "2026-09-16T00:00:01Z",
    sourceTimeMs: 1250,
    armed: true,
    reasonCodes: ["armed_zone_entry"],
    components: {
      detector: "scripted-v1",
      tracker: "scripted-v1",
      riskEngine: "rules-v1",
      configuration: "golden-default-v1"
    }
  };

  assert.equal(validateIncidentEvent(value).valid, false);
});

test("validates the shared v1 incident snapshot fixture", () => {
  const value: unknown = JSON.parse(readFileSync(snapshotFixturePath, "utf8"));
  const result = validateIncidentSnapshot(value);
  assert.equal(result.valid, true, JSON.stringify(result.errors));
});

test("validates the shared v1 evaluation manifest fixture", () => {
  const value: unknown = JSON.parse(readFileSync(evaluationFixturePath, "utf8"));
  const result = validateEvaluationManifest(value);
  assert.equal(result.valid, true, JSON.stringify(result.errors));
});
