// useRun: subscribes to a run's SSE stream and reduces events into UI state.
import { useEffect, useRef, useState } from 'react'
import type { Persona, RunEvent } from './client'

export interface ExpertState {
  index: number
  persona?: Persona
  status: 'pending' | 'thinking' | 'done'
  insight?: Record<string, unknown>
}

export interface MarketBrief {
  topic: string
  channel: string
  findings: string
  citations: { index: number; url: string; title: string }[]
}

export interface BoardTurn {
  round: number
  speaker: string
  statement: string
}

export interface MarketTopic {
  title: string
  channel: string
  why?: string
  done: boolean
}

export interface ActivityItem {
  id: number
  icon: string
  text: string
  detail?: string
  tone: 'info' | 'good' | 'search' | 'expert'
  at: number
}

export interface RunState {
  status: 'connecting' | 'running' | 'waiting_input' | 'completed' | 'failed'
  stages: string[]
  currentStage?: string
  completedStages: string[]
  blueprint?: Record<string, unknown>
  personas: Persona[]
  experts: Record<number, ExpertState>
  market: MarketBrief[]
  marketTopics: MarketTopic[]
  boardTurns: BoardTurn[]
  activity: ActivityItem[]
  clarifyQuestions: { id: string; question: string; why: string }[] | null
  chart?: Record<string, unknown>
  aggregates?: Record<string, unknown>
  totalCostUsd: number
  engagementId?: number
  error?: string
}

const initial = (): RunState => ({
  status: 'connecting',
  stages: [],
  completedStages: [],
  personas: [],
  experts: {},
  market: [],
  marketTopics: [],
  boardTurns: [],
  activity: [],
  clarifyQuestions: null,
  totalCostUsd: 0,
})

const STAGE_NAMES: Record<string, string> = {
  architect: 'Panel Architect', personas: 'Casting experts', market: 'Market intelligence',
  insights: 'Expert analysis', synthesis: 'Synthesis', debate: 'Board debate',
  minutes: 'Minutes & vote', draft: 'Drafting chart', refine: 'Refining chart',
  revise: 'Revising chart', breakthrough: 'Breakthrough thinking', workchart: 'Work chart',
}

let activitySeq = 0
function log(state: RunState, item: Omit<ActivityItem, 'id' | 'at'>): ActivityItem[] {
  const next = [{ ...item, id: ++activitySeq, at: Date.now() }, ...state.activity]
  return next.slice(0, 60)
}

