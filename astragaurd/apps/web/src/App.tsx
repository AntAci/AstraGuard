import { useState, useEffect, useCallback } from 'react'
import type {
  ConjunctionEvent,
  CesiumSnapshot,
  RunAutonomyLoopResponse,
  MissionLogEntry,
  LogLevel,
} from './types'
import {
  getArtifactsLatest,
  getTopConjunctions,
  getCesiumSnapshot,
  runAutonomyLoop,
} from './lib/api'
import CesiumGlobe from './components/CesiumGlobe'
import EventList from './components/EventList'
import AutonomyPanel from './components/AutonomyPanel'
import MissionLog from './components/MissionLog'

const UVICORN_CMD = 'uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000'

function makeLogEntry(level: LogLevel, message: string): MissionLogEntry {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    timestamp: new Date().toISOString().replace('T', ' ').slice(0, 19),
    level,
    message,
  }
}

export default function App() {
  const [events, setEvents] = useState<ConjunctionEvent[]>([])
  const [snapshot, setSnapshot] = useState<CesiumSnapshot | null>(null)
  const [timeIndex, setTimeIndex] = useState(0)
  const [selectedEvent, setSelectedEvent] = useState<ConjunctionEvent | null>(null)
  const [autonomyResult, setAutonomyResult] = useState<RunAutonomyLoopResponse | null>(null)
  const [missionLog, setMissionLog] = useState<MissionLogEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [loadingMessage, setLoadingMessage] = useState('Connecting to API...')
  const [error, setError] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [copied, setCopied] = useState(false)
  const [showContinents, setShowContinents] = useState(true)

  const log = useCallback((level: LogLevel, message: string) => {
    setMissionLog((prev) => [...prev, makeLogEntry(level, message)])
  }, [])

  // Initial data load
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        setLoadingMessage('Connecting to API...')
        await getArtifactsLatest()
        if (cancelled) return
        log('success', 'Connected to AstraGuard API')

        setLoadingMessage('Loading orbits and conjunctions...')
        const [conjData, snapData] = await Promise.all([
          getTopConjunctions(),
          getCesiumSnapshot(),
        ])
        if (cancelled) return

        setEvents(conjData.events)
        setSnapshot(snapData)
        log(
          'info',
          `Loaded ${conjData.events.length} events, ${snapData.objects.length} objects, ${snapData.times_utc.length} timesteps`
        )
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
  }, [log])

  const handleRunAutonomy = useCallback(async () => {
    setIsRunning(true)
    log('info', `Autonomy loop initiated${selectedEvent ? ` for ${selectedEvent.event_id}` : ' (top-risk)'}...`)
    try {
      const result = await runAutonomyLoop(selectedEvent?.event_id ?? null)
      setAutonomyResult(result)

      const d = result.result.consultant_decision
      const v = result.result.value_signal
      const p = result.result.payment_result
      log(
        'success',
        `Decision: ${d.decision} | Confidence: ${Math.round(d.confidence * 100)}% | ROI: ${v.roi_ratio.toFixed(1)}x | Payment: ${p.status}`
      )

      // Auto-select the analyzed event
      const selectedId = result.result.selected_event_id
      const matchedEvent = events.find((e) => e.event_id === selectedId)
      if (matchedEvent) setSelectedEvent(matchedEvent)
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      log('error', `Autonomy loop failed: ${msg}`)
    } finally {
      setIsRunning(false)
    }
  }, [selectedEvent, events, log])

  const handleCopyCmd = () => {
    navigator.clipboard.writeText(`cd astragaurd && ${UVICORN_CMD}`).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

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
      <div style={{
        position: 'fixed', inset: 0, background: '#000810',
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', gap: 16, zIndex: 100,
      }}>
        <div style={{
          width: 40, height: 40, borderRadius: '50%',
          border: '3px solid rgba(0,200,255,0.2)',
          borderTopColor: '#00c8ff',
          animation: 'spin 0.8s linear infinite',
        }} />
        <div style={{ color: '#00c8ff', fontSize: 13, letterSpacing: '0.1em' }}>
          {loadingMessage}
        </div>
        <div style={{ color: 'rgba(224,244,255,0.5)', fontSize: 11, marginTop: 4 }}>
          ASTRAGAURD MISSION CONTROL
        </div>
      </div>
    )
  }

  // ── Main layout ─────────────────────────────────────────────────────────────
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '320px 1fr 340px',
      gridTemplateRows: '1fr',
      height: '100vh',
      gap: 8,
      padding: 8,
      background: 'var(--bg-deep)',
    }}>
      {/* Left panel: event list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minHeight: 0 }}>
        {/* Title */}
        <div style={{
          padding: '10px 16px',
          borderBottom: '1px solid rgba(0,200,255,0.1)',
        }}>
          <div style={{
            fontSize: 16,
            fontWeight: 700,
            color: 'var(--cyan)',
            textShadow: '0 0 12px var(--cyan-glow)',
            letterSpacing: '0.15em',
          }}>
            ASTRAGAURD
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: 10, letterSpacing: '0.1em' }}>
            MISSION CONTROL
          </div>
        </div>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 12px',
          borderBottom: '1px solid rgba(0,200,255,0.08)',
          fontSize: 11,
          color: 'var(--text-muted)',
        }}>
          <span style={{ letterSpacing: '0.08em' }}>CONTINENTS</span>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showContinents}
              onChange={(event) => setShowContinents(event.target.checked)}
            />
            <span style={{ color: 'var(--cyan)', letterSpacing: '0.08em' }}>
              {showContinents ? 'ON' : 'OFF'}
            </span>
          </label>
        </div>

        <div style={{ flex: 1, minHeight: 0 }}>
          <EventList
            events={events}
            selectedEvent={selectedEvent}
            onSelect={setSelectedEvent}
            timeIndex={timeIndex}
            totalTimesteps={snapshot?.times_utc.length ?? 0}
            onTimeChange={setTimeIndex}
          />
        </div>

        <MissionLog entries={missionLog} />
      </div>

      {/* Center: Cesium globe */}
      <div style={{ borderRadius: 8, overflow: 'hidden', border: '1px solid rgba(0,200,255,0.1)', minHeight: 0 }}>
        <CesiumGlobe
          snapshot={snapshot}
          timeIndex={timeIndex}
          selectedEvent={selectedEvent}
          onTimeChange={setTimeIndex}
          showContinents={showContinents}
        />
      </div>

      {/* Right panel: autonomy */}
      <AutonomyPanel
        result={autonomyResult}
        selectedEvent={selectedEvent}
        isRunning={isRunning}
        onRun={handleRunAutonomy}
      />
    </div>
  )
}
