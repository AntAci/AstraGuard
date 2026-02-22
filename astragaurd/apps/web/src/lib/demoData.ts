import type {
  ArtifactsLatest,
  CesiumSnapshot,
  ConjunctionEvent,
  DecisionEnum,
  RunAutonomyLoopResponse,
  TopConjunctionsArtifact,
  TrendMetrics,
  ManeuverPlan,
} from '../types'

const SCHEMA_VERSION = '1.1.0'
const MODEL_VERSION = 'demo_policy_v1'
const GENERATED_AT_UTC = '2026-02-22T10:00:00Z'
const START_TS_MS = Date.parse(GENERATED_AT_UTC)
const STEP_SECONDS = 600
const STEP_MS = STEP_SECONDS * 1000
const TIMESTEP_COUNT = 24

function toIsoUtc(tsMs: number): string {
  return new Date(tsMs).toISOString().replace('.000Z', 'Z')
}

function round3(value: number): number {
  return Math.round(value * 1000) / 1000
}

function buildTrack(radiusM: number, inclinationDeg: number, phaseDeg: number, driftDeg: number): [number, number, number][] {
  const inclination = (inclinationDeg * Math.PI) / 180
  return DEMO_TIMES_UTC.map((_, idx) => {
    const theta = ((phaseDeg + idx * (360 / TIMESTEP_COUNT) + driftDeg * idx) * Math.PI) / 180
    const x = radiusM * Math.cos(theta)
    const y = radiusM * Math.sin(theta) * Math.cos(inclination)
    const z = radiusM * Math.sin(theta) * Math.sin(inclination)
    return [round3(x), round3(y), round3(z)]
  })
}

const DEMO_TIMES_UTC = Array.from({ length: TIMESTEP_COUNT }, (_, idx) => toIsoUtc(START_TS_MS + idx * STEP_MS))

const DEMO_OBJECTS = [
  { norad_id: 90001, name: 'ORION-OPS-1', source_group: 'ACTIVE', positions_ecef_m: buildTrack(6_905_000, 53, 4, 0.25) },
  { norad_id: 90002, name: 'ORION-OPS-2', source_group: 'ACTIVE', positions_ecef_m: buildTrack(6_915_000, 54, 66, 0.22) },
  { norad_id: 90003, name: 'HAWK-EARTH-7', source_group: 'ACTIVE', positions_ecef_m: buildTrack(6_890_000, 97, 130, 0.14) },
  { norad_id: 90004, name: 'PIONEER-RELAY-2', source_group: 'ACTIVE', positions_ecef_m: buildTrack(6_980_000, 75, 188, 0.2) },
  { norad_id: 80001, name: 'DEBRIS-CLUSTER-A19', source_group: 'DEBRIS', positions_ecef_m: buildTrack(6_940_000, 52, 12, 0.29) },
  { norad_id: 80002, name: 'DEBRIS-CLUSTER-F04', source_group: 'DEBRIS', positions_ecef_m: buildTrack(6_875_000, 99, 116, 0.18) },
  { norad_id: 80003, name: 'DEBRIS-CLUSTER-R55', source_group: 'DEBRIS', positions_ecef_m: buildTrack(6_960_000, 76, 212, 0.12) },
  { norad_id: 80004, name: 'DEBRIS-CLUSTER-K07', source_group: 'DEBRIS', positions_ecef_m: buildTrack(6_930_000, 58, 274, 0.16) },
]

function eventId(primaryId: number, secondaryId: number, tcaIndex: number): string {
  return `EVT-${primaryId}-${secondaryId}-${DEMO_TIMES_UTC[tcaIndex]}`
}

function byNorad(noradId: number): string {
  return DEMO_OBJECTS.find((obj) => obj.norad_id === noradId)?.name ?? `Object ${noradId}`
}

type DemoEvent = ConjunctionEvent & {
  relative_speed_mps: number
}

