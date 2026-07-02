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

export interface RunState {
  status: 'connecting' | 'running' | 'waiting_input' | 'completed' | 'failed'
  stages: string[]
  currentStage?: string
  completedStages: string[]
  blueprint?: Record<string, unknown>
  personas: Persona[]
  experts: Record<number, ExpertState>
  market: MarketBrief[]
  boardTurns: BoardTurn[]
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
  boardTurns: [],
  clarifyQuestions: null,
  totalCostUsd: 0,
})

function reduce(state: RunState, event: RunEvent): RunState {
  const d = event.data as Record<string, any>
  switch (event.type) {
    case 'run.started':
      return { ...state, status: 'running', stages: (d.stages as string[]) ?? [] }
    case 'stage.started':
      return { ...state, currentStage: d.stage }
    case 'stage.completed': {
      const cost = d.usage?.totalCostUsd
      return {
        ...state,
        completedStages: [...state.completedStages, d.stage],
        totalCostUsd: typeof cost === 'number' ? cost : state.totalCostUsd,
      }
    }
    case 'blueprint.ready':
      return { ...state, blueprint: d.blueprint }
    case 'persona.created': {
      const personas = [...state.personas, d.persona]
      const experts = { ...state.experts }
      experts[personas.length - 1] = { index: personas.length - 1, persona: d.persona, status: 'pending' }
      return { ...state, personas, experts }
    }
    case 'expert.started': {
      const experts = { ...state.experts }
      experts[d.index] = { ...(experts[d.index] ?? { index: d.index }), status: 'thinking' }
      return { ...state, experts }
    }
    case 'expert.completed': {
      const experts = { ...state.experts }
      experts[d.index] = { ...(experts[d.index] ?? { index: d.index }), status: 'done', insight: d.insight }
      return { ...state, experts }
    }
    case 'market.completed':
      return { ...state, market: [...state.market, d as MarketBrief] }
    case 'board.turn':
      return { ...state, boardTurns: [...state.boardTurns, d as BoardTurn] }
    case 'clarify':
      return { ...state, status: 'waiting_input', clarifyQuestions: d.questions }
    case 'chart.draft':
    case 'chart.final':
      return { ...state, chart: d.chart }
    case 'breakthrough.ready':
      return { ...state, chart: state.chart ? { ...state.chart, breakthroughOpportunities: d.opportunities } : state.chart }
    case 'pulse.batch':
      return { ...state, aggregates: d.aggregates }
    case 'run.completed':
      return {
        ...state,
        status: 'completed',
        engagementId: d.engagementId,
        totalCostUsd: d.usage?.total_cost_usd ?? state.totalCostUsd,
      }
    case 'run.error':
      return { ...state, status: 'failed', error: d.message }
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
        'persona.created', 'expert.started', 'expert.completed', 'market.completed',
        'board.turn', 'clarify', 'chart.draft', 'chart.final', 'breakthrough.ready',
        'pulse.batch', 'run.completed', 'run.error',
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
