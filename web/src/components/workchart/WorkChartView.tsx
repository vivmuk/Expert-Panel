// Work Chart v2 rendering: current vs future lanes, deltas, agent factory,
// and the "Beyond the Chart" breakthrough opportunities.
import { useState } from 'react'

export interface ChartStep {
  step: string
  task: string
  owner: 'Human' | 'AI Agent' | 'Hybrid' | 'Digital Twin'
  agentFunction?: string | null
  reusableAgentAsset?: { name: string; description: string; reusePotential: string } | null
  successTarget: string
  rule: string
  estimatedTimeMinutes: number
  estimatedCostUSD: number
  fteFraction?: number
  compute?: { modelSize: string; estimatedInputTokens: number; estimatedOutputTokens: number; tools: string[] } | null
}

export interface WorkChart {
  currentProcess: { name?: string; steps: ChartStep[]; assumptions?: string[] }
  futureProcess: { name?: string; steps: ChartStep[]; assumptions?: string[] }
  deltas?: { timeSavedPct: number; costSavedPct: number; fteFreed: number; narrative: string }
  agentFactory?: { assetName: string; functionType: string; description: string; usedInSteps: string[]; buildComplexity: string }[]
  breakthroughOpportunities?: {
    title: string; thesis: string; whatChanges: string; ambitionLevel: string
    orderOfMagnitudeImpact: string; prerequisites: string[]; firstExperiment: string
  }[]
  changeLog?: { stepRef: string; changeType: string; before: string; after: string; rationale: string }[]
}

export const OWNER_COLORS: Record<string, string> = {
  Human: 'var(--owner-human)',
  'AI Agent': 'var(--owner-agent)',
  Hybrid: 'var(--owner-hybrid)',
  'Digital Twin': 'var(--owner-twin)',
}

const FUNCTION_ICONS: Record<string, string> = {
  retrieval: '⌕', reasoning: '∴', generation: '✎', orchestration: '⧉',
  extraction: '⇥', validation: '✓', communication: '➤',
}

function fmtMinutes(min: number) {
  if (min >= 60) return `${(min / 60).toFixed(min % 60 ? 1 : 0)}h`
  return `${min}m`
}

function StepCard({ step, highlight }: { step: ChartStep; highlight?: 'added' | 'modified' | 'reassigned' }) {
  const color = OWNER_COLORS[step.owner] ?? 'var(--ink-low)'
  return (
    <div
      className="card"
      style={{
        padding: 14,
        borderLeft: `3px solid ${color}`,
        ...(highlight ? { boxShadow: `0 0 0 1px var(--star-gold)` } : {}),
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'baseline' }}>
        <div style={{ fontWeight: 650, fontSize: 14 }}>{step.step}</div>
        <span className="chip" style={{ color, borderColor: color, flexShrink: 0 }}>
          {step.agentFunction ? `${FUNCTION_ICONS[step.agentFunction] ?? ''} ` : ''}{step.owner}
        </span>
      </div>
      <div className="muted" style={{ fontSize: 13, margin: '6px 0' }}>{step.task}</div>
      <div className="dim" style={{ fontSize: 12 }}>
        <span className="mono">{fmtMinutes(step.estimatedTimeMinutes)}</span> · <span className="mono">${step.estimatedCostUSD}</span>
        {step.fteFraction != null && <> · <span className="mono">{step.fteFraction} FTE</span></>}
        {step.compute && <> · {step.compute.modelSize} model{step.compute.tools?.length ? ` · ${step.compute.tools.join(', ')}` : ''}</>}
      </div>
      {step.reusableAgentAsset && (
        <div className="chip" style={{ marginTop: 8, color: 'var(--star-gold)', borderColor: 'rgba(232,182,76,0.4)' }}>
          ♺ {step.reusableAgentAsset.name} ({step.reusableAgentAsset.reusePotential})
        </div>
      )}
      <div className="dim" style={{ fontSize: 11, marginTop: 6 }}>Target: {step.successTarget}</div>
    </div>
  )
}

