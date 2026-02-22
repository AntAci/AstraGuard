import { useState, useEffect, useCallback } from 'react'
import type {
  ConjunctionEvent,
  CesiumSnapshot,
  RunAutonomyLoopResponse,
} from './types'
import {
  getArtifactsLatest,
  getTopConjunctions,
  getCesiumSnapshot,
  runAutonomyLoop,
  isDemoMode,
} from './lib/api'
import CesiumGlobe from './components/CesiumGlobe'
import EventList from './components/EventList'
import AutonomyPanel from './components/AutonomyPanel'

const UVICORN_CMD = 'uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000'

type RawConjunctionEvent = Partial<ConjunctionEvent> & {
  primary_id?: number
  secondary_id?: number
  risk_score?: number
  p_collision?: number
  decision_mode_hint?: string | null
  defer_until_utc?: string | null
  trend_pc_peak?: number | null
  trend_pc_slope?: number | null
  trend_pc_stability?: number | null
  plan_delta_v_mps?: number | null
  plan_burn_time_utc?: string | null
}

function toFiniteNumber(value: unknown, fallback: number): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function parseIdsFromEventId(eventId: string): { primaryId: number | null; secondaryId: number | null } {
  const match = /^EVT-(\d+)-(\d+)-/.exec(eventId)
  if (!match) return { primaryId: null, secondaryId: null }
  return {
    primaryId: Number(match[1]),
    secondaryId: Number(match[2]),
  }
}

function inferRiskTier(probability: number): string {
  if (probability >= 1e-3) return 'CRITICAL'
  if (probability >= 1e-4) return 'HIGH'
  if (probability >= 1e-5) return 'MEDIUM'
  return 'LOW'
}

function formatTcaShort(utc: string): string {
  const parsed = Date.parse(utc)
  if (!Number.isFinite(parsed)) return 'N/A'
  return new Date(parsed).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatTimeUntil(utc: string): string {
  const parsed = Date.parse(utc)
  if (!Number.isFinite(parsed)) return 'N/A'
  const deltaMinutes = Math.round((parsed - Date.now()) / 60000)
  if (deltaMinutes <= 0) return 'now'
  if (deltaMinutes < 60) return `in ${deltaMinutes}m`
  const hours = Math.floor(deltaMinutes / 60)
  const mins = deltaMinutes % 60
  return mins > 0 ? `in ${hours}h ${mins}m` : `in ${hours}h`
}

function normalizeConjunctionEvents(rawEvents: unknown[], snapshot: CesiumSnapshot): ConjunctionEvent[] {
  const nameByNorad = new Map<number, string>()
  for (const obj of snapshot.objects) {
    if (typeof obj.norad_id === 'number' && typeof obj.name === 'string' && obj.name.trim().length > 0) {
      nameByNorad.set(obj.norad_id, obj.name.trim())
    }
  }

  return rawEvents
    .map((value, index) => {
      const event = (value ?? {}) as RawConjunctionEvent
      const eventId = String(event.event_id ?? `EVT-UNKNOWN-${index}`)
      const parsed = parseIdsFromEventId(eventId)

      const primaryId = toFiniteNumber(
        event.primary_norad_id ?? event.primary_id ?? parsed.primaryId,
        -1
      )
      const secondaryId = toFiniteNumber(
        event.secondary_norad_id ?? event.secondary_id ?? parsed.secondaryId,
        -1
      )

      const primaryNameRaw = typeof event.primary_name === 'string' ? event.primary_name.trim() : ''
      const secondaryNameRaw = typeof event.secondary_name === 'string' ? event.secondary_name.trim() : ''
      const primaryName = primaryNameRaw || nameByNorad.get(primaryId) || `Object ${primaryId}`
      const secondaryName = secondaryNameRaw || nameByNorad.get(secondaryId) || `Object ${secondaryId}`

      const probability = toFiniteNumber(event.pc_assumed ?? event.risk_score ?? event.p_collision, 0)
      const riskTierRaw = typeof event.risk_tier === 'string' ? event.risk_tier.trim().toUpperCase() : ''
      const riskTier = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].includes(riskTierRaw)
        ? riskTierRaw
        : inferRiskTier(probability)

      return {
        event_id: eventId,
        primary_norad_id: primaryId,
        secondary_norad_id: secondaryId,
        primary_name: primaryName,
        secondary_name: secondaryName,
        tca_utc: String(event.tca_utc ?? ''),
        miss_distance_m: toFiniteNumber(event.miss_distance_m, 0),
        pc_assumed: probability,
        risk_tier: riskTier,
        tca_index_snapshot: toFiniteNumber(event.tca_index_snapshot, 0),
        decision_mode_hint: (typeof event.decision_mode_hint === 'string'
          ? event.decision_mode_hint.toUpperCase()
          : null) as ConjunctionEvent['decision_mode_hint'],
        defer_until_utc: typeof event.defer_until_utc === 'string' ? event.defer_until_utc : null,
        trend_pc_peak: event.trend_pc_peak ?? null,
        trend_pc_slope: event.trend_pc_slope ?? null,
        trend_pc_stability: event.trend_pc_stability ?? null,
        plan_delta_v_mps: event.plan_delta_v_mps ?? null,
        plan_burn_time_utc: typeof event.plan_burn_time_utc === 'string' ? event.plan_burn_time_utc : null,
      } satisfies ConjunctionEvent
    })
    .filter((event) => event.event_id.length > 0)
}

