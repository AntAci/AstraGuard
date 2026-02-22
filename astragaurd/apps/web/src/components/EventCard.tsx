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

export default function EventCard({ event, selected, onClick }: Props) {
  const tierColor = TIER_COLOR[event.risk_tier] ?? 'var(--cyan)'
  const distKm = (event.miss_distance_m / 1000).toFixed(1)
  const pcExp = event.pc_assumed > 0
    ? `1e${Math.round(Math.log10(event.pc_assumed))}`
    : '< 1e-10'

  return (
    <div
      onClick={onClick}
      style={{
        padding: '10px 14px',
        borderRadius: 6,
        border: selected
          ? `1px solid ${tierColor}`
          : '1px solid rgba(0,200,255,0.1)',
        background: selected ? 'rgba(0,200,255,0.07)' : 'transparent',
        cursor: 'pointer',
        transition: 'all 0.15s',
        marginBottom: 6,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ color: 'var(--text-primary)', fontWeight: 700, fontSize: 12 }}>
          {event.primary_name}
        </span>
        <span
          className={`badge badge-${event.risk_tier === 'CRITICAL' ? 'MANEUVER' : event.risk_tier === 'HIGH' ? 'INSURE' : event.risk_tier === 'MEDIUM' ? 'MONITOR' : 'IGNORE'}`}
          style={{ fontSize: 10 }}
        >
          {event.risk_tier}
        </span>
      </div>
      <div style={{ color: 'var(--text-muted)', fontSize: 11, marginBottom: 2 }}>
        vs {event.secondary_name}
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