const DEMO_EVENTS: DemoEvent[] = [
  {
    event_id: eventId(90001, 80001, 8),
    primary_norad_id: 90001,
    secondary_norad_id: 80001,
    primary_name: byNorad(90001),
    secondary_name: byNorad(80001),
    tca_utc: DEMO_TIMES_UTC[8],
    tca_index_snapshot: 8,
    miss_distance_m: 128,
    relative_speed_mps: 58.2,
    pc_assumed: 2.4e-3,
    risk_tier: 'CRITICAL',
    decision_mode_hint: 'MANEUVER',
    defer_until_utc: null,
    trend_pc_peak: 2.2e-3,
    trend_pc_slope: 1.3e-4,
    trend_pc_stability: 0.84,
    plan_delta_v_mps: 0.23,
    plan_burn_time_utc: DEMO_TIMES_UTC[6],
  },
  {
    event_id: eventId(90003, 80002, 5),
    primary_norad_id: 90003,
    secondary_norad_id: 80002,
    primary_name: byNorad(90003),
    secondary_name: byNorad(80002),
    tca_utc: DEMO_TIMES_UTC[5],
    tca_index_snapshot: 5,
    miss_distance_m: 410,
    relative_speed_mps: 133.9,
    pc_assumed: 4.2e-4,
    risk_tier: 'HIGH',
    decision_mode_hint: 'MANEUVER',
    defer_until_utc: null,
    trend_pc_peak: 3.9e-4,
    trend_pc_slope: 4.8e-5,
    trend_pc_stability: 0.79,
    plan_delta_v_mps: 0.16,
    plan_burn_time_utc: DEMO_TIMES_UTC[3],
  },
  {
    event_id: eventId(90002, 80003, 13),
    primary_norad_id: 90002,
    secondary_norad_id: 80003,
    primary_name: byNorad(90002),
    secondary_name: byNorad(80003),
    tca_utc: DEMO_TIMES_UTC[13],
    tca_index_snapshot: 13,
    miss_distance_m: 970,
    relative_speed_mps: 221.5,
    pc_assumed: 7.5e-5,
    risk_tier: 'MEDIUM',
    decision_mode_hint: 'DEFER',
    defer_until_utc: DEMO_TIMES_UTC[16],
    trend_pc_peak: 8.8e-5,
    trend_pc_slope: -1.6e-5,
    trend_pc_stability: 0.41,
    plan_delta_v_mps: null,
    plan_burn_time_utc: null,
  },
  {
    event_id: eventId(90004, 80004, 19),
    primary_norad_id: 90004,
    secondary_norad_id: 80004,
    primary_name: byNorad(90004),
    secondary_name: byNorad(80004),
    tca_utc: DEMO_TIMES_UTC[19],
    tca_index_snapshot: 19,
    miss_distance_m: 1450,
    relative_speed_mps: 276.3,
    pc_assumed: 8.0e-5,
    risk_tier: 'MEDIUM',
    decision_mode_hint: 'DEFER',
    defer_until_utc: DEMO_TIMES_UTC[21],
    trend_pc_peak: 8.6e-5,
    trend_pc_slope: -2.1e-5,
    trend_pc_stability: 0.28,
    plan_delta_v_mps: null,
    plan_burn_time_utc: null,
  },
  {
    event_id: eventId(90001, 90004, 17),
    primary_norad_id: 90001,
    secondary_norad_id: 90004,
    primary_name: byNorad(90001),
    secondary_name: byNorad(90004),
    tca_utc: DEMO_TIMES_UTC[17],
    tca_index_snapshot: 17,
    miss_distance_m: 4200,
    relative_speed_mps: 19.5,
    pc_assumed: 2.0e-6,
    risk_tier: 'LOW',
    decision_mode_hint: 'IGNORE',
    defer_until_utc: null,
    trend_pc_peak: 2.3e-6,
    trend_pc_slope: -2.3e-7,
    trend_pc_stability: 0.15,
    plan_delta_v_mps: null,
    plan_burn_time_utc: null,
  },
  {
    event_id: eventId(90002, 80004, 21),
    primary_norad_id: 90002,
    secondary_norad_id: 80004,
    primary_name: byNorad(90002),
    secondary_name: byNorad(80004),
    tca_utc: DEMO_TIMES_UTC[21],
    tca_index_snapshot: 21,
    miss_distance_m: 7900,
    relative_speed_mps: 311.4,
    pc_assumed: 1.2e-7,
    risk_tier: 'LOW',
    decision_mode_hint: 'IGNORE',
    defer_until_utc: null,
    trend_pc_peak: 1.5e-7,
    trend_pc_slope: -2.0e-8,
    trend_pc_stability: 0.09,
    plan_delta_v_mps: null,
    plan_burn_time_utc: null,
  },
]

