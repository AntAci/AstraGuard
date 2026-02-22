import type { RunAutonomyLoopResponse, ConjunctionEvent } from '../types'

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
  const voice = result?.result.voice

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
                  Selected: <span style={{ color: 'var(--cyan)' }}>{selectedEvent.primary_name}</span>
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
                <span style={{ color: 'var(--cyan)', fontSize: 11 }}>
                  {Math.round(decision.confidence * 100)}%
                </span>
              </div>
              <div className="confidence-bar-track">
                <div
                  className="confidence-bar-fill"
                  style={{ width: `${decision.confidence * 100}%` }}
                />
              </div>
            </div>

            {/* Rationale */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em', marginBottom: 6 }}>
                RATIONALE
              </div>
              <div style={{ color: 'var(--text-primary)', fontSize: 11, lineHeight: 1.6 }}>
                {decision.rationale}
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
                    background: 'rgba(0,200,255,0.05)',
                    borderRadius: 4,
                    border: '1px solid rgba(0,200,255,0.1)',
                  }}>
                    <span style={{ color: 'var(--cyan)', fontSize: 10 }}>▶</span>
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
                  <ValueMetric label="ROI Ratio" value={`${value.roi_ratio.toFixed(1)}x`} color="var(--green)" />
                  <ValueMetric label="Loss Avoided" value={`$${(value.estimated_loss_avoided_usd / 1000).toFixed(0)}K`} />
                  <ValueMetric label="Cost" value={`$${value.intervention_cost_usd.toFixed(0)}`} />
                  <ValueMetric label="Confidence" value={`${Math.round(value.confidence * 100)}%`} />
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
                    borderRadius: 4,
                    fontSize: 11,
                    background: payment.status === 'skipped'
                      ? 'rgba(255,204,0,0.1)'
                      : 'rgba(0,255,136,0.1)',
                    border: `1px solid ${payment.status === 'skipped' ? 'var(--yellow)' : 'var(--green)'}`,
                    color: payment.status === 'skipped' ? 'var(--yellow)' : 'var(--green)',
                  }}>
                    {payment.status.toUpperCase()}
                  </span>
                  <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                    ${payment.amount_usd.toFixed(2)} {payment.currency}
                  </span>
                </div>
              </div>
            )}

            {/* Voice */}
            {voice && (
              <div>
                <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em', marginBottom: 6 }}>
                  VOICE BRIEFING
                </div>
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
      background: 'rgba(0,0,0,0.3)',
      borderRadius: 4,
      border: '1px solid rgba(0,200,255,0.08)',
    }}>
      <div style={{ color: 'var(--text-muted)', fontSize: 9, letterSpacing: '0.08em', marginBottom: 3 }}>{label.toUpperCase()}</div>
      <div style={{ color, fontSize: 14, fontWeight: 700 }}>{value}</div>
    </div>
  )
}
