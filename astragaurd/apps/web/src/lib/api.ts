import type {
  ArtifactsLatest,
  TopConjunctionsArtifact,
  CesiumSnapshot,
  RunAutonomyLoopResponse,
} from '../types'

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body?.detail?.error ?? body?.detail ?? detail
    } catch {
      // ignore parse error
    }
    throw new Error(`${res.status} ${detail}`)
  }
  return res.json() as Promise<T>
}

export function getArtifactsLatest(): Promise<ArtifactsLatest> {
  return fetchJSON<ArtifactsLatest>('/api/artifacts/latest')
}

export function getTopConjunctions(): Promise<TopConjunctionsArtifact> {
  return fetchJSON<TopConjunctionsArtifact>('/api/artifacts/top-conjunctions')
}

export function getCesiumSnapshot(): Promise<CesiumSnapshot> {
  return fetchJSON<CesiumSnapshot>('/api/artifacts/cesium-snapshot')
}

export function runAutonomyLoop(targetEventId: string | null): Promise<RunAutonomyLoopResponse> {
  return fetchJSON<RunAutonomyLoopResponse>('/api/run-autonomy-loop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      request_id: `REQ-${Date.now()}`,
      mode: 'dry_run',
      selection_strategy: 'top_risk',
      target_event_id: targetEventId ?? null,
      providers: {
        consultant: 'claude-3-7-sonnet',
        vision: 'gemini-2.0-flash',
        payments: 'stripe',
        value: 'paid_ai',
        voice: 'elevenlabs',
      },
      payment: { enabled: false, amount_usd: 25.0, currency: 'USD' },
      schema_version: '1.0.0',
    }),
  })
}