function trendMetricsFor(event: DemoEvent): TrendMetrics {
  const decision = event.decision_mode_hint ?? 'IGNORE'
  const gateReasonCode = decision === 'MANEUVER'
    ? 'SUSTAINED_RISK'
    : decision === 'DEFER'
      ? 'TRANSIENT_RISK'
      : 'LOW_RISK'
  const gateReason = decision === 'MANEUVER'
    ? 'Risk is sustained near TCA; minimum delta-v burn is feasible.'
    : decision === 'DEFER'
      ? 'Risk peak is not stable enough yet; defer and refresh at next window.'
      : 'Risk trend remains low and decreasing; no immediate intervention required.'
  return {
    pc_peak: event.trend_pc_peak ?? event.pc_assumed,
    pc_slope: event.trend_pc_slope ?? 0,
    pc_stability: event.trend_pc_stability ?? 0,
    window_minutes: 30,
    cadence_seconds: 60,
    sample_count: 31,
    time_to_tca_hours: Math.max(0, (Date.parse(event.tca_utc) - START_TS_MS) / 3_600_000),
    threshold: 1e-5,
    critical_override: 1e-3,
    gate_decision: decision,
    gate_reason_code: gateReasonCode,
    gate_reason: gateReason,
  }
}

function maneuverPlanFor(event: DemoEvent): ManeuverPlan | null {
  if (event.decision_mode_hint !== 'MANEUVER') return null
  return {
    burn_time_utc: event.plan_burn_time_utc ?? null,
    frame: 'RTN',
    direction: 'N',
    delta_v_mps: event.plan_delta_v_mps ?? null,
    expected_miss_m: Math.max(event.miss_distance_m * 5.5, 700),
    feasibility: 'feasible',
    early_vs_late_ratio: 0.42,
    notes: 'Chosen by minimum-delta-v sweep across early/late candidate burns.',
  }
}

type PlanEntry = {
  event_id: string
  decision_mode_hint: DecisionEnum
  defer_until_utc: string | null
  trend_metrics: TrendMetrics
  maneuver_plan: ManeuverPlan | null
}

const DEMO_PLANS_BY_EVENT_ID: Record<string, PlanEntry> = Object.fromEntries(
  DEMO_EVENTS.map((event) => [
    event.event_id,
    {
      event_id: event.event_id,
      decision_mode_hint: (event.decision_mode_hint ?? 'IGNORE') as DecisionEnum,
      defer_until_utc: event.defer_until_utc ?? null,
      trend_metrics: trendMetricsFor(event),
      maneuver_plan: maneuverPlanFor(event),
    } satisfies PlanEntry,
  ])
)

export const demoArtifactsLatest: ArtifactsLatest = {
  schema_version: SCHEMA_VERSION,
  generated_at_utc: GENERATED_AT_UTC,
  latest_run_id: 'RUN-DEMO-20260222',
  artifacts: {
    top_conjunctions: {
      path: 'demo/top_conjunctions.json',
      schema_version: SCHEMA_VERSION,
      model_version: MODEL_VERSION,
      sha256: 'demo',
      generated_at_utc: GENERATED_AT_UTC,
    },
    cesium_snapshot: {
      path: 'demo/cesium_orbits_snapshot.json',
      schema_version: SCHEMA_VERSION,
      model_version: MODEL_VERSION,
      sha256: 'demo',
      generated_at_utc: GENERATED_AT_UTC,
    },
    maneuver_plans: {
      path: 'demo/maneuver_plans.json',
      schema_version: SCHEMA_VERSION,
      model_version: MODEL_VERSION,
      sha256: 'demo',
      generated_at_utc: GENERATED_AT_UTC,
    },
  },
}

export const demoTopConjunctions: TopConjunctionsArtifact = {
  schema_version: SCHEMA_VERSION,
  generated_at_utc: GENERATED_AT_UTC,
  event_count: DEMO_EVENTS.length,
  events: DEMO_EVENTS,
}

export const demoManeuverPlans: Record<string, unknown> = {
  schema_version: SCHEMA_VERSION,
  generated_at_utc: GENERATED_AT_UTC,
  event_count: DEMO_EVENTS.length,
  plans_by_event_id: DEMO_PLANS_BY_EVENT_ID,
}

