import { useEffect, useRef } from 'react'
import type { ConjunctionEvent } from '../types'
import EventCard from './EventCard'

interface Props {
  events: ConjunctionEvent[]
  selectedEvent: ConjunctionEvent | null
  onSelect: (event: ConjunctionEvent) => void
  timeIndex: number
  totalTimesteps: number
  onTimeChange: (index: number) => void
}

const IDLE_BEFORE_AUTODRIFT_MS = 4000
const AUTODRIFT_STEP_INTERVAL_MS = 1800

export default function EventList({
  events,
  selectedEvent,
  onSelect,
  timeIndex,
  totalTimesteps,
  onTimeChange,
}: Props) {
  const lastInteractionRef = useRef<number>(performance.now())
  const isDraggingRef = useRef(false)
  const latestStateRef = useRef({
    timeIndex,
    totalTimesteps,
    onTimeChange,
  })
  latestStateRef.current = { timeIndex, totalTimesteps, onTimeChange }

  const markInteraction = () => {
    lastInteractionRef.current = performance.now()
  }

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    let prefersReducedMotion = media.matches

    const onReducedMotionChange = (event: MediaQueryListEvent) => {
      prefersReducedMotion = event.matches
      markInteraction()
    }
    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', onReducedMotionChange)
    } else {
      media.addListener(onReducedMotionChange)
    }

    const onUserActivity = () => markInteraction()
    const onDragEnd = () => {
      isDraggingRef.current = false
      markInteraction()
    }
    const onVisibilityChange = () => {
      if (document.visibilityState !== 'visible') {
        isDraggingRef.current = false
      }
      markInteraction()
    }

    window.addEventListener('wheel', onUserActivity, { passive: true })
    window.addEventListener('pointerdown', onUserActivity, { passive: true })
    window.addEventListener('touchstart', onUserActivity, { passive: true })
    window.addEventListener('keydown', onUserActivity)
    window.addEventListener('pointerup', onDragEnd, { passive: true })
    window.addEventListener('touchend', onDragEnd, { passive: true })
    window.addEventListener('blur', onDragEnd)
    document.addEventListener('visibilitychange', onVisibilityChange)

    let rafId = 0
    let lastFrameTs = performance.now()
    let driftElapsedMs = 0

    const tick = (now: number) => {
      const deltaMs = now - lastFrameTs
      lastFrameTs = now

      const { timeIndex: idx, totalTimesteps: total, onTimeChange: changeTime } = latestStateRef.current
      const isIdle = now - lastInteractionRef.current >= IDLE_BEFORE_AUTODRIFT_MS
      const canAutoDrift = !prefersReducedMotion && !isDraggingRef.current && total > 1 && isIdle

      if (canAutoDrift) {
        driftElapsedMs += deltaMs
        if (driftElapsedMs >= AUTODRIFT_STEP_INTERVAL_MS) {
          driftElapsedMs = 0
          changeTime(idx >= total - 1 ? 0 : idx + 1)
        }
      } else {
        driftElapsedMs = 0
      }

      rafId = window.requestAnimationFrame(tick)
    }

    rafId = window.requestAnimationFrame(tick)

    return () => {
      window.cancelAnimationFrame(rafId)
      if (typeof media.removeEventListener === 'function') {
        media.removeEventListener('change', onReducedMotionChange)
      } else {
        media.removeListener(onReducedMotionChange)
      }
      window.removeEventListener('wheel', onUserActivity)
      window.removeEventListener('pointerdown', onUserActivity)
      window.removeEventListener('touchstart', onUserActivity)
      window.removeEventListener('keydown', onUserActivity)
      window.removeEventListener('pointerup', onDragEnd)
      window.removeEventListener('touchend', onDragEnd)
      window.removeEventListener('blur', onDragEnd)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [])

  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div className="panel-header">
        Conjunction Events
        <span style={{ float: 'right', color: 'var(--text-muted)', fontWeight: 400 }}>
          {events.length} events
        </span>
      </div>

      {/* Time slider */}
      {totalTimesteps > 0 && (
        <div style={{ padding: '10px 14px', borderBottom: 'var(--panel-border)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ color: 'var(--text-muted)', fontSize: 11, letterSpacing: '0.05em' }}>TIME STEP</span>
            <span style={{ color: 'var(--accent-primary)', fontSize: 11, fontWeight: 600 }}>
              {timeIndex + 1} / {totalTimesteps}
            </span>
          </div>
          <input
            type="range"
            className="time-slider"
            min={0}
            max={totalTimesteps - 1}
            value={timeIndex}
            onChange={(e) => {
              markInteraction()
              onTimeChange(Number(e.target.value))
            }}
            onPointerDown={() => {
              isDraggingRef.current = true
              markInteraction()
            }}
            onPointerUp={() => {
              isDraggingRef.current = false
              markInteraction()
            }}
            onPointerCancel={() => {
              isDraggingRef.current = false
              markInteraction()
            }}
            onFocus={markInteraction}
            onKeyDown={markInteraction}
          />
        </div>
      )}

      {/* Event list */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '10px 10px' }}>
        {events.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '20px 0', textAlign: 'center' }}>
            No events loaded
          </div>
        ) : (
          events.map((ev) => (
            <EventCard
              key={ev.event_id}
              event={ev}
              selected={selectedEvent?.event_id === ev.event_id}
              onClick={() => onSelect(ev)}
            />
          ))
        )}
      </div>
    </div>
  )
}
