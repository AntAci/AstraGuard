// ── Conjunction events ────────────────────────────────────────────────────────
export interface ConjunctionEvent {
  event_id: string
  primary_norad_id: number
  secondary_norad_id: number
  primary_name: string
  secondary_name: string
  tca_utc: string
  miss_distance_m: number
  pc_assumed: number
  risk_tier: string
  tca_index_snapshot: number
}

export interface TopConjunctionsArtifact {
  schema_version: string
  generated_at_utc: string
  event_count: number
  events: ConjunctionEvent[]
}

// ── Cesium snapshot ───────────────────────────────────────────────────────────
export interface CesiumSnapshotMeta {
  generated_at_utc: string
  schema_version: string
  epoch_utc: string
  step_seconds: number
  timestep_count: number
  object_count: number
}

export interface CesiumObject {
  norad_id: number
  name: string
  source_group: string
  positions_ecef_m: [number, number, number][]
}

export interface CesiumSnapshot {
  meta: CesiumSnapshotMeta
  times_utc: string[]
  objects: CesiumObject[]
}

// ── Autonomy loop ─────────────────────────────────────────────────────────────
export type DecisionEnum = 'IGNORE' | 'MONITOR' | 'INSURE' | 'MANEUVER'

export interface VisionFinding {
  code: string
  severity: string
  detail: string
}

export interface VisionReport {
  vision_report_id: string
  event_id: string
  provider: string
  model_version: string
  status: string
  confidence: number
  summary: string
  findings: VisionFinding[]
  generated_at_utc: string
}

export interface ConsultantDecision {
  decision_id: string
  event_id: string
  provider: string
  model_version: string
  decision: DecisionEnum
  confidence: number
  rationale: string
  recommended_actions: string[]
  generated_at_utc: string
}

export interface PaymentResult {
  payment_result_id: string
  decision_id: string
  event_id: string
  provider: string
  status: string
  amount_usd: number
  currency: string
  transaction_id: string | null
  processed_at_utc: string | null
}

export interface ValueSignal {
  value_signal_id: string
  event_id: string
  provider: string
  model_version: string
  estimated_loss_avoided_usd: number
  intervention_cost_usd: number
  roi_ratio: number
  confidence: number
  generated_at_utc: string
}

export interface VoiceResult {
  provider: string
  status: string
  audio_url: string | null
  script_text: string
}

export interface ArtifactRefs {
  top_conjunctions_path: string
  cesium_snapshot_path: string
}

export interface AutonomyRunResult {
  run_id: string
  status: string
  started_at_utc: string
  completed_at_utc: string
  selected_event_id: string
  top_event_ids: string[]
  vision_report: VisionReport
  consultant_decision: ConsultantDecision
  value_signal: ValueSignal
  payment_result: PaymentResult
  voice: VoiceResult
  refs: ArtifactRefs
  errors: string[]
  model_version: string
}

export interface RunAutonomyLoopResponse {
  run_id: string
  status: string
  result: AutonomyRunResult
}

// ── Artifact manifest ─────────────────────────────────────────────────────────
export interface ArtifactEntry {
  path: string
  schema_version: string
  model_version: string
  sha256: string
  generated_at_utc: string
}

export interface ArtifactsLatest {
  schema_version: string
  generated_at_utc: string
  latest_run_id: string | null
  artifacts: Record<string, ArtifactEntry>
}

// ── UI-only ───────────────────────────────────────────────────────────────────
export type LogLevel = 'info' | 'success' | 'warning' | 'error'

export interface MissionLogEntry {
  id: string
  timestamp: string
  level: LogLevel
  message: string
}