export const demoSnapshot: CesiumSnapshot = {
  meta: {
    generated_at_utc: GENERATED_AT_UTC,
    schema_version: SCHEMA_VERSION,
    epoch_utc: DEMO_TIMES_UTC[0],
    step_seconds: STEP_SECONDS,
    timestep_count: TIMESTEP_COUNT,
    object_count: DEMO_OBJECTS.length,
  },
  times_utc: DEMO_TIMES_UTC,
  objects: DEMO_OBJECTS,
}

function decisionSummary(decision: DecisionEnum): { reasonCode: string; reasonText: string; confidence: number } {
  if (decision === 'MANEUVER') {
    return {
      reasonCode: 'SUSTAINED_RISK',
      reasonText: 'Sustained collision-risk trend and feasible low delta-v path justify a burn.',
      confidence: 0.93,
    }
  }
  if (decision === 'DEFER') {
    return {
      reasonCode: 'TRANSIENT_RISK',
      reasonText: 'Risk remains below intervention threshold stability; defer and refresh trajectory data.',
      confidence: 0.84,
    }
  }
  return {
    reasonCode: 'LOW_RISK',
    reasonText: 'Risk trend is low and decaying; no immediate operational cost required.',
    confidence: 0.78,
  }
}

function recommendedActions(decision: DecisionEnum): string[] {
  if (decision === 'MANEUVER') return ['schedule_maneuver', 'monitor_24h']
  if (decision === 'DEFER') return ['defer_and_rerun', 'monitor_6h']
  return ['no_action']
}

