// Full report view for panel-flow engagements (deep dive, red team).
import { useState } from 'react'
import CitationText, { type Citation } from '../CitationText'
import type { Persona } from '../../api/client'

interface InsightEntry {
  persona: Persona
  insights_and_analysis?: {
    insight: string
    supporting_reasoning: string
    confidence_level: string
    implementation_ideas: string[]
    identified_risks?: string[]
    identified_opportunities?: string[]
  }[]
  error?: string
}

interface Synthesis {
  executive_summary: string
  key_themes: { theme: string; evidence: string; driving_experts: string[] }[]
  consensus_dissent: { topic: string; type: string; summary: string }[]
  recommendations: { recommendation: string; horizon: string; rationale: string; first_step: string; success_measure: string }[]
  risks_and_blind_spots: string[]
  next_steps: string[]
}

export interface PanelResult {
  problem: string
  blueprint?: { disciplines: { name: string; count: number; rationale: string }[]; mandatedContrarians?: { stance: string; rationale: string }[]; coverageNotes?: string }
  personas: Persona[]
  insights: InsightEntry[]
  market_intelligence?: { topic: string; channel: string; findings: string; citations: Citation[] }[]
  synthesis?: Synthesis
}

const HORIZON_ORDER = ['Now', 'Next', 'Later']
const HORIZON_COLORS: Record<string, string> = { Now: 'var(--status-critical)', Next: 'var(--star-gold)', Later: 'var(--star-blue)' }

