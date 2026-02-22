import { useEffect, useRef } from 'react'
import type { MissionLogEntry } from '../types'

interface Props {
  entries: MissionLogEntry[]
}

const LEVEL_COLOR: Record<string, string> = {
  info: 'var(--cyan)',
  success: 'var(--green)',
  warning: 'var(--yellow)',
  error: 'var(--red)',
}

const LEVEL_PREFIX: Record<string, string> = {
  info: '[INFO]',
  success: '[OK]',
  warning: '[WARN]',
  error: '[ERR]',
}

export default function MissionLog({ entries }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [entries.length])

  return (
    <div
      className="panel"
      style={{ display: 'flex', flexDirection: 'column', height: 180, flexShrink: 0 }}
    >
      <div className="panel-header">Mission Log</div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 12px', fontFamily: 'monospace', fontSize: 11 }}>
        {entries.length === 0 ? (
          <div style={{ color: 'var(--text-muted)' }}>Awaiting events...</div>
        ) : (
          entries.map((entry) => (
            <div key={entry.id} style={{ marginBottom: 4, lineHeight: 1.5 }}>
              <span style={{ color: 'var(--text-muted)' }}>{entry.timestamp} </span>
              <span style={{ color: LEVEL_COLOR[entry.level] ?? 'var(--cyan)' }}>
                {LEVEL_PREFIX[entry.level] ?? '[LOG]'}{' '}
              </span>
              <span style={{ color: 'var(--text-primary)' }}>{entry.message}</span>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
