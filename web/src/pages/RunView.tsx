import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { useRun, type ExpertState } from '../api/useRun'
import ConstellationMap from '../components/ConstellationMap'
import ProgressRail from '../components/ProgressRail'
import CostBadge from '../components/CostBadge'
import CitationText from '../components/CitationText'
import WorkChartView from '../components/workchart/WorkChartView'

function ExpertDrawer({ expert, onClose }: { expert: ExpertState; onClose: () => void }) {
  const insight = expert.insight as any
  const items = insight?.insights_and_analysis ?? []
  return (
    <div className="card fade-up" style={{ position: 'sticky', top: 20, maxHeight: '80vh', overflowY: 'auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
        <div>
          <h3 style={{ margin: 0 }}>{expert.persona?.name}</h3>
          <div className="dim" style={{ fontSize: 13 }}>{expert.persona?.title} · {expert.persona?.discipline}</div>
        </div>
        <button className="btn" onClick={onClose} style={{ padding: '4px 10px' }}>✕</button>
      </div>
      <p className="muted" style={{ fontSize: 13 }}>{expert.persona?.background}</p>
      {expert.status !== 'done' && <p className="dim">Analysis {expert.status === 'thinking' ? 'in progress…' : 'queued.'}</p>}
      {insight?.stance != null && (
        <p>Stance <strong>{insight.stance}/5</strong> (confidence {insight.confidence}/5) — “{insight.one_liner}”<br />
          <span className="dim">Top concern: {insight.top_concern}</span></p>
      )}
      {items.map((item: any, i: number) => (
        <div key={i} style={{ borderTop: '1px solid var(--hairline)', paddingTop: 10, marginTop: 10 }}>
          <div style={{ fontWeight: 600 }}>{item.insight}</div>
          <div className="muted" style={{ fontSize: 13, margin: '6px 0' }}>{item.supporting_reasoning}</div>
          <div className="chip" style={{ marginBottom: 6 }}>confidence: {item.confidence_level}</div>
          <ul className="muted" style={{ fontSize: 13, margin: '4px 0' }}>
            {item.implementation_ideas?.map((idea: string, j: number) => <li key={j}>{idea}</li>)}
          </ul>
        </div>
      ))}
    </div>
  )
}

function ClarifyDialog({ runId, questions }: { runId: string; questions: { id: string; question: string; why: string }[] }) {
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [sent, setSent] = useState(false)
  const submit = async () => {
    await api.answer(runId, answers)
    setSent(true)
  }
  if (sent) return <div className="card">Answers sent — refining the chart…</div>
  return (
    <div className="card fade-up" style={{ borderColor: 'var(--star-gold)' }}>
      <h3 style={{ marginTop: 0 }}>The analyst needs a few answers</h3>
      {questions.map((q) => (
        <div key={q.id} style={{ marginBottom: 12 }}>
          <label className="label" style={{ textTransform: 'none', fontSize: 14, color: 'var(--ink-hi)' }}>{q.question}</label>
          <div className="dim" style={{ fontSize: 12, marginBottom: 6 }}>{q.why}</div>
          <input className="input" value={answers[q.id] ?? ''} onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })} />
        </div>
      ))}
      <button className="btn btn-primary" onClick={submit}>Send answers</button>
      <span className="dim" style={{ marginLeft: 12, fontSize: 12 }}>or wait — the draft stands if you skip this</span>
    </div>
  )
}

