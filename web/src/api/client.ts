// API client + types for the Constellation backend.

export interface ModelInfo {
  id: string
  name: string
  contextTokens?: number
  supportsWebSearch: boolean
  supportsXSearch: boolean
  supportsReasoning: boolean
  supportsFunctionCalling: boolean
  pricing: { inputPerMtok?: number; outputPerMtok?: number }
}

export interface ModeInfo {
  id: string
  name: string
  description: string
  status: 'available' | 'coming_soon'
  flow: 'panel' | 'board' | 'workchart'
  defaults: { panelSize: number; maxPanelSize: number }
}

export interface EngagementCard {
  id: number
  mode: string
  title: string
  status: string
  created_at: string
  updated_at: string
  total_cost_usd: number
  total_tokens: number
  revision_count: number
}

export interface Persona {
  name: string
  title: string
  background: string
  focus_areas: string[]
  perspective: string
  discipline?: string
}

export interface Estimate {
  mode: string
  panelSize: number
  stages: { stage: string; model: string; calls: number; estCostUsd: number }[]
  totalCostUsd: number
}

export interface RunEvent {
  seq: number
  type: string
  data: Record<string, unknown>
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = res.statusText
    try {
      const body = await res.json()
      message = body?.error?.message ?? message
    } catch { /* keep statusText */ }
    throw new Error(message)
  }
  return res.json()
}

export const api = {
  models: () => fetch('/api/models').then((r) => json<ModelInfo[]>(r)),
  modes: () => fetch('/api/modes').then((r) => json<ModeInfo[]>(r)),
  estimate: (body: object) =>
    fetch('/api/estimate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then((r) => json<Estimate>(r)),
  createRun: (body: object) =>
    fetch('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then((r) => json<{ runId: string; engagementId: number; estimate: Estimate }>(r)),
  getRun: (runId: string) => fetch(`/api/runs/${runId}`).then((r) => json<{ status: string; events: RunEvent[] }>(r)),
  answer: (runId: string, answers: Record<string, string>) =>
    fetch(`/api/runs/${runId}/answers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers }),
    }).then((r) => json<{ ok: boolean }>(r)),
  cancelRun: (runId: string) => fetch(`/api/runs/${runId}/cancel`, { method: 'POST' }).then((r) => json<{ ok: boolean }>(r)),
  engagements: (params?: { mode?: string; q?: string }) => {
    const qs = new URLSearchParams()
    if (params?.mode) qs.set('mode', params.mode)
    if (params?.q) qs.set('q', params.q)
    return fetch(`/api/engagements?${qs}`).then((r) => json<EngagementCard[]>(r))
  },
  engagement: (id: number | string) =>
    fetch(`/api/engagements/${id}`).then((r) =>
      json<EngagementCard & { revisions: { rev: number; note: string; cost_usd: number; created_at: string }[]; latest?: { rev: number; input: object; result: Record<string, unknown>; usage: Record<string, unknown> } }>(r),
    ),
  revision: (id: number | string, rev: number | string) =>
    fetch(`/api/engagements/${id}/revisions/${rev}`).then((r) =>
      json<{ rev: number; input: object; result: Record<string, unknown> }>(r),
    ),
  renameEngagement: (id: number, title: string) =>
    fetch(`/api/engagements/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    }).then((r) => json<{ ok: boolean }>(r)),
  deleteEngagement: (id: number) =>
    fetch(`/api/engagements/${id}`, { method: 'DELETE' }).then((r) => json<{ ok: boolean }>(r)),
}
