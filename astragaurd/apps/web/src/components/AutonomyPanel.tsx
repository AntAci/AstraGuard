import type { RunAutonomyLoopResponse, ConjunctionEvent, EarthImpact, TrendMetrics, ManeuverPlan } from '../types'

interface Props {
  result: RunAutonomyLoopResponse | null
  selectedEvent: ConjunctionEvent | null
  isRunning: boolean
  runError: string | null
  onRun: () => void
}

function decisionSummary(mode: string): { title: string; hint: string } {
  if (mode === 'MANEUVER') {
    return { title: 'Execute avoidance burn', hint: 'Risk is sustained near TCA and maneuver is feasible.' }
  }
  if (mode === 'DEFER') {
    return { title: 'Defer and re-evaluate', hint: 'Risk is not sustained enough right now to justify immediate action.' }
  }
  if (mode === 'INSURE') {
    return { title: 'Trigger contingency cover', hint: 'Financial hedge selected as the preferred protective action.' }
  }
  return { title: 'No intervention now', hint: 'Current risk profile does not justify immediate operational cost.' }
}

function trendDirectionLabel(slope: unknown): string {
  const parsed = Number(slope)
  if (!Number.isFinite(parsed)) return 'Unknown'
  if (parsed > 0) return 'Rising'
  if (parsed < 0) return 'Falling'
  return 'Flat'
}

function friendlyActionLabel(action: string): string {
  if (action === 'schedule_maneuver') return 'Schedule avoidance burn'
  if (action === 'defer_and_rerun') return 'Re-run at defer time'
  if (action === 'execute_insurance_purchase') return 'Trigger contingency cover'
  if (action === 'monitor_24h') return 'Monitor for 24 hours'
  if (action === 'monitor_6h') return 'Monitor for 6 hours'
  if (action === 'no_action') return 'No immediate action'
  return action.replace(/_/g, ' ')
}

function formatUtcDateTime(value: string | null | undefined): string {
  if (!value) return '-'
  const parsed = Date.parse(value)
  if (!Number.isFinite(parsed)) return String(value)
  const base = new Date(parsed).toLocaleString('en-US', {
    month: 'short',
    day: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'UTC',
  })
  return `${base} UTC`
}

function asFiniteNumber(value: unknown): number | null {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function formatFixed(value: unknown, digits: number): string {
  const parsed = asFiniteNumber(value)
  if (parsed == null) return '-'
  return parsed.toFixed(digits)
}

function formatScientific(value: unknown, digits = 2): string {
  const parsed = asFiniteNumber(value)
  if (parsed == null) return '-'
  return parsed.toExponential(digits)
}

function formatPercent(value: unknown, digits = 0): string {
  const parsed = asFiniteNumber(value)
  if (parsed == null) return '-'
  return `${(parsed * 100).toFixed(digits)}%`
}

function sanitizeCopy(text: string): string {
  return text
    .replace(/\bdeciis\b/gi, 'decision')
    .replace(/\s+/g, ' ')
    .trim()
}

function hasOwnFields(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && Object.keys(value as Record<string, unknown>).length > 0)
}

