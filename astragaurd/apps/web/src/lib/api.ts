import type {
  ArtifactsLatest,
  TopConjunctionsArtifact,
  CesiumSnapshot,
  RunAutonomyLoopResponse,
} from '../types'
import {
  demoArtifactsLatest,
  demoTopConjunctions,
  demoSnapshot,
  demoManeuverPlans,
  createDemoAutonomyResponse,
} from './demoData'

const importMetaEnv = (import.meta as unknown as { env?: Record<string, string | undefined> }).env
export const isDemoMode = importMetaEnv?.VITE_DEMO_MODE === '1'

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

function cloneDemo<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function normalizeRunAutonomyResponse(payload: unknown): RunAutonomyLoopResponse {
  if (!payload || typeof payload !== 'object') {
    throw new Error('Invalid run-autonomy-loop response payload')
  }

  const candidate = payload as Record<string, unknown>
  const nested = candidate.result
  if (nested && typeof nested === 'object') {
    return candidate as unknown as RunAutonomyLoopResponse
  }

  const runId = typeof candidate.run_id === 'string' ? candidate.run_id : `RUN-${Date.now()}`
  const status = typeof candidate.status === 'string' ? candidate.status : 'completed'

  return {
    run_id: runId,
    status,
    result: candidate as unknown as RunAutonomyLoopResponse['result'],
  }
}

export function getArtifactsLatest(): Promise<ArtifactsLatest> {
  if (isDemoMode) {
    return Promise.resolve(cloneDemo(demoArtifactsLatest))
  }
  return fetchJSON<ArtifactsLatest>('/api/artifacts/latest')
}

export function getTopConjunctions(includePlans = false): Promise<TopConjunctionsArtifact> {
  if (isDemoMode) {
    return Promise.resolve(cloneDemo(demoTopConjunctions))
  }
  const suffix = includePlans ? '?include_plans=1' : ''
  return fetchJSON<TopConjunctionsArtifact>(`/api/artifacts/top-conjunctions${suffix}`)
}

export function getCesiumSnapshot(): Promise<CesiumSnapshot> {
  if (isDemoMode) {
    return Promise.resolve(cloneDemo(demoSnapshot))
  }
  return fetchJSON<CesiumSnapshot>('/api/artifacts/cesium-snapshot')
}

export function getManeuverPlans(): Promise<Record<string, unknown>> {
  if (isDemoMode) {
    return Promise.resolve(cloneDemo(demoManeuverPlans))
  }
  return fetchJSON<Record<string, unknown>>('/api/artifacts/maneuver-plans')
}

export function runAutonomyLoop(targetEventId: string | null): Promise<RunAutonomyLoopResponse> {
  if (isDemoMode) {
    return Promise.resolve(cloneDemo(createDemoAutonomyResponse(targetEventId)))
  }
  return fetchJSON<unknown>('/api/run-autonomy-loop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      request_id: `REQ-${Date.now()}`,
      mode: 'live',
      selection_strategy: 'top_risk',
      target_event_id: targetEventId ?? null,
      providers: {
        consultant: 'claude-3-7-sonnet',
        vision: 'gemini-2.5-flash',
        payments: 'stripe',
        value: 'paid_ai',
        voice: 'elevenlabs',
      },
      payment: { enabled: true, amount_usd: 0.0, currency: 'USD' },
      schema_version: '1.1.0',
    }),
  }).then((payload) => normalizeRunAutonomyResponse(payload))
}