function Lane({ title, steps, totalLabel, changedSteps }: { title: string; steps: ChartStep[]; totalLabel: string; changedSteps?: Map<string, string> }) {
  return (
    <div style={{ flex: 1, minWidth: 300 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
        <h3 style={{ margin: 0 }}>{title}</h3>
        <span className="chip mono">{totalLabel}</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {steps.map((s, i) => (
          <div key={i}>
            <StepCard step={s} highlight={changedSteps?.get(s.step) as 'added' | 'modified' | 'reassigned' | undefined} />
            {i < steps.length - 1 && (
              <svg width="100%" height="22" aria-hidden>
                <line x1="50%" y1="0" x2="50%" y2="16" stroke="var(--hairline-strong)" strokeWidth="1.5" />
                <polygon points="0,-0 0,0" />
                <path d="M -4 10 L 0 16 L 4 10" transform="translate(0,0)" stroke="var(--hairline-strong)" strokeWidth="1.5" fill="none"
                  style={{ transform: 'translateX(50%)' }} />
              </svg>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function laneTotals(steps: ChartStep[]) {
  const time = steps.reduce((a, s) => a + (s.estimatedTimeMinutes || 0), 0)
  const cost = steps.reduce((a, s) => a + (s.estimatedCostUSD || 0), 0)
  return `${fmtMinutes(time)} · $${Math.round(cost)}`
}

const AMBITION_COLORS: Record<string, string> = {
  incremental: 'var(--ink-low)',
  'step-change': 'var(--star-blue)',
  reinvention: 'var(--star-gold)',
}

export default function WorkChartView({ chart }: { chart: WorkChart }) {
  const [showAssumptions, setShowAssumptions] = useState(false)
  const changed = new Map((chart.changeLog ?? []).map((c) => [c.stepRef, c.changeType]))

  return (
    <div style={{ display: 'grid', gap: 18 }}>
      {chart.deltas && (
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {[
            { label: 'Time saved', value: `${chart.deltas.timeSavedPct}%` },
            { label: 'Cost saved', value: `${chart.deltas.costSavedPct}%` },
            { label: 'FTEs freed', value: String(chart.deltas.fteFreed) },
          ].map((t) => (
            <div className="card" key={t.label} style={{ padding: '12px 18px', flex: 1, minWidth: 120 }}>
              <div className="label">{t.label}</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--star-gold)' }}>{t.value}</div>
            </div>
          ))}
          <div className="card" style={{ flex: 3, minWidth: 240, padding: '12px 18px' }}>
            <div className="label">The story</div>
            <div className="muted" style={{ fontSize: 13 }}>{chart.deltas.narrative}</div>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: 10, fontSize: 12, flexWrap: 'wrap' }}>
        {Object.entries(OWNER_COLORS).map(([owner, color]) => (
          <span key={owner} className="chip"><span style={{ width: 9, height: 9, borderRadius: 2, background: color, display: 'inline-block' }} /> {owner}</span>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
        <Lane title="Today" steps={chart.currentProcess?.steps ?? []} totalLabel={laneTotals(chart.currentProcess?.steps ?? [])} />
        <Lane title="Agent era" steps={chart.futureProcess?.steps ?? []} totalLabel={laneTotals(chart.futureProcess?.steps ?? [])} changedSteps={changed} />
      </div>

      {(chart.agentFactory?.length ?? 0) > 0 && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Agent factory <span className="dim" style={{ fontSize: 12 }}>reusable agent assets this process would mint</span></h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 12 }}>
            {chart.agentFactory!.map((a) => (
              <div key={a.assetName} style={{ border: '1px solid var(--hairline)', borderRadius: 10, padding: 12 }}>
                <div style={{ fontWeight: 650, color: 'var(--star-gold)' }}>♺ {a.assetName}</div>
                <div className="chip" style={{ margin: '6px 0' }}>{FUNCTION_ICONS[a.functionType] ?? ''} {a.functionType} · build: {a.buildComplexity}</div>
                <div className="muted" style={{ fontSize: 13 }}>{a.description}</div>
                <div className="dim" style={{ fontSize: 11, marginTop: 6 }}>Used in: {a.usedInSteps.join(', ')}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {(chart.breakthroughOpportunities?.length ?? 0) > 0 && (
        <div className="card" style={{ borderColor: 'rgba(232,182,76,0.35)', background: 'linear-gradient(180deg, rgba(232,182,76,0.05), transparent)' }}>
          <h3 style={{ marginTop: 0 }}>Beyond the chart <span className="dim" style={{ fontSize: 12 }}>type-2 thinking — what the incremental redesign can't see</span></h3>
          <div style={{ display: 'grid', gap: 14 }}>
            {chart.breakthroughOpportunities!.map((o, i) => (
              <div key={i} style={{ borderTop: i ? '1px solid var(--hairline)' : 'none', paddingTop: i ? 14 : 0 }}>
                <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
                  <strong style={{ fontSize: 15 }}>{o.title}</strong>
                  <span className="chip" style={{ color: AMBITION_COLORS[o.ambitionLevel] }}>{o.ambitionLevel}</span>
                  <span className="chip">impact: {o.orderOfMagnitudeImpact}</span>
                </div>
                <p className="muted" style={{ fontSize: 14, margin: '6px 0' }}>{o.thesis}</p>
                <p style={{ fontSize: 13, margin: '6px 0' }}><span className="label" style={{ display: 'inline' }}>What changes: </span><span className="muted">{o.whatChanges}</span></p>
                <p style={{ fontSize: 13, margin: '6px 0' }}><span className="label" style={{ display: 'inline' }}>First experiment: </span><span className="muted">{o.firstExperiment}</span></p>
                {o.prerequisites?.length > 0 && <div className="dim" style={{ fontSize: 12 }}>Prerequisites: {o.prerequisites.join(' · ')}</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      {(chart.currentProcess?.assumptions?.length || chart.futureProcess?.assumptions?.length) && (
        <div>
          <button className="btn" onClick={() => setShowAssumptions(!showAssumptions)}>
            {showAssumptions ? 'Hide' : 'Show'} assumptions
          </button>
          {showAssumptions && (
            <ul className="muted" style={{ fontSize: 13 }}>
              {[...(chart.currentProcess?.assumptions ?? []), ...(chart.futureProcess?.assumptions ?? [])].map((a, i) => <li key={i}>{a}</li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