export default function AutonomyPanel({ result, selectedEvent, isRunning, runError, onRun }: Props) {
  const importMetaEnv = (import.meta as unknown as { env?: Record<string, string | undefined> }).env
  const isDemoMode = importMetaEnv?.VITE_DEMO_MODE === '1'
  const decision = result?.result.consultant_decision
  const value = result?.result.value_signal
  const payment = result?.result.payment_result
  const phase3Decision = result?.result.decision as
    | {
      llm_provider?: string
      expected_loss_usd?: number
      rationale?: string[]
      confidence?: number
      decision_mode?: string
      defer_until_utc?: string | null
      decision_reason_text?: string
      decision_reason_code?: string
    }
    | undefined
  const phase3Payment = result?.result.payment as
    | { id?: string | null; checkout_url?: string | null; status?: string; mode?: string }
    | undefined
  const voice = result?.result.voice
  const earthImpact = result?.result.earth_impact as EarthImpact | undefined
  const trendMetricsPayload = result?.result.trend_metrics
  const trendMetrics = hasOwnFields(trendMetricsPayload) ? (trendMetricsPayload as TrendMetrics) : undefined
  const maneuverPlan = result?.result.maneuver_plan as ManeuverPlan | null | undefined
  const decisionMode = (result?.result.decision_mode ?? phase3Decision?.decision_mode ?? decision?.decision ?? 'IGNORE').toUpperCase()
  const deferUntil = result?.result.defer_until_utc ?? phase3Decision?.defer_until_utc ?? null
  const adjustedLoss = result?.result.expected_loss_adjusted_usd
  const narration = result?.result.narration_text
  const decisionRationaleRaw = Array.isArray(decision?.rationale)
    ? decision.rationale.join(' ')
    : (decision?.rationale ?? '')
  const decisionRationale = sanitizeCopy(decisionRationaleRaw)
  const decisionReasonRaw = typeof phase3Decision?.decision_reason_text === 'string'
    ? phase3Decision.decision_reason_text
    : ''
  const decisionReason = sanitizeCopy(decisionReasonRaw)
  const summary = decisionSummary(decisionMode)
  const whyText = decisionReason || sanitizeCopy(trendMetrics?.gate_reason ?? '') || summary.hint
  const showTechnicalRationale = decisionRationale.trim().length > 0 && decisionRationale.trim() !== whyText.trim()
  const decisionRationaleShort = decisionRationale.length > 360
    ? `${decisionRationale.slice(0, 357)}...`
    : decisionRationale
  const roiRatio = asFiniteNumber(result?.result.roi ?? value?.roi_ratio) ?? 0
  const confidence = asFiniteNumber(phase3Decision?.confidence ?? decision?.confidence) ?? 0
  const recommendedActions = Array.isArray(decision?.recommended_actions) ? decision.recommended_actions : []
  const lossAvoidedUsd = Number(value?.estimated_loss_avoided_usd ?? 0)
  const earthImpactScore = asFiniteNumber(earthImpact?.impact_score) ?? 0
  const isHighEarthImpact = earthImpactScore > 0.5
  const earthImpactColor = isHighEarthImpact ? 'var(--red)' : 'var(--green)'
  const earthImpactBackground = isHighEarthImpact ? 'rgba(176, 64, 63, 0.14)' : 'rgba(46, 138, 102, 0.14)'
  const spendSectionTitle = decisionMode === 'MANEUVER'
    ? 'ACTION COST'
    : decisionMode === 'INSURE'
      ? 'COVERAGE COST'
      : 'IMMEDIATE COST'
  const paymentStatus = String(payment?.status ?? '').toLowerCase()
  const paymentIsSkippedLike = paymentStatus === 'skipped' || paymentStatus === 'deferred'
  const paymentStatusColor = paymentIsSkippedLike ? 'var(--yellow)' : 'var(--green)'
  const paymentStatusBg = paymentIsSkippedLike ? 'rgba(155, 120, 7, 0.1)' : 'rgba(46, 138, 102, 0.1)'
  const paymentId = phase3Payment?.id ?? payment?.id ?? payment?.transaction_id ?? payment?.payment_intent_id ?? null
  const checkoutUrl = phase3Payment?.checkout_url ?? payment?.checkout_url ?? null
  const firstAction = decision?.recommended_actions?.[0]
  const solutionAction = friendlyActionLabel(firstAction ?? 'no_action')
  const voiceStatus = String(voice?.status ?? '').toLowerCase()
  const voiceHasError = /error|failed|unavailable/.test(voiceStatus)
  const showVoice = Boolean(voice) && !(isDemoMode && voiceHasError)
  const maneuverDeltaV = asFiniteNumber(maneuverPlan?.delta_v_mps)
  const maneuverEarlyLateRatio = asFiniteNumber(maneuverPlan?.early_vs_late_ratio)
  const timingComparison = (() => {
    if (!maneuverPlan || maneuverDeltaV == null || maneuverEarlyLateRatio == null) {
      return null
    }
    const ratio = maneuverEarlyLateRatio
    if (!Number.isFinite(ratio) || ratio <= 0) return null
    const selectedDeltaV = maneuverDeltaV
    const lateDeltaV = selectedDeltaV / ratio
    const savingsDeltaV = Math.max(0, lateDeltaV - selectedDeltaV)
    const savingsPct = lateDeltaV > 0 ? (savingsDeltaV / lateDeltaV) * 100 : 0
    return {
      ratio,
      lateDeltaV,
      savingsDeltaV,
      savingsPct,
    }
  })()

  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div className="panel-header">Autonomy Loop</div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px' }}>
        {/* Run button */}
        <button
          className="btn-run"
          onClick={onRun}
          disabled={isRunning}
          style={{ marginBottom: 16 }}
        >
          {isRunning ? (
            <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
              <span className="spinner" />
              Running...
            </span>
          ) : (
            `Run Optimization${selectedEvent ? ` — ${selectedEvent.event_id}` : ''}`
          )}
        </button>

        {runError && !isRunning && (
          <div style={{
            marginBottom: 14,
            padding: '8px 10px',
            borderRadius: 8,
            border: '1px solid rgba(176, 64, 63, 0.28)',
            background: 'rgba(176, 64, 63, 0.08)',
            color: 'var(--red)',
            fontSize: 11,
            lineHeight: 1.45,
          }}>
            {runError}
          </div>
        )}

        {/* No result state */}
        {!result && !isRunning && (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            {selectedEvent ? (
              <>
                <div style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 8 }}>
                  Selected: <span style={{ color: 'var(--accent-primary)', fontWeight: 600 }}>{selectedEvent.primary_name}</span>
                </div>
                <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                  Click above to analyze this conjunction event
                </div>
              </>
            ) : (
              <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                Select an event or run to analyze top-risk event
              </div>
            )}
          </div>
        )}

        {/* Decision result */}
        {decision && (
          <>
            {/* Decision badge */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em', marginBottom: 6 }}>
                DECISION
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span className={`badge badge-${decisionMode}`}>{decisionMode}</span>
                <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                  {formatUtcDateTime(decision.generated_at_utc)}
                </span>
              </div>
              <div style={{
                marginTop: 8,
                padding: '8px 10px',
                background: 'var(--bg-muted)',
                borderRadius: 8,
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-primary)',
                fontSize: 11,
                lineHeight: 1.45,
              }}>
                <div style={{ fontWeight: 700, marginBottom: 2 }}>{summary.title}</div>
                <div style={{ color: 'var(--text-muted)' }}>{summary.hint}</div>
              </div>
              {deferUntil && (
                <div style={{ color: 'var(--yellow)', fontSize: 11, marginTop: 6 }}>
                  Defer until: {formatUtcDateTime(deferUntil)}
                </div>
              )}
            </div>

            <div style={{ marginBottom: 16 }}>
              <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em', marginBottom: 8 }}>
                SOLUTION SNAPSHOT
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <ValueMetric label="Recommended Action" value={decisionMode} color="var(--accent-primary)" />
                <ValueMetric
                  label="Immediate Cost"
                  value={`$${formatFixed(payment?.amount_usd ?? 0, 2)}`}
                  color={decisionMode === 'MANEUVER' || decisionMode === 'INSURE' ? 'var(--red)' : 'var(--green)'}
                />
                <ValueMetric label="Next Step" value={solutionAction} wide />
              </div>
              <div style={{ marginTop: 8, color: 'var(--text-muted)', fontSize: 10, lineHeight: 1.45 }}>
                {lossAvoidedUsd > 0
                  ? `Expected value preserved: $${Math.round(lossAvoidedUsd).toLocaleString()} at immediate cost $${formatFixed(payment?.amount_usd ?? 0, 2)}.`
                  : 'No immediate spend required for this decision path.'}
              </div>
            </div>

            {/* Trend metrics */}
            {trendMetrics && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em', marginBottom: 8 }}>
                  TREND GATE
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <ValueMetric label="Peak Risk (Pc)" value={formatScientific(trendMetrics.pc_peak, 2)} />
                  <ValueMetric label="Trend" value={trendDirectionLabel(trendMetrics.pc_slope)} />
                  <ValueMetric label="Stability Near Peak" value={formatPercent(trendMetrics.pc_stability, 0)} />
                  <ValueMetric label="Window" value={`${formatFixed(trendMetrics.window_minutes, 0)}m / ${formatFixed(trendMetrics.cadence_seconds, 0)}s`} />
                </div>
                <div style={{ color: 'var(--text-muted)', fontSize: 10, marginTop: 8 }}>
                  {trendMetrics.gate_reason}
                </div>
              </div>
            )}

            {/* Maneuver plan */}
            {maneuverPlan && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em', marginBottom: 8 }}>
                  MANEUVER PLAN
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <ValueMetric label="Direction" value={maneuverPlan.direction ?? '-'} />
                  <ValueMetric label="Delta-V" value={maneuverDeltaV != null ? `${formatFixed(maneuverDeltaV, 3)} m/s` : '-'} color="var(--red)" />
                  <ValueMetric label="Burn Time" value={formatUtcDateTime(maneuverPlan.burn_time_utc)} />
                  <ValueMetric label="Early/Late" value={maneuverEarlyLateRatio != null ? `${formatFixed(maneuverEarlyLateRatio, 2)}x` : '-'} />
                  {timingComparison && (
                    <ValueMetric
                      label="Late Baseline dV"
                      value={`${timingComparison.lateDeltaV.toFixed(3)} m/s`}
                    />
                  )}
                  {timingComparison && (
                    <ValueMetric
                      label="Timing Savings"
                      value={`${timingComparison.savingsDeltaV.toFixed(3)} m/s (${timingComparison.savingsPct.toFixed(1)}%)`}
                      color="var(--green)"
                    />
                  )}
                </div>
                <div style={{ color: 'var(--text-muted)', fontSize: 10, marginTop: 8 }}>
                  {maneuverPlan.notes}
                </div>
                {timingComparison && (
                  <div style={{ color: 'var(--text-muted)', fontSize: 10, marginTop: 6 }}>
                    Compared against a late baseline burn derived from planner timing ratio.
                  </div>
                )}
              </div>
            )}

            {/* Confidence */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em' }}>CONFIDENCE</span>
                <span style={{ color: 'var(--accent-primary)', fontSize: 11, fontWeight: 600 }}>
                  {Math.round(confidence * 100)}%
                </span>
              </div>
              <div className="confidence-bar-track">
                <div
                  className="confidence-bar-fill"
                  style={{ width: `${confidence * 100}%` }}
                />
              </div>
            </div>

            {/* Earth Impact Score */}
            {earthImpact && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em', marginBottom: 6 }}>
                  EARTH IMPACT SCORE
                </div>
	                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: '50%',
                    background: earthImpactBackground,
                    border: `2px solid ${earthImpactColor}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 11, fontWeight: 700,
                    color: earthImpactColor,
                  }}>
	                    {formatPercent(earthImpact.impact_score, 0)}
	                  </div>
	                  <div>
                    <div style={{ color: 'var(--text-primary)', fontSize: 11, fontWeight: 600 }}>
                      {earthImpactScore > 0.7 ? 'HIGH IMPACT' : earthImpactScore > 0.4 ? 'MODERATE IMPACT' : 'LOW IMPACT'}
                    </div>
	                    {earthImpact.nearest_zone && (
	                      <div style={{ color: 'var(--text-muted)', fontSize: 10 }}>
	                        Near {earthImpact.nearest_zone} ({earthImpact.zone_category?.replace(/_/g, ' ')})
	                        {earthImpact.zone_distance_km != null && ` — ${formatFixed(earthImpact.zone_distance_km, 0)} km`}
	                      </div>
	                    )}
	                    <div style={{ color: 'var(--text-muted)', fontSize: 9 }}>
	                      {formatFixed(earthImpact.ground_lat, 2)}°, {formatFixed(earthImpact.ground_lon, 2)}° · {earthImpact.method}
	                    </div>
                    <div style={{ color: 'var(--text-muted)', fontSize: 9 }}>
                      This score weights ground-impact context, not orbital collision probability.
                    </div>
                  </div>
                </div>
	                {earthImpact.components && (
	                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6 }}>
	                    <ValueMetric label="Infra" value={formatPercent(earthImpact.components.infra, 0)} />
	                    <ValueMetric label="Population" value={formatPercent(earthImpact.components.population, 0)} />
	                    <ValueMetric label="Orbital" value={formatPercent(earthImpact.components.orbital, 0)} />
	                  </div>
	                )}
	              </div>
            )}

            {/* Decision reason */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em', marginBottom: 6 }}>
                WHY THIS DECISION
              </div>
              <div style={{ color: 'var(--text-primary)', fontSize: 11, lineHeight: 1.6 }}>
                {whyText}
              </div>
              {showTechnicalRationale && (
                <div style={{ marginTop: 8, color: 'var(--text-muted)', fontSize: 10, lineHeight: 1.5 }}>
                  AI note: {decisionRationaleShort}
                </div>
              )}
              <div style={{ marginTop: 6, color: 'var(--text-muted)', fontSize: 10 }}>
                Decision code: {(phase3Decision?.decision_reason_code ?? trendMetrics?.gate_reason_code ?? 'N/A').toString()}
              </div>
            </div>

            {/* Recommended actions */}
	            {recommendedActions.length > 0 && (
	              <div style={{ marginBottom: 16 }}>
                <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em', marginBottom: 6 }}>
                  ACTIONS
                </div>
	                {recommendedActions.map((action) => (
                  <div key={action} style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '5px 8px', marginBottom: 4,
                    background: 'var(--bg-soft-accent)',
                    borderRadius: 8,
                    border: '1px solid var(--border-subtle)',
                  }}>
                    <span style={{ color: 'var(--accent-secondary)', fontSize: 10 }}>▶</span>
                    <span style={{ color: 'var(--text-primary)', fontSize: 11 }}>{friendlyActionLabel(action)}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Value signal */}
            {value && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em', marginBottom: 8 }}>
                  VALUE SIGNAL
                </div>
	                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
	                  <ValueMetric label="ROI Ratio" value={`${roiRatio.toFixed(1)}x`} color="var(--green)" />
	                  <ValueMetric label="Loss Avoided" value={`$${formatFixed(((asFiniteNumber(value.estimated_loss_avoided_usd) ?? 0) / 1000), 0)}K`} />
	                  <ValueMetric
	                    label="Cost"
	                    value={`$${formatFixed((value as unknown as { intervention_cost_usd?: number }).intervention_cost_usd ?? (value as unknown as { estimated_cost_usd?: number }).estimated_cost_usd ?? 0, 0)}`}
	                  />
	                  <ValueMetric label="Confidence" value={`${Math.round((value.confidence ?? 0) * 100)}%`} />
	                  {adjustedLoss != null && (
	                    <ValueMetric label="Adj. Loss" value={`$${formatFixed((asFiniteNumber(adjustedLoss) ?? 0) / 1000, 0)}K`} color="var(--yellow)" />
	                  )}
	                </div>
	              </div>
            )}

            {/* Payment */}
            {payment && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em', marginBottom: 8 }}>
                  {spendSectionTitle}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{
                    padding: '3px 10px',
                    borderRadius: 999,
                    fontSize: 11,
                    background: paymentStatusBg,
                    border: `1px solid ${paymentStatusColor}`,
                    color: paymentStatusColor,
                  }}>
                    {payment.status.toUpperCase()}
                  </span>
	                  <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
	                    ${formatFixed(payment.amount_usd, 2)} {String(payment.currency).toUpperCase()}
	                  </span>
	                </div>
                {paymentId && (
                  <div style={{ color: 'var(--text-muted)', fontSize: 10, marginTop: 6 }}>
                    ID: {paymentId}
                  </div>
                )}
                {checkoutUrl && (
                  <>
                    <div style={{ color: 'var(--text-muted)', fontSize: 11, lineHeight: 1.45, marginTop: 8 }}>
                      Continue to secure checkout to complete this contingency coverage step.
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'center', marginTop: 10 }}>
                      <a
                        href={checkoutUrl}
                        target="_blank"
                        rel="noreferrer"
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          minWidth: 260,
                          padding: '12px 22px',
                          borderRadius: 999,
                          background: 'var(--accent-primary)',
                          color: '#ffffff',
                          fontSize: 13,
                          fontWeight: 700,
                          letterSpacing: '0.04em',
                          textDecoration: 'none',
                        }}
                      >
                        Open Secure Checkout
                      </a>
                    </div>
                  </>
                )}
              </div>
            )}

            {narration && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em', marginBottom: 6 }}>
                  RUN NARRATION
                </div>
                <div style={{ color: 'var(--text-muted)', fontSize: 11, lineHeight: 1.5 }}>
                  {narration}
                </div>
              </div>
            )}

            {/* Voice */}
            {showVoice && voice && (
              <div>
                <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em', marginBottom: 6 }}>
                  VOICE BRIEFING
                </div>
                {voice.audio_url && !voiceHasError && (
                  <audio
                    controls
                    src={voice.audio_url}
                    style={{ width: '100%', height: 32, marginBottom: 8 }}
                  />
                )}
                {!voiceHasError ? (
                  <div style={{ color: 'var(--text-muted)', fontSize: 11, fontStyle: 'italic', lineHeight: 1.5 }}>
                    "{voice.script_text}"
                  </div>
                ) : (
                  <div style={{ color: 'var(--text-muted)', fontSize: 11, lineHeight: 1.5 }}>
                    Voice generation unavailable for this run.
                  </div>
                )}
                <div style={{ color: 'var(--text-muted)', fontSize: 10, marginTop: 4 }}>
                  {voice.provider} — {voice.status}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function ValueMetric({
  label,
  value,
  color = 'var(--text-primary)',
  wide = false,
}: {
  label: string
  value: string
  color?: string
  wide?: boolean
}) {
  return (
    <div style={{
      padding: '6px 10px',
      background: 'var(--bg-muted)',
      borderRadius: 8,
      border: '1px solid var(--border-subtle)',
      gridColumn: wide ? '1 / -1' : undefined,
    }}>
      <div style={{ color: 'var(--text-muted)', fontSize: 9, letterSpacing: '0.08em', marginBottom: 3 }}>{label.toUpperCase()}</div>
      <div style={{ color, fontSize: 13, fontWeight: 700, lineHeight: 1.35 }}>{value}</div>
    </div>
  )
}
