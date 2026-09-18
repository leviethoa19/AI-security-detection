import Ajv2020, { type ErrorObject } from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import incidentEventSchema from "../schema/incident-event.v1.schema.json" with { type: "json" };
import incidentSnapshotSchema from "../schema/incident-snapshot.v1.schema.json" with { type: "json" };
import evaluationManifestSchema from "../schema/evaluation-manifest.v1.schema.json" with { type: "json" };

export type EventType =
  | "person_observed"
  | "zone_intrusion"
  | "extended_presence"
  | "high_risk_evidence"
  | "incident_resolved";

export type ReasonCode =
  | "person_present"
  | "armed_zone_entry"
  | "dwell_threshold_exceeded"
  | "persistent_high_risk_visual_evidence"
  | "track_left_scene"
  | "resolution_grace_elapsed";

export interface IncidentEventV1 {
  schemaVersion: "1.0";
  eventId: string;
  incidentId: string;
  cameraId: string;
  trackId: string;
  zoneId?: string | null;
  eventType: EventType;
  riskLevel: 0 | 1 | 2 | 3 | 4;
  occurredAt: string;
  sourceTimeMs: number;
  armed: boolean;
  reasonCodes: ReasonCode[];
  evidence?: {
    meanScore?: number;
    maxScore?: number;
    positiveFrames?: number;
    windowFrames?: number;
  };
  components: {
    detector: string;
    tracker: string;
    highRiskDetector?: string;
    riskEngine: string;
    configuration: string;
  };
}

export interface IncidentTimelineEntryV1 {
  eventId: string;
  eventType: Exclude<EventType, "person_observed">;
  riskLevel: 0 | 1 | 2 | 3 | 4;
  occurredAt: string;
  sourceTimeMs: number;
  reasonCodes: ReasonCode[];
}

export interface IncidentSnapshotV1 {
  schemaVersion: "1.0";
  incidentId: string;
  cameraId: string;
  trackId: string;
  zoneId: string;
  status: "active" | "escalated" | "resolved";
  currentRiskLevel: 0 | 1 | 2 | 3 | 4;
  peakRiskLevel: 2 | 3 | 4;
  openedAt: string;
  updatedAt: string;
  resolvedAt: string | null;
  openedSourceTimeMs: number;
  updatedSourceTimeMs: number;
  resolvedSourceTimeMs: number | null;
  reasonCodes: ReasonCode[];
  timeline: IncidentTimelineEntryV1[];
  components: IncidentEventV1["components"];
  configuration: {
    dwellThresholdMs: number;
    resolutionGraceMs: number;
    evidencePreMs: number;
    evidencePostMs: number;
    highRiskWindowMs: number;
    highRiskMinPositiveFrames: number;
    highRiskMinMeanScore: number;
  };
}

export interface EvaluationManifestV1 {
  schemaVersion: "1.0";
  datasetId: string;
  description?: string;
  eventTypes: Array<"zone_intrusion" | "extended_presence" | "high_risk_evidence">;
  scenarios: Array<{
    scenarioId: string;
    scenarioPath: string;
    split: "train" | "validation" | "test";
    splitGroup: string;
    durationMs: number;
    subgroups: Record<string, string>;
    groundTruth: Array<{
      eventType: "zone_intrusion" | "extended_presence" | "high_risk_evidence";
      trackId: string;
      onsetTimeMs: number;
      windowEndMs: number;
      failureCategory?: string;
    }>;
  }>;
}

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validateEvent = ajv.compile<IncidentEventV1>(incidentEventSchema);
const validateSnapshot = ajv.compile<IncidentSnapshotV1>(incidentSnapshotSchema);
const validateEvaluation = ajv.compile<EvaluationManifestV1>(evaluationManifestSchema);

export interface ValidationResult {
  valid: boolean;
  errors: ErrorObject[];
}

export function validateIncidentEvent(value: unknown): ValidationResult {
  const valid = validateEvent(value);
  return { valid, errors: validateEvent.errors ? [...validateEvent.errors] : [] };
}

export function validateIncidentSnapshot(value: unknown): ValidationResult {
  const valid = validateSnapshot(value);
  return { valid, errors: validateSnapshot.errors ? [...validateSnapshot.errors] : [] };
}

export function validateEvaluationManifest(value: unknown): ValidationResult {
  const valid = validateEvaluation(value);
  return { valid, errors: validateEvaluation.errors ? [...validateEvaluation.errors] : [] };
}
