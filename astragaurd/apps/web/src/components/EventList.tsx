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

export default function EventList({
  events,
  selectedEvent,
  onSelect,
  timeIndex,
  totalTimesteps,
  onTimeChange,
}: Props) {
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
            <span style={{ color: 'var(--cyan)', fontSize: 11 }}>
              {timeIndex + 1} / {totalTimesteps}
            </span>
          </div>
          <input
            type="range"
            className="time-slider"
            min={0}
            max={totalTimesteps - 1}
            value={timeIndex}
            onChange={(e) => onTimeChange(Number(e.target.value))}
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
