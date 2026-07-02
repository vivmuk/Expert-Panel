import { useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import PanelReport, { type PanelResult } from '../components/reports/PanelReport'
import BoardReport, { type BoardResult } from '../components/reports/BoardReport'
import WorkChartView, { type WorkChart } from '../components/workchart/WorkChartView'
import DiffView from '../components/workchart/DiffView'
import PulseChart, { type PulseAggregates } from '../components/charts/PulseChart'
import CostBadge from '../components/CostBadge'
import { exportElementAsHtml } from '../lib/exportHtml'

export default function EngagementDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const reportRef = useRef<HTMLDivElement>(null)
  const [selectedRev, setSelectedRev] = useState<number | null>(null)
  const [instruction, setInstruction] = useState('')
  const [revising, setRevising] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')

  const { data: engagement, isLoading } = useQuery({
    queryKey: ['engagement', id],
    queryFn: () => api.engagement(id!),
    enabled: !!id,
  })

  const { data: revision } = useQuery({
    queryKey: ['revision', id, selectedRev],
    queryFn: () => api.revision(id!, selectedRev!),
    enabled: !!id && selectedRev != null,
  })

  if (isLoading) return <p className="dim">Loading…</p>
  if (!engagement) return <p className="dim">Engagement not found.</p>

  const active = selectedRev != null && revision ? revision : engagement.latest
  const result = active?.result as Record<string, unknown> | undefined
  const mode = engagement.mode

  const revise = async () => {
    if (!instruction.trim()) return
    setRevising(true)
    try {
      const res = await api.createRun({
        mode: 'workchart',
        engagementId: engagement.id,
        input: { problem: 'revision', instruction },
        note: instruction.slice(0, 120),
      })
      navigate(`/run/${res.runId}`)
    } finally {
      setRevising(false)
    }
  }

  const rename = async () => {
    if (titleDraft.trim()) {
      await api.renameEngagement(engagement.id, titleDraft.trim())
      queryClient.invalidateQueries({ queryKey: ['engagement', id] })
      queryClient.invalidateQueries({ queryKey: ['engagements'] })
    }
    setRenaming(false)
  }

  return (
    <div className="fade-up">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: 14, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 280 }}>
          {renaming ? (
            <div style={{ display: 'flex', gap: 8 }}>
              <input className="input" value={titleDraft} onChange={(e) => setTitleDraft(e.target.value)} autoFocus />
              <button className="btn btn-primary" onClick={rename}>Save</button>
            </div>
          ) : (
            <h1 style={{ margin: '8px 0', cursor: 'text' }} onClick={() => { setTitleDraft(engagement.title); setRenaming(true) }} title="Click to rename">
              {engagement.title}
            </h1>
          )}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <span className="chip">{mode}</span>
            <span className="chip">{engagement.status}</span>
            <CostBadge usd={engagement.total_cost_usd ?? 0} label="total spend" />
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => reportRef.current && exportElementAsHtml(reportRef.current, engagement.title)}>
            ⬇ HTML
          </button>
          <button className="btn" onClick={() => window.print()}>⎙ PDF</button>
        </div>
      </div>

      {(engagement.revisions?.length ?? 0) > 1 && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', margin: '14px 0', flexWrap: 'wrap' }}>
          <span className="label" style={{ margin: 0 }}>Revisions</span>
          {engagement.revisions.map((r) => {
            const isActive = selectedRev === r.rev || (selectedRev == null && r.rev === engagement.latest?.rev)
            return (
              <button
                key={r.rev}
                className="chip"
                onClick={() => setSelectedRev(r.rev === engagement.latest?.rev ? null : r.rev)}
                title={`${r.note ?? ''} · ${new Date(r.created_at + 'Z').toLocaleString()}`}
                style={{
                  cursor: 'pointer',
                  borderColor: isActive ? 'var(--indigo-deep)' : 'var(--hairline)',
                  color: isActive ? 'var(--indigo-deep)' : 'var(--ink-mid)',
                  fontWeight: isActive ? 700 : 400,
                  background: 'var(--space-2)',
                }}
              >
                v{r.rev}
              </button>
            )
          })}
          {selectedRev != null && <span className="dim" style={{ fontSize: 12 }}>viewing v{selectedRev} — select the latest to enable revisions</span>}
        </div>
      )}

      <div ref={reportRef} style={{ marginTop: 16 }}>
        {!result && <div className="card muted">This engagement has no results yet{engagement.status === 'running' ? ' — a run is in progress' : ''}.</div>}
        {result && mode === 'workchart' && (
          <div style={{ display: 'grid', gap: 16 }}>
            {(result.changeLog as WorkChart['changeLog']) && <DiffView changeLog={result.changeLog as NonNullable<WorkChart['changeLog']>} />}
            <WorkChartView chart={result as unknown as WorkChart} />
          </div>
        )}
        {result && mode === 'board_meeting' && <BoardReport result={result as unknown as BoardResult} />}
        {result && mode === 'quick_pulse' && (
          <div style={{ display: 'grid', gap: 16 }}>
            <PulseChart aggregates={result.aggregates as unknown as PulseAggregates} />
            <div className="card">
              <h3 style={{ marginTop: 0 }}>Top concerns raised</h3>
              <ul className="muted" style={{ fontSize: 14 }}>
                {((result.aggregates as any)?.top_concerns ?? []).slice(0, 12).map((c: string, i: number) => <li key={i}>{c}</li>)}
              </ul>
            </div>
          </div>
        )}
        {result && (mode === 'deep_dive' || mode === 'red_team') && <PanelReport result={result as unknown as PanelResult} />}
      </div>

      {mode === 'workchart' && selectedRev == null && engagement.status !== 'running' && (
        <div className="card" style={{ marginTop: 18, borderColor: 'var(--hairline-strong)' }}>
          <h3 style={{ marginTop: 0 }}>Update this plan</h3>
          <p className="dim" style={{ fontSize: 13, marginTop: -6 }}>
            Describe the change in plain language — a new revision is generated with a change log, and every prior version stays in the history above.
          </p>
          <div style={{ display: 'flex', gap: 10 }}>
            <input
              className="input"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder='e.g. "Make the QA step fully agentic and add a compliance review before payout"'
              onKeyDown={(e) => e.key === 'Enter' && revise()}
            />
            <button className="btn btn-primary" onClick={revise} disabled={revising || !instruction.trim()}>
              {revising ? 'Starting…' : 'Revise'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
