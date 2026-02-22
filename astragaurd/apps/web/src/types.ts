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
  decision_mode_hint?: 'IGNORE' | 'DEFER' | 'MANEUVER' | null
  defer_until_utc?: string | null
  trend_pc_peak?: number | null
  trend_pc_slope?: number | null
  trend_pc_stability?: number | null
  plan_delta_v_mps?: number | null
  plan_burn_time_utc?: string | null
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
export type DecisionEnum = 'IGNORE' | 'MONITOR' | 'INSURE' | 'MANEUVER' | 'DEFER'

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
  rationale: string | string[]
  recommended_actions: string[]
  generated_at_utc: string
  llm_provider?: 'claude' | 'gemini' | 'demo' | string
  expected_loss_usd?: number
  var_usd?: number
  llm_usage?: LLMUsage
  llm_cost_usd?: number
  llm_observability?: LLMObservability
}

export interface LLMUsage {
  input_tokens: number
  output_tokens: number
  total_tokens: number
  source: 'provider' | 'estimated' | 'none' | string
}

export interface LLMPricing {
  input_per_million_usd: number
  output_per_million_usd: number
  estimation_mode: string
}

export interface LLMTrace {
  trace_id: string | null
  span_id: string | null
}

export interface LLMObservability {
  provider: string
  model: string
  latency_ms: number
  usage: LLMUsage
  pricing: LLMPricing
  estimated_cost_usd: number
  trace: LLMTrace
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
  payment_intent_id?: string | null
  mode?: string
  id?: string | null
  checkout_url?: string | null
  reason?: string
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

export interface EarthImpact {
  impact_score: number
  ground_lat: number
  ground_lon: number
  nearest_zone: string | null
  zone_category: string | null
  zone_distance_km: number | null
  method: string
  components?: { infra: number; population: number; orbital: number }
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
  maneuver_plans_path?: string | null
}

export interface TrendMetrics {
  pc_peak: number
  pc_slope: number
  pc_stability: number
  window_minutes: number
  cadence_seconds: number
  sample_count: number
  time_to_tca_hours: number
  threshold: number
  critical_override: number
  gate_decision: string
  gate_reason_code: string
  gate_reason: string
}

export interface ManeuverPlan {
  burn_time_utc: string | null
  frame: string
  direction: string | null
  delta_v_mps: number | null
  expected_miss_m: number
  feasibility: string
  early_vs_late_ratio: number | null
  notes: string
}

export interface AutonomyRunResult {
  run_id: string
  status: string
  run_at_utc?: string
  started_at_utc: string
  completed_at_utc: string
  selected_event_id: string
  top_event_ids: string[]
  event?: Record<string, unknown>
  decision?: Record<string, unknown>
  payment?: Record<string, unknown>
  premium_quote_usd?: number
  value_generated_usd?: number
  cost_usd?: number
  llm_observability?: LLMObservability
  roi?: number
  narration_text?: string
  ledger?: Record<string, unknown>
  vision_report: VisionReport
  consultant_decision: ConsultantDecision
  value_signal: ValueSignal
  payment_result: PaymentResult
  voice: VoiceResult
  refs: ArtifactRefs
  earth_impact?: EarthImpact
  expected_loss_adjusted_usd?: number
  decision_mode?: DecisionEnum
  trend_metrics?: TrendMetrics
  defer_until_utc?: string | null
  maneuver_plan?: ManeuverPlan | null
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
