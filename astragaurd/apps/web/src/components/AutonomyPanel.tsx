import type { RunAutonomyLoopResponse, ConjunctionEvent, EarthImpact } from '../types'

interface Props {
  result: RunAutonomyLoopResponse | null
  selectedEvent: ConjunctionEvent | null
  isRunning: boolean
  onRun: () => void
}

export default function AutonomyPanel({ result, selectedEvent, isRunning, onRun }: Props) {
  const decision = result?.result.consultant_decision
  const value = result?.result.value_signal
  const payment = result?.result.payment_result
  const phase3Decision = result?.result.decision as
    | { llm_provider?: string; expected_loss_usd?: number; rationale?: string[]; confidence?: number }
    | undefined
  const phase3Payment = result?.result.payment as
    | { id?: string | null; checkout_url?: string | null; status?: string; mode?: string }
    | undefined
  const voice = result?.result.voice
  const earthImpact = result?.result.earth_impact as EarthImpact | undefined
  const adjustedLoss = result?.result.expected_loss_adjusted_usd
  const narration = result?.result.narration_text
  const decisionRationale = Array.isArray(decision?.rationale)
    ? decision.rationale.join(' ')
    : (decision?.rationale ?? '')
  const roiRatio = result?.result.roi ?? value?.roi_ratio ?? 0
  const isHighEarthImpact = (earthImpact?.impact_score ?? 0) > 0.5
  const earthImpactColor = isHighEarthImpact ? 'var(--red)' : 'var(--green)'
  const earthImpactBackground = isHighEarthImpact ? 'rgba(176, 64, 63, 0.14)' : 'rgba(46, 138, 102, 0.14)'

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
            `Run Autonomy Loop${selectedEvent ? ` — ${selectedEvent.event_id}` : ''}`
          )}
        </button>

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
                <span className={`badge badge-${decision.decision}`}>{decision.decision}</span>
                <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                  {new Date(decision.generated_at_utc).toLocaleTimeString()}
                </span>
              </div>
            </div>

            {/* Confidence */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em' }}>CONFIDENCE</span>
                <span style={{ color: 'var(--accent-primary)', fontSize: 11, fontWeight: 600 }}>
                  {Math.round((phase3Decision?.confidence ?? decision.confidence) * 100)}%
                </span>
              </div>
              <div className="confidence-bar-track">
                <div
                  className="confidence-bar-fill"
                  style={{ width: `${(phase3Decision?.confidence ?? decision.confidence) * 100}%` }}
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
                    {Math.round(earthImpact.impact_score * 100)}%
                  </div>
                  <div>
                    <div style={{ color: 'var(--text-primary)', fontSize: 11, fontWeight: 600 }}>
                      {earthImpact.impact_score > 0.7 ? 'HIGH RISK' : earthImpact.impact_score > 0.4 ? 'MODERATE' : 'LOW RISK'}
                    </div>
                    {earthImpact.nearest_zone && (
                      <div style={{ color: 'var(--text-muted)', fontSize: 10 }}>
                        Near {earthImpact.nearest_zone} ({earthImpact.zone_category?.replace(/_/g, ' ')})
                        {earthImpact.zone_distance_km != null && ` — ${earthImpact.zone_distance_km.toFixed(0)} km`}
                      </div>
                    )}
                    <div style={{ color: 'var(--text-muted)', fontSize: 9 }}>
                      {earthImpact.ground_lat.toFixed(2)}°, {earthImpact.ground_lon.toFixed(2)}° · {earthImpact.method}
                    </div>
                  </div>
                </div>
                {earthImpact.components && (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6 }}>
                    <ValueMetric label="Infra" value={`${(earthImpact.components.infra * 100).toFixed(0)}%`} />
                    <ValueMetric label="Population" value={`${(earthImpact.components.population * 100).toFixed(0)}%`} />
                    <ValueMetric label="Orbital" value={`${(earthImpact.components.orbital * 100).toFixed(0)}%`} />
                  </div>
                )}
              </div>
            )}

            {/* Rationale */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em', marginBottom: 6 }}>
                RATIONALE
              </div>
              <div style={{ color: 'var(--text-primary)', fontSize: 11, lineHeight: 1.6 }}>
                {decisionRationale}
              </div>
            </div>

            {/* Recommended actions */}
            {decision.recommended_actions.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em', marginBottom: 6 }}>
                  ACTIONS
                </div>
                {decision.recommended_actions.map((action) => (
                  <div key={action} style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '5px 8px', marginBottom: 4,
                    background: 'var(--bg-soft-accent)',
                    borderRadius: 8,
                    border: '1px solid var(--border-subtle)',
                  }}>
                    <span style={{ color: 'var(--accent-secondary)', fontSize: 10 }}>▶</span>
                    <span style={{ color: 'var(--text-primary)', fontSize: 11 }}>{action}</span>
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
                  <ValueMetric label="Loss Avoided" value={`$${(((value.estimated_loss_avoided_usd ?? 0) as number) / 1000).toFixed(0)}K`} />
                  <ValueMetric
                    label="Cost"
                    value={`$${((value as unknown as { intervention_cost_usd?: number }).intervention_cost_usd ?? (value as unknown as { estimated_cost_usd?: number }).estimated_cost_usd ?? 0).toFixed(0)}`}
                  />
                  <ValueMetric label="Confidence" value={`${Math.round((value.confidence ?? 0) * 100)}%`} />
                  {adjustedLoss != null && (
                    <ValueMetric label="Adj. Loss" value={`$${(adjustedLoss / 1000).toFixed(0)}K`} color="var(--yellow)" />
                  )}
                </div>
              </div>
            )}

            {/* Payment */}
            {payment && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em', marginBottom: 8 }}>
                  PAYMENT
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{
                    padding: '3px 10px',
                    borderRadius: 999,
                    fontSize: 11,
                    background: payment.status === 'skipped'
                      ? 'rgba(155, 120, 7, 0.1)'
                      : 'rgba(46, 138, 102, 0.1)',
                    border: `1px solid ${payment.status === 'skipped' ? 'var(--yellow)' : 'var(--green)'}`,
                    color: payment.status === 'skipped' ? 'var(--yellow)' : 'var(--green)',
                  }}>
                    {payment.status.toUpperCase()}
                  </span>
                  <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                    ${payment.amount_usd.toFixed(2)} {payment.currency}
                  </span>
                </div>
                {(phase3Payment?.id ?? payment.transaction_id ?? payment.payment_intent_id) && (
                  <div style={{ color: 'var(--text-muted)', fontSize: 10, marginTop: 6 }}>
                    ID: {phase3Payment?.id ?? payment.transaction_id ?? payment.payment_intent_id}
                  </div>
                )}
                {phase3Payment?.checkout_url && (
                  <>
                    <div style={{ color: 'var(--text-muted)', fontSize: 11, lineHeight: 1.45, marginTop: 8 }}>
                      Continue to secure checkout to complete this payment step.
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'center', marginTop: 10 }}>
                      <a
                        href={phase3Payment.checkout_url}
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
            {voice && (
              <div>
                <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em', marginBottom: 6 }}>
                  VOICE BRIEFING
                </div>
                {voice.audio_url && (
                  <audio
                    controls
                    src={voice.audio_url}
                    style={{ width: '100%', height: 32, marginBottom: 8 }}
                  />
                )}
                <div style={{ color: 'var(--text-muted)', fontSize: 11, fontStyle: 'italic', lineHeight: 1.5 }}>
                  "{voice.script_text}"
                </div>
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

function ValueMetric({ label, value, color = 'var(--text-primary)' }: { label: string; value: string; color?: string }) {
  return (
    <div style={{
      padding: '6px 10px',
      background: 'var(--bg-muted)',
      borderRadius: 8,
      border: '1px solid var(--border-subtle)',
    }}>
      <div style={{ color: 'var(--text-muted)', fontSize: 9, letterSpacing: '0.08em', marginBottom: 3 }}>{label.toUpperCase()}</div>
      <div style={{ color, fontSize: 14, fontWeight: 700 }}>{value}</div>
    </div>
  )
}