export default function RunView() {
  const { runId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const run = useRun(runId ?? null)
  const [selected, setSelected] = useState<ExpertState | null>(null)

  useEffect(() => {
    if (run.status === 'completed' && run.engagementId) {
      queryClient.invalidateQueries({ queryKey: ['engagement', String(run.engagementId)] })
      queryClient.invalidateQueries({ queryKey: ['engagements'] })
      const t = setTimeout(() => navigate(`/e/${run.engagementId}`), 1200)
      return () => clearTimeout(t)
    }
  }, [run.status, run.engagementId, navigate, queryClient])

  const doneCount = Object.values(run.experts).filter((e) => e.status === 'done').length
  const total = Object.keys(run.experts).length

  return (
    <div className="fade-up">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <h1 style={{ margin: '8px 0', display: 'flex', alignItems: 'center', gap: 14 }}>
          {(run.status === 'running' || run.status === 'connecting') && (
            <svg width="34" height="34" viewBox="0 0 34 34" aria-hidden className="float-y">
              <circle cx="17" cy="17" r="14" fill="none" stroke="url(#run-grad)" strokeWidth="2.2" strokeDasharray="58 30" strokeLinecap="round" className="orbit" style={{ transformOrigin: '17px 17px' }} />
              <defs>
                <linearGradient id="run-grad" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#2a5fc4" /><stop offset="100%" stopColor="#0e9f8a" />
                </linearGradient>
              </defs>
              <circle cx="17" cy="17" r="3.4" fill="#e8b64c" />
            </svg>
          )}
          <span>
            {run.status === 'completed' ? 'Engagement complete' : run.status === 'failed' ? 'Engagement failed' : 'Engagement '}
            {run.status !== 'completed' && run.status !== 'failed' && <span className="gradient-text">in motion</span>}
          </span>
        </h1>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <CostBadge usd={run.totalCostUsd} />
          {run.status === 'running' && (
            <button className="btn btn-danger" onClick={() => runId && api.cancelRun(runId)}>Cancel</button>
          )}
        </div>
      </div>

      <div style={{ margin: '10px 0 18px' }}>
        <ProgressRail stages={run.stages} currentStage={run.currentStage} completedStages={run.completedStages} />
      </div>

      {run.status === 'failed' && (
        <div className="card" style={{ borderColor: 'var(--status-critical)' }}>
          <strong>Run failed:</strong> {run.error}
        </div>
      )}
      {run.status === 'completed' && (
        <div className="card" style={{ borderColor: 'var(--status-good)' }}>
          ✦ Engagement complete — opening the report…
        </div>
      )}

      {run.clarifyQuestions && run.status === 'waiting_input' && runId && (
        <div style={{ margin: '0 0 18px' }}>
          <ClarifyDialog runId={runId} questions={run.clarifyQuestions} />
        </div>
      )}

      {total === 0 && (run.status === 'running' || run.status === 'connecting') && (
        <div className="card" style={{ textAlign: 'center', padding: '56px 24px' }}>
          <svg width="72" height="72" viewBox="0 0 72 72" aria-hidden style={{ margin: '0 auto', display: 'block' }}>
            <circle cx="36" cy="36" r="30" fill="none" stroke="var(--hairline-strong)" strokeWidth="1" strokeDasharray="4 6" className="orbit" style={{ transformOrigin: '36px 36px' }} />
            <circle cx="36" cy="36" r="20" fill="none" stroke="var(--indigo-line)" strokeWidth="1" strokeDasharray="3 5" className="orbit" style={{ transformOrigin: '36px 36px', animationDirection: 'reverse', animationDuration: '4s' }} />
            <circle cx="36" cy="16" r="3.4" fill="var(--star-gold-bright)" className="orbit" style={{ transformOrigin: '36px 36px', animationDuration: '3.4s' }} />
            <circle cx="36" cy="36" r="4.5" fill="var(--indigo-deep)" />
          </svg>
          <h3 style={{ margin: '18px 0 6px' }}>
            {run.blueprint ? 'Casting your experts…' : 'The Panel Architect is designing your panel'}
          </h3>
          <p className="dim" style={{ margin: 0, fontSize: 13 }}>
            {run.blueprint
              ? 'Each expert will appear as a star in the constellation below as they join.'
              : 'Mapping the disciplines, seniority mix, and contrarian seats your problem demands.'}
          </p>
          {run.blueprint != null && (
            <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap', marginTop: 16 }}>
              {((run.blueprint as any).disciplines ?? []).map((d: any, i: number) => (
                <span key={i} className="chip fade-up" style={{ borderColor: 'var(--indigo-line)' }}>
                  ✦ {d.name} <span className="mono dim">×{d.count}</span>
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {total > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: selected ? '1.6fr 1fr' : '1fr', gap: 18 }}>
          <div className="card" style={{ padding: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 10px' }}>
              <span className="muted" style={{ fontSize: 13 }}>The panel — {doneCount}/{total} analyses complete</span>
              <span className="dim" style={{ fontSize: 12 }}>hover a star · click for the full analysis</span>
            </div>
            <ConstellationMap experts={run.experts} onSelect={setSelected} />
          </div>
          {selected && <ExpertDrawer expert={run.experts[selected.index] ?? selected} onClose={() => setSelected(null)} />}
        </div>
      )}

      {run.boardTurns.length > 0 && (
        <div className="card" style={{ marginTop: 18 }}>
          <h3 style={{ marginTop: 0 }}>Board transcript</h3>
          {run.boardTurns.map((t, i) => (
            <div key={i} style={{ borderTop: i ? '1px solid var(--hairline)' : 'none', padding: '10px 0' }}>
              <div style={{ fontWeight: 600, fontSize: 13 }}>
                <span className="chip" style={{ marginRight: 8 }}>R{t.round}</span>{t.speaker}
              </div>
              <div className="muted" style={{ fontSize: 14, marginTop: 4 }}>{t.statement}</div>
            </div>
          ))}
        </div>
      )}

      {run.market.length > 0 && (
        <div className="card" style={{ marginTop: 18 }}>
          <h3 style={{ marginTop: 0 }}>Market intelligence <span className="dim" style={{ fontSize: 12 }}>(live web{run.market.some((m) => m.channel === 'x') ? ' + X' : ''} search)</span></h3>
          {run.market.map((m, i) => (
            <div key={i} style={{ borderTop: i ? '1px solid var(--hairline)' : 'none', padding: '10px 0' }}>
              <div style={{ fontWeight: 600 }}>{m.topic} {m.channel === 'x' && <span className="chip">𝕏</span>}</div>
              <div className="muted" style={{ fontSize: 14, marginTop: 4 }}>
                <CitationText text={m.findings} citations={m.citations} />
              </div>
            </div>
          ))}
        </div>
      )}

      {run.chart && (
        <div style={{ marginTop: 18 }}>
          <WorkChartView chart={run.chart as any} />
        </div>
      )}

      {run.aggregates != null && (
        <div className="card" style={{ marginTop: 18 }}>
          <h3 style={{ marginTop: 0 }}>Pulse results are in</h3>
          <p className="muted">Opening the full report…</p>
        </div>
      )}
    </div>
  )
}
