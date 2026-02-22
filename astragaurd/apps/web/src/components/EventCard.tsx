import type { ConjunctionEvent } from '../types'

interface Props {
  event: ConjunctionEvent
  selected: boolean
  onClick: () => void
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
  const pcExp = event.pc_assumed > 0
    ? `1e${Math.round(Math.log10(event.pc_assumed))}`
    : '< 1e-10'

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
          className={`badge badge-${event.risk_tier === 'CRITICAL' ? 'MANEUVER' : event.risk_tier === 'HIGH' ? 'INSURE' : event.risk_tier === 'MEDIUM' ? 'MONITOR' : 'IGNORE'}`}
          style={{ fontSize: 9 }}
        >
          {event.risk_tier}
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
    </div>
  )
}