function reduce(state: RunState, event: RunEvent): RunState {
  const d = event.data as Record<string, any>
  switch (event.type) {
    case 'run.started':
      return { ...state, status: 'running', stages: (d.stages as string[]) ?? [], activity: log(state, { icon: '✦', text: 'Engagement started', tone: 'info' }) }
    case 'stage.started':
      return { ...state, currentStage: d.stage, activity: log(state, { icon: '◐', text: `${STAGE_NAMES[d.stage] ?? d.stage} started`, tone: 'info' }) }
    case 'stage.completed': {
      const cost = d.usage?.totalCostUsd
      return {
        ...state,
        completedStages: [...state.completedStages, d.stage],
        totalCostUsd: typeof cost === 'number' ? cost : state.totalCostUsd,
        activity: log(state, { icon: '✓', text: `${STAGE_NAMES[d.stage] ?? d.stage} complete`, tone: 'good' }),
      }
    }
    case 'blueprint.ready': {
      const bp = d.blueprint as any
      const n = (bp?.disciplines ?? []).reduce((a: number, x: any) => a + (x.count || 0), 0)
      return { ...state, blueprint: d.blueprint, activity: log(state, { icon: '✦', text: `Blueprint ready — ${n} seats across ${(bp?.disciplines ?? []).length} disciplines`, detail: bp?.coverageNotes, tone: 'good' }) }
    }
    case 'persona.created': {
      const personas = [...state.personas, d.persona]
      const experts = { ...state.experts }
      experts[personas.length - 1] = { index: personas.length - 1, persona: d.persona, status: 'pending' }
      return { ...state, personas, experts, activity: log(state, { icon: '★', text: `Cast ${d.persona.name}`, detail: `${d.persona.title} · ${d.persona.discipline ?? ''}`, tone: 'info' }) }
    }
    case 'expert.started': {
      const experts = { ...state.experts }
      experts[d.index] = { ...(experts[d.index] ?? { index: d.index }), status: 'thinking' }
      return { ...state, experts }
    }
    case 'expert.completed': {
      const experts = { ...state.experts }
      experts[d.index] = { ...(experts[d.index] ?? { index: d.index }), status: 'done', insight: d.insight }
      return { ...state, experts, activity: log(state, { icon: '✦', text: `${d.personaName} delivered their analysis`, tone: 'expert' }) }
    }
    case 'market.planned': {
      const topics: MarketTopic[] = (d.topics ?? []).map((t: any) => ({ ...t, done: false }))
      return { ...state, marketTopics: topics, activity: log(state, { icon: '⌕', text: `Researching ${topics.length} market topics live`, detail: topics.map((t) => t.title).join(' · '), tone: 'search' }) }
    }
    case 'market.completed': {
      const marketTopics = state.marketTopics.map((t) => (t.title === d.topic ? { ...t, done: true } : t))
      return { ...state, market: [...state.market, d as MarketBrief], marketTopics, activity: log(state, { icon: d.channel === 'x' ? '𝕏' : '⌕', text: `Researched: ${d.topic}`, detail: `${(d.citations ?? []).length} sources cited`, tone: 'search' }) }
    }
    case 'board.turn':
      return { ...state, boardTurns: [...state.boardTurns, d as BoardTurn], activity: log(state, { icon: '❝', text: `${d.speaker} spoke (round ${d.round})`, tone: 'expert' }) }
    case 'clarify':
      return { ...state, status: 'waiting_input', clarifyQuestions: d.questions, activity: log(state, { icon: '?', text: 'Awaiting your answers', tone: 'info' }) }
    case 'chart.draft':
      return { ...state, chart: d.chart, activity: log(state, { icon: '⇄', text: 'Draft work chart ready', tone: 'good' }) }
    case 'chart.final':
      return { ...state, chart: d.chart }
    case 'breakthrough.ready':
      return { ...state, chart: state.chart ? { ...state.chart, breakthroughOpportunities: d.opportunities } : state.chart, activity: log(state, { icon: '✧', text: `${(d.opportunities ?? []).length} breakthrough opportunities identified`, tone: 'good' }) }
    case 'pulse.batch':
      return { ...state, aggregates: d.aggregates }
    case 'run.completed':
      return {
        ...state,
        status: 'completed',
        engagementId: d.engagementId,
        totalCostUsd: d.usage?.total_cost_usd ?? state.totalCostUsd,
        activity: log(state, { icon: '✦', text: 'Engagement complete', tone: 'good' }),
      }
    case 'run.error':
      return { ...state, status: 'failed', error: d.message, activity: log(state, { icon: '!', text: `Failed: ${d.message}`, tone: 'info' }) }
    default:
      return state
  }
}

export function useRun(runId: string | null) {
  const [state, setState] = useState<RunState>(initial)
  const lastSeq = useRef(0)

  useEffect(() => {
    if (!runId) return
    setState(initial())
    lastSeq.current = 0
    let source: EventSource | null = null
    let closed = false

    const connect = () => {
      source = new EventSource(`/api/runs/${runId}/events?lastEventId=${lastSeq.current}`)
      const handle = (e: MessageEvent, type: string) => {
        const seq = Number((e as MessageEvent).lastEventId || 0)
        if (seq) lastSeq.current = seq
        const event: RunEvent = { seq, type, data: JSON.parse(e.data) }
        setState((s) => reduce(s, event))
        if (type === 'run.completed' || type === 'run.error') {
          closed = true
          source?.close()
        }
      }
      const types = [
        'run.started', 'stage.started', 'stage.completed', 'blueprint.ready',
        'persona.created', 'expert.started', 'expert.completed', 'market.planned',
        'market.completed', 'board.turn', 'clarify', 'chart.draft', 'chart.final',
        'breakthrough.ready', 'pulse.batch', 'run.completed', 'run.error',
      ]
      for (const t of types) source.addEventListener(t, (e) => handle(e as MessageEvent, t))
      source.onerror = () => {
        source?.close()
        if (!closed) setTimeout(connect, 2000) // reconnect with replay via lastEventId
      }
    }
    connect()
    return () => {
      closed = true
      source?.close()
    }
  }, [runId])

  return state
}