export default function MissionControl() {
  const [events, setEvents] = useState<ConjunctionEvent[]>([])
  const [snapshot, setSnapshot] = useState<CesiumSnapshot | null>(null)
  const [timeIndex, setTimeIndex] = useState(0)
  const [selectedEvent, setSelectedEvent] = useState<ConjunctionEvent | null>(null)
  const [autonomyResult, setAutonomyResult] = useState<RunAutonomyLoopResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loadingMessage, setLoadingMessage] = useState('Connecting to API...')
  const [error, setError] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [autonomyError, setAutonomyError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [showContinents, setShowContinents] = useState(true)

  // Initial data load
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        setLoadingMessage(isDemoMode ? 'Loading demo scenario...' : 'Connecting to API...')
        await getArtifactsLatest()
        if (cancelled) return

        setLoadingMessage(isDemoMode ? 'Preparing optimized demo data...' : 'Loading orbits and conjunctions...')
        const [conjData, snapData] = await Promise.all([
          getTopConjunctions(true),
          getCesiumSnapshot(),
        ])
        if (cancelled) return

        const rawEvents = Array.isArray((conjData as { events?: unknown[] }).events)
          ? (conjData as { events: unknown[] }).events
          : []
        setEvents(normalizeConjunctionEvents(rawEvents, snapData))
        setSnapshot(snapData)
        setIsLoading(false)
      } catch (err) {
        if (cancelled) return
        const msg = err instanceof Error ? err.message : String(err)
        if (msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('502') || msg.includes('404')) {
          setError('offline')
        } else if (msg.includes('ARTIFACTS') || msg.includes('404')) {
          setError('artifacts')
        } else {
          setError(msg)
        }
        setIsLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  const handleRunAutonomy = useCallback(async () => {
    setIsRunning(true)
    setAutonomyError(null)
    try {
      const result = await runAutonomyLoop(selectedEvent?.event_id ?? null)
      setAutonomyResult(result)

      // Auto-select the analyzed event
      const selectedId = result.result.selected_event_id
      const matchedEvent = events.find((e) => e.event_id === selectedId)
      if (matchedEvent) setSelectedEvent(matchedEvent)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      if (message.includes('CONSULTANT_UNAVAILABLE')) {
        setAutonomyError('Consultant unavailable. Set ANTHROPIC_API_KEY or GEMINI_API_KEY and retry.')
      } else if (message.includes('CONSULTANT_INVALID_OUTPUT')) {
        setAutonomyError('Consultant returned invalid structured output. Retry the run or switch model provider.')
      } else {
        setAutonomyError(message)
      }
    } finally {
      setIsRunning(false)
    }
  }, [selectedEvent, events])

  const handleCopyCmd = () => {
    navigator.clipboard.writeText(`cd astragaurd && ${UVICORN_CMD}`).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const maneuverCandidateCount = events.filter((event) => event.decision_mode_hint === 'MANEUVER').length
  const deferCandidateCount = events.filter((event) => event.decision_mode_hint === 'DEFER').length
  const closestMissMeters = events.reduce(
    (min, event) => Math.min(min, event.miss_distance_m),
    Number.POSITIVE_INFINITY
  )
  const closestMissText = Number.isFinite(closestMissMeters)
    ? `${(closestMissMeters / 1000).toFixed(2)} km`
    : 'N/A'
  const soonestEvent = events.reduce<ConjunctionEvent | null>((earliest, event) => {
    if (!earliest) return event
    return Date.parse(event.tca_utc) < Date.parse(earliest.tca_utc) ? event : earliest
  }, null)
  const soonestTcaText = soonestEvent ? `${formatTcaShort(soonestEvent.tca_utc)} (${formatTimeUntil(soonestEvent.tca_utc)})` : 'N/A'
  const highestRisk = events.reduce((max, event) => Math.max(max, event.pc_assumed), 0)
  const highestRiskText = highestRisk >= 1e-4
    ? `${(highestRisk * 100).toFixed(2)}%`
    : highestRisk > 0
      ? highestRisk.toExponential(2)
      : 'N/A'

  // ── Error states ────────────────────────────────────────────────────────────
  if (error === 'offline') {
    return (
      <div className="offline-banner">
        <div className="panel offline-card">
          <h2>API OFFLINE</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 8 }}>
            Start the FastAPI server from the <code>astragaurd/</code> directory:
          </p>
          <pre>{UVICORN_CMD}</pre>
          <button className="btn-copy" onClick={handleCopyCmd}>
            {copied ? 'Copied!' : 'Copy command'}
          </button>
        </div>
      </div>
    )
  }

  if (error === 'artifacts') {
    return (
      <div className="offline-banner">
        <div className="panel offline-card">
          <h2>ARTIFACTS MISSING</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>
            Run the screening pipeline first:
          </p>
          <pre>cd astragaurd{'\n'}python scripts/run_screening.py</pre>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="offline-banner">
        <div className="panel offline-card">
          <h2>ERROR</h2>
          <pre style={{ fontSize: 11 }}>{error}</pre>
        </div>
      </div>
    )
  }

  // ── Loading ─────────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="loading-overlay">
        <div className="spinner" style={{ width: 40, height: 40, borderWidth: 3 }} />
        <div style={{ color: 'var(--accent-primary)', fontSize: 13, letterSpacing: '0.08em', fontWeight: 600 }}>
          {loadingMessage}
        </div>
        <div className="loading-caption">ASTRAGAURD OPERATIONS CONSOLE</div>
      </div>
    )
  }

  // ── Main layout ─────────────────────────────────────────────────────────────
  return (
    <div className="app-layout">
      {/* Left panel: event list */}
      <div className="app-column-left" style={{ display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0 }}>
        {/* Title */}
        <div style={{
          padding: '14px 16px',
          border: 'var(--panel-border)',
          borderRadius: 12,
          background: 'var(--bg-card)',
          boxShadow: 'var(--shadow-soft)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <div style={{
              fontSize: 17,
              fontWeight: 700,
              color: 'var(--text-strong)',
              letterSpacing: '0.07em',
              fontFamily: 'var(--font-label)',
            }}>
              ASTRAGAURD
            </div>
            <span className={`badge ${isDemoMode ? 'badge-DEFER' : 'badge-IGNORE'}`}>
              {isDemoMode ? 'DEMO' : 'LIVE'}
            </span>
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.08em', marginTop: 2 }}>
            MANEUVER OPTIMIZATION CONSOLE
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: 10, marginTop: 5, lineHeight: 1.4 }}>
            Objective: minimize recurring conjunction response cost without weakening safety thresholds.
          </div>
        </div>
        <div className="panel" style={{ padding: '10px 12px' }}>
          <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em', marginBottom: 8 }}>
            QUICK METRICS
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <MetricTile label="Events" value={String(events.length)} />
            <MetricTile label="Maneuver" value={String(maneuverCandidateCount)} color="var(--red)" />
            <MetricTile label="Defer" value={String(deferCandidateCount)} color="var(--yellow)" />
            <MetricTile label="Closest Miss" value={closestMissText} />
            <MetricTile label="Soonest TCA" value={soonestTcaText} wide />
            <MetricTile label="Peak Risk" value={highestRiskText} wide color="var(--accent-primary)" />
          </div>
        </div>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 12px',
          border: 'var(--panel-border)',
          borderRadius: 12,
          background: 'var(--bg-card)',
          boxShadow: 'var(--shadow-soft)',
          fontSize: 11,
          color: 'var(--text-muted)',
        }}>
          <span style={{ letterSpacing: '0.08em' }}>CONTINENTS</span>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showContinents}
              onChange={(event) => setShowContinents(event.target.checked)}
              style={{ accentColor: 'var(--accent-primary)' }}
            />
            <span style={{ color: 'var(--accent-primary)', letterSpacing: '0.08em', fontWeight: 600 }}>
              {showContinents ? 'ON' : 'OFF'}
            </span>
          </label>
        </div>

        <div className="app-event-list-wrap" style={{ flex: 1, minHeight: 0 }}>
          <EventList
            events={events}
            selectedEvent={selectedEvent}
            onSelect={setSelectedEvent}
            timeIndex={timeIndex}
            totalTimesteps={snapshot?.times_utc.length ?? 0}
            onTimeChange={setTimeIndex}
          />
        </div>
      </div>

      {/* Center: Cesium globe */}
      <div
        className="app-globe-shell"
        style={{
          borderRadius: 12,
          overflow: 'hidden',
          border: 'var(--panel-border)',
          minHeight: 0,
          background: 'var(--bg-card)',
          boxShadow: 'var(--shadow-soft)',
        }}
      >
        <CesiumGlobe
          snapshot={snapshot}
          timeIndex={timeIndex}
          selectedEvent={selectedEvent}
          onTimeChange={setTimeIndex}
          showContinents={showContinents}
        />
      </div>

      {/* Right panel: autonomy */}
      <div className="app-column-right" style={{ minHeight: 0 }}>
        <AutonomyPanel
          result={autonomyResult}
          selectedEvent={selectedEvent}
          isRunning={isRunning}
          runError={autonomyError}
          onRun={handleRunAutonomy}
        />
      </div>
    </div>
  )
}

function MetricTile({
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
    <div
      style={{
        padding: '8px 10px',
        borderRadius: 8,
        background: 'var(--bg-muted)',
        border: '1px solid var(--border-subtle)',
        gridColumn: wide ? '1 / -1' : undefined,
      }}
    >
      <div style={{ color: 'var(--text-muted)', fontSize: 9, letterSpacing: '0.08em', marginBottom: 3 }}>
        {label.toUpperCase()}
      </div>
      <div style={{ color, fontSize: 12, fontWeight: 700, lineHeight: 1.35 }}>{value}</div>
    </div>
  )
}