export function createDemoAutonomyResponse(targetEventId: string | null): RunAutonomyLoopResponse {
  const selected = DEMO_EVENTS.find((event) => event.event_id === targetEventId) ?? DEMO_EVENTS[0]
  const plan = DEMO_PLANS_BY_EVENT_ID[selected.event_id]
  const decision = (plan.decision_mode_hint ?? 'IGNORE') as DecisionEnum
  const decisionMeta = decisionSummary(decision)

  const runTimestamp = Date.now()
  const runId = `RUN-DEMO-${runTimestamp}`
  const generatedAt = toIsoUtc(runTimestamp)
  const completedAt = toIsoUtc(runTimestamp + 1200)
  const llmCostUsd = 0

  const assetValueUsd = 180_000_000
  const expectedLossAdjustedUsd = selected.pc_assumed * assetValueUsd * 1.22
  const costUsd = decision === 'MANEUVER' ? 4_800 : 0
  const valueGeneratedUsd = decision === 'IGNORE'
    ? 0
    : decision === 'DEFER'
      ? expectedLossAdjustedUsd * 0.3
      : expectedLossAdjustedUsd * 0.94
  const roi = costUsd > 0 ? valueGeneratedUsd / costUsd : 0

  const paymentStatus = decision === 'MANEUVER' ? 'scheduled' : 'skipped'
  const paymentCheckoutUrl = decision === 'MANEUVER'
    ? `/?demo_checkout=maneuver&run_id=${encodeURIComponent(runId)}`
    : null
  const actions = recommendedActions(decision)

  return {
    run_id: runId,
    status: 'completed',
    result: {
      run_id: runId,
      status: 'completed',
      run_at_utc: generatedAt,
      started_at_utc: generatedAt,
      completed_at_utc: completedAt,
      selected_event_id: selected.event_id,
      top_event_ids: DEMO_EVENTS.slice(0, 5).map((event) => event.event_id),
      event: selected as unknown as Record<string, unknown>,
      decision: {
        decision,
        decision_mode: decision,
        llm_provider: 'demo',
        expected_loss_usd: expectedLossAdjustedUsd,
        confidence: decisionMeta.confidence,
        rationale: [
          decisionMeta.reasonText,
          'Optimization objective: minimize recurring conjunction-response cost while preserving mission safety margin.',
        ],
        decision_reason_code: decisionMeta.reasonCode,
        decision_reason_text: decisionMeta.reasonText,
        defer_until_utc: plan.defer_until_utc,
        trend_metrics: plan.trend_metrics,
        maneuver_plan: plan.maneuver_plan,
      },
      payment: {
        provider: 'simulator',
        status: paymentStatus,
        mode: decision === 'MANEUVER' ? 'maneuver' : 'none',
        amount_usd: costUsd,
        currency: 'usd',
        id: paymentStatus === 'scheduled' ? `SIM-${runId}` : null,
        checkout_url: paymentCheckoutUrl,
      },
      premium_quote_usd: 0,
      value_generated_usd: valueGeneratedUsd,
      cost_usd: costUsd,
      llm_observability: {
        provider: 'demo',
        model: MODEL_VERSION,
        latency_ms: 0,
        usage: {
          input_tokens: 0,
          output_tokens: 0,
          total_tokens: 0,
          source: 'none',
        },
        pricing: {
          input_per_million_usd: 0,
          output_per_million_usd: 0,
          estimation_mode: 'demo',
        },
        estimated_cost_usd: llmCostUsd,
        trace: {
          trace_id: null,
          span_id: null,
        },
      },
      roi,
      narration_text: `Demo briefing: ${selected.primary_name} vs ${selected.secondary_name}. Decision ${decision}. Expected loss avoided $${Math.round(valueGeneratedUsd).toLocaleString()}.`,
      ledger: {
        mode: 'demo',
      },
      vision_report: {
        vision_report_id: `VR-${runId}`,
        event_id: selected.event_id,
        provider: 'demo',
        model_version: MODEL_VERSION,
        status: 'completed',
        confidence: 0.89,
        summary: 'No anomalous pattern conflict with trend gate.',
        findings: [
          {
            code: 'TREND_CONSISTENT',
            severity: 'low',
            detail: 'Trend-gate and kinematic indicators are consistent in this scenario.',
          },
        ],
        generated_at_utc: completedAt,
      },
      consultant_decision: {
        decision_id: `DEC-${runId}`,
        event_id: selected.event_id,
        provider: 'demo',
        model_version: MODEL_VERSION,
        decision,
        confidence: decisionMeta.confidence,
        rationale: [
          decisionMeta.reasonText,
          'Deterministic demo scenario selected for hackathon presentation stability.',
        ],
        recommended_actions: actions,
        generated_at_utc: completedAt,
        llm_provider: 'demo',
        expected_loss_usd: expectedLossAdjustedUsd,
        var_usd: expectedLossAdjustedUsd * 1.08,
      },
      value_signal: {
        value_signal_id: `VAL-${runId}`,
        event_id: selected.event_id,
        provider: 'demo',
        model_version: MODEL_VERSION,
        estimated_loss_avoided_usd: valueGeneratedUsd,
        intervention_cost_usd: costUsd,
        roi_ratio: roi,
        confidence: 0.86,
        generated_at_utc: completedAt,
      },
      payment_result: {
        payment_result_id: `PAY-${runId}`,
        decision_id: `DEC-${runId}`,
        event_id: selected.event_id,
        provider: 'simulator',
        status: paymentStatus,
        amount_usd: costUsd,
        currency: 'USD',
        transaction_id: paymentStatus === 'scheduled' ? `SIM-TX-${runId}` : null,
        processed_at_utc: completedAt,
        payment_intent_id: null,
        checkout_url: paymentCheckoutUrl,
      },
      voice: {
        provider: 'demo',
        status: 'skipped',
        audio_url: null,
        script_text: 'Demo mode active. Voice output is disabled for deterministic playback.',
      },
      refs: {
        top_conjunctions_path: 'demo/top_conjunctions.json',
        cesium_snapshot_path: 'demo/cesium_orbits_snapshot.json',
        maneuver_plans_path: 'demo/maneuver_plans.json',
      },
      earth_impact: {
        impact_score: decision === 'MANEUVER' ? 0.68 : decision === 'DEFER' ? 0.36 : 0.19,
        ground_lat: 34.05,
        ground_lon: -118.25,
        nearest_zone: 'Los Angeles Metro',
        zone_category: 'urban',
        zone_distance_km: decision === 'MANEUVER' ? 92 : 410,
        method: 'demo_weighted',
        components: {
          infra: decision === 'MANEUVER' ? 0.74 : 0.41,
          population: decision === 'MANEUVER' ? 0.7 : 0.38,
          orbital: decision === 'MANEUVER' ? 0.62 : 0.34,
        },
      },
      expected_loss_adjusted_usd: expectedLossAdjustedUsd,
      decision_mode: decision,
      trend_metrics: plan.trend_metrics,
      defer_until_utc: plan.defer_until_utc,
      maneuver_plan: plan.maneuver_plan,
      errors: [],
      model_version: MODEL_VERSION,
    },
  }
}
