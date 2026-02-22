import type { ConjunctionEvent } from '../types'

interface Props {
  event: ConjunctionEvent
  selected: boolean
  onClick: () => void
}

function formatProbability(pc: number): string {
  if (pc <= 0) return '< 1e-10'
  if (pc < 1e-6) return pc.toExponential(1)
  if (pc < 1e-3) return pc.toExponential(2)
  return `${(pc * 100).toFixed(2)}%`
}

function decisionHintLabel(mode: ConjunctionEvent['decision_mode_hint']): string {
  if (mode === 'DEFER') return 'Defer & Recheck'
  if (mode === 'MANEUVER') return 'Avoidance Burn'
  if (mode === 'IGNORE') return 'No Action'
  return ''
}

const TIER_COLOR: Record<string, string> = {
  CRITICAL: 'var(--red)',
  HIGH: 'var(--orange)',
  MEDIUM: 'var(--yellow)',
  LOW: 'var(--green)',
}

const TIER_SELECTED_BG: Record<string, string> = {
  CRITICAL: 'rgba(176, 64, 63, 0.2)',
  HIGH: 'rgba(168, 102, 34, 0.2)',
  MEDIUM: 'rgba(155, 120, 7, 0.2)',
  LOW: 'rgba(46, 138, 102, 0.2)',
}

const TIER_SELECTED_SHADOW: Record<string, string> = {
  CRITICAL: '0 10px 20px rgba(176, 64, 63, 0.22)',
  HIGH: '0 10px 20px rgba(168, 102, 34, 0.22)',
  MEDIUM: '0 10px 20px rgba(155, 120, 7, 0.22)',
  LOW: '0 10px 20px rgba(46, 138, 102, 0.2)',
}

export default function EventCard({ event, selected, onClick }: Props) {
  const tierColor = TIER_COLOR[event.risk_tier] ?? 'var(--accent-primary)'
  const selectedBg = TIER_SELECTED_BG[event.risk_tier] ?? 'var(--bg-soft-accent)'
  const selectedShadow = TIER_SELECTED_SHADOW[event.risk_tier] ?? '0 10px 20px rgba(17, 35, 57, 0.14)'
  const primaryLabel = event.primary_name?.trim() || `Object ${event.primary_norad_id}`
  const secondaryLabel = event.secondary_name?.trim() || `Object ${event.secondary_norad_id}`
  const distKm = (event.miss_distance_m / 1000).toFixed(1)
  const pcExp = formatProbability(event.pc_assumed)
  const decisionHint = event.decision_mode_hint ?? null
  const badgeClass = decisionHint
    ? `badge-${decisionHint}`
    : `badge-${event.risk_tier === 'CRITICAL' ? 'MANEUVER' : event.risk_tier === 'HIGH' ? 'INSURE' : event.risk_tier === 'MEDIUM' ? 'MONITOR' : 'IGNORE'}`
  const badgeText = decisionHint === 'MANEUVER' && typeof event.plan_delta_v_mps === 'number'
    ? `MANEUVER ${event.plan_delta_v_mps.toFixed(3)}m/s`
    : (decisionHint ?? event.risk_tier)
  const actionText = decisionHintLabel(decisionHint)

  return (
    <div
      onClick={onClick}
      style={{
        padding: '10px 14px',
        borderRadius: 10,
        border: selected
          ? `2px solid ${tierColor}`
          : '1px solid var(--border-subtle)',
        background: selected ? selectedBg : 'var(--bg-card)',
        cursor: 'pointer',
        transition: 'border-color 0.15s ease, background-color 0.15s ease, transform 0.15s ease',
        transform: selected ? 'scale(1.015)' : 'none',
        boxShadow: selected ? selectedShadow : 'none',
        marginBottom: 7,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ color: 'var(--text-strong)', fontWeight: 700, fontSize: 12 }}>
          {primaryLabel}
        </span>
        <span
          className={`badge ${badgeClass}`}
          style={{ fontSize: 9 }}
        >
          {badgeText}
        </span>
      </div>
      <div style={{ color: 'var(--text-muted)', fontSize: 11, marginBottom: 2 }}>
        vs {secondaryLabel}
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 6 }}>
        <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
          Dist: <span style={{ color: 'var(--text-primary)' }}>{distKm} km</span>
        </span>
        <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
          Pc: <span style={{ color: tierColor }}>{pcExp}</span>
        </span>
      </div>
      <div style={{ color: 'var(--text-muted)', fontSize: 10, marginTop: 4 }}>
        TCA: {event.tca_utc.replace('T', ' ').replace('Z', ' UTC')}
      </div>
      {actionText && (
        <div style={{ color: 'var(--text-primary)', fontSize: 10, marginTop: 2 }}>
          Action: {actionText}
        </div>
      )}
      {decisionHint === 'DEFER' && event.defer_until_utc && (
        <div style={{ color: 'var(--yellow)', fontSize: 10, marginTop: 2 }}>
          Defer until: {event.defer_until_utc.replace('T', ' ').replace('Z', ' UTC')}
        </div>
      )}
      {decisionHint === 'MANEUVER' && event.plan_burn_time_utc && (
        <div style={{ color: 'var(--red)', fontSize: 10, marginTop: 2 }}>
          Burn: {event.plan_burn_time_utc.replace('T', ' ').replace('Z', ' UTC')}
        </div>
      )}
    </div>
  )
}