export default function PanelReport({ result }: { result: PanelResult }) {
  const [tab, setTab] = useState<'report' | 'experts' | 'market' | 'blueprint'>('report')
  const s = result.synthesis
  const allCitations = (result.market_intelligence ?? []).flatMap((m) => m.citations)

  const tabs = [
    ['report', 'Report'],
    ['experts', `Experts (${result.personas?.length ?? 0})`],
    ['market', 'Market Intel'],
    ['blueprint', 'Blueprint'],
  ] as const

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {tabs.map(([id, label]) => (
          <button key={id} className="btn" onClick={() => setTab(id)}
            style={tab === id ? { borderColor: 'var(--indigo-deep)', background: 'var(--indigo-deep)', color: '#fff' } : {}}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'report' && s && (
        <div style={{ display: 'grid', gap: 16 }}>
          <div className="card">
            <h3 style={{ marginTop: 0 }}>Executive summary</h3>
            <p className="muted" style={{ fontSize: 15 }}><CitationText text={s.executive_summary} citations={allCitations} /></p>
          </div>
          <div className="card">
            <h3 style={{ marginTop: 0 }}>Key themes</h3>
            {s.key_themes.map((t, i) => (
              <div key={i} style={{ borderTop: i ? '1px solid var(--hairline)' : 'none', padding: '10px 0' }}>
                <strong>{t.theme}</strong>
                <p className="muted" style={{ margin: '4px 0', fontSize: 14 }}><CitationText text={t.evidence} citations={allCitations} /></p>
                <div className="dim" style={{ fontSize: 12 }}>Driven by: {t.driving_experts.join(', ')}</div>
              </div>
            ))}
          </div>
          <div className="card">
            <h3 style={{ marginTop: 0 }}>Consensus & dissent</h3>
            {s.consensus_dissent.map((c, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, padding: '6px 0', alignItems: 'baseline' }}>
                <span className="chip" style={{ color: c.type === 'consensus' ? 'var(--status-good)' : 'var(--status-serious)', flexShrink: 0 }}>
                  {c.type === 'consensus' ? '⊕ consensus' : '⊘ dissent'}
                </span>
                <div>
                  <strong style={{ fontSize: 14 }}>{c.topic}</strong>
                  <span className="muted" style={{ fontSize: 14 }}> — {c.summary}</span>
                </div>
              </div>
            ))}
          </div>
          <div className="card">
            <h3 style={{ marginTop: 0 }}>Recommendations</h3>
            {HORIZON_ORDER.map((h) => {
              const recs = s.recommendations.filter((r) => r.horizon === h)
              if (!recs.length) return null
              return (
                <div key={h} style={{ marginBottom: 12 }}>
                  <div className="label" style={{ color: HORIZON_COLORS[h] }}>{h}</div>
                  {recs.map((r, i) => (
                    <div key={i} style={{ padding: '8px 0', borderTop: '1px solid var(--hairline)' }}>
                      <strong style={{ fontSize: 14 }}>{r.recommendation}</strong>
                      <p className="muted" style={{ fontSize: 13, margin: '4px 0' }}>{r.rationale}</p>
                      <div className="dim" style={{ fontSize: 12 }}>First step: {r.first_step} · Measure: {r.success_measure}</div>
                    </div>
                  ))}
                </div>
              )
            })}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div className="card">
              <h3 style={{ marginTop: 0 }}>Risks & blind spots</h3>
              <ul className="muted" style={{ fontSize: 14, paddingLeft: 18 }}>
                {s.risks_and_blind_spots.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
            <div className="card">
              <h3 style={{ marginTop: 0 }}>Next 30 days</h3>
              <ul className="muted" style={{ fontSize: 14, paddingLeft: 18 }}>
                {s.next_steps.map((n, i) => <li key={i}>{n}</li>)}
              </ul>
            </div>
          </div>
        </div>
      )}
      {tab === 'report' && !s && <div className="card muted">No synthesis available for this engagement.</div>}

      {tab === 'experts' && (
        <div style={{ display: 'grid', gap: 12 }}>
          {result.insights?.map((entry, i) => (
            <details key={i} className="card">
              <summary style={{ cursor: 'pointer' }}>
                <strong>{entry.persona?.name}</strong>
                <span className="dim" style={{ fontSize: 13 }}> — {entry.persona?.title} · {entry.persona?.discipline}</span>
              </summary>
              <p className="muted" style={{ fontSize: 13 }}>{entry.persona?.background}</p>
              {entry.error && <p style={{ color: 'var(--status-critical)' }}>Analysis unavailable: {entry.error}</p>}
              {entry.insights_and_analysis?.map((item, j) => (
                <div key={j} style={{ borderTop: '1px solid var(--hairline)', paddingTop: 10, marginTop: 10 }}>
                  <strong style={{ fontSize: 14 }}>{item.insight}</strong>
                  <p className="muted" style={{ fontSize: 13, margin: '6px 0' }}>{item.supporting_reasoning}</p>
                  <span className="chip">confidence: {item.confidence_level}</span>
                  <ul className="muted" style={{ fontSize: 13 }}>
                    {item.implementation_ideas?.map((idea, k) => <li key={k}>{idea}</li>)}
                  </ul>
                  {!!item.identified_risks?.length && <div className="dim" style={{ fontSize: 12 }}>Risks: {item.identified_risks.join(' · ')}</div>}
                  {!!item.identified_opportunities?.length && <div className="dim" style={{ fontSize: 12 }}>Opportunities: {item.identified_opportunities.join(' · ')}</div>}
                </div>
              ))}
            </details>
          ))}
        </div>
      )}

      {tab === 'market' && (
        <div style={{ display: 'grid', gap: 12 }}>
          {(result.market_intelligence ?? []).map((m, i) => (
            <div key={i} className="card">
              <h3 style={{ marginTop: 0 }}>{m.topic} {m.channel === 'x' && <span className="chip">𝕏 sentiment</span>}</h3>
              <p className="muted" style={{ fontSize: 14 }}><CitationText text={m.findings} citations={m.citations} /></p>
              {!!m.citations?.length && (
                <div className="dim" style={{ fontSize: 12 }}>
                  Sources: {m.citations.slice(0, 8).map((c, j) => (
                    <span key={j}>{j > 0 && ' · '}<a href={c.url} target="_blank" rel="noreferrer">[{c.index}] {c.title?.slice(0, 50)}</a></span>
                  ))}
                </div>
              )}
            </div>
          ))}
          {!result.market_intelligence?.length && <div className="card muted">Market intelligence was not enabled for this run.</div>}
        </div>
      )}

      {tab === 'blueprint' && result.blueprint && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Panel blueprint</h3>
          <p className="muted" style={{ fontSize: 14 }}>{result.blueprint.coverageNotes}</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 12 }}>
            {result.blueprint.disciplines.map((d) => (
              <div key={d.name} style={{ border: '1px solid var(--hairline)', borderRadius: 10, padding: 12 }}>
                <strong>{d.name}</strong> <span className="chip mono">{d.count} seats</span>
                <p className="muted" style={{ fontSize: 13, margin: '6px 0 0' }}>{d.rationale}</p>
              </div>
            ))}
          </div>
          {!!result.blueprint.mandatedContrarians?.length && (
            <div style={{ marginTop: 14 }}>
              <div className="label">Mandated contrarians</div>
              {result.blueprint.mandatedContrarians.map((c, i) => (
                <div key={i} className="muted" style={{ fontSize: 13 }}>⚔ {c.stance} — <span className="dim">{c.rationale}</span></div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
