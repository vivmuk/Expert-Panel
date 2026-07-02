// Board meeting result: minutes, vote tally, and the full debate transcript.
import { useState } from 'react'
import type { Persona } from '../../api/client'

export interface BoardResult {
  problem: string
  members: Persona[]
  transcript: { round: number; speaker: string; statement: string }[]
  minutes: {
    motion: string
    member_positions: { member: string; evolution: string; vote: 'for' | 'against' | 'abstain' }[]
    decisive_arguments: string[]
    resolution: string
    conditions: string[]
  }
}

const VOTE_COLORS = { for: 'var(--status-good)', against: 'var(--status-critical)', abstain: 'var(--ink-low)' }
const VOTE_ICONS = { for: '✓', against: '✗', abstain: '○' }

export default function BoardReport({ result }: { result: BoardResult }) {
  const [showTranscript, setShowTranscript] = useState(false)
  const m = result.minutes
  const tally = { for: 0, against: 0, abstain: 0 }
  m?.member_positions?.forEach((p) => { tally[p.vote] = (tally[p.vote] ?? 0) + 1 })

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Resolution</h3>
        <p style={{ fontSize: 16 }}>{m?.resolution}</p>
        <div style={{ display: 'flex', gap: 12 }}>
          {(['for', 'against', 'abstain'] as const).map((v) => (
            <span key={v} className="chip" style={{ color: VOTE_COLORS[v] }}>
              {VOTE_ICONS[v]} {tally[v]} {v}
            </span>
          ))}
        </div>
        {!!m?.conditions?.length && (
          <>
            <div className="label" style={{ marginTop: 12 }}>Conditions attached</div>
            <ul className="muted" style={{ fontSize: 14 }}>{m.conditions.map((c, i) => <li key={i}>{c}</li>)}</ul>
          </>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>How each member landed</h3>
        {m?.member_positions?.map((p, i) => (
          <div key={i} style={{ display: 'flex', gap: 12, padding: '8px 0', borderTop: i ? '1px solid var(--hairline)' : 'none' }}>
            <span style={{ color: VOTE_COLORS[p.vote], fontWeight: 700, width: 20, flexShrink: 0 }}>{VOTE_ICONS[p.vote]}</span>
            <div>
              <strong style={{ fontSize: 14 }}>{p.member}</strong>
              <p className="muted" style={{ fontSize: 13, margin: '2px 0' }}>{p.evolution}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Decisive arguments</h3>
        <ul className="muted" style={{ fontSize: 14 }}>
          {m?.decisive_arguments?.map((a, i) => <li key={i}>{a}</li>)}
        </ul>
      </div>

      <div>
        <button className="btn" onClick={() => setShowTranscript(!showTranscript)}>
          {showTranscript ? 'Hide' : 'Show'} full transcript ({result.transcript?.length ?? 0} statements)
        </button>
        {showTranscript && (
          <div className="card" style={{ marginTop: 12 }}>
            {result.transcript?.map((t, i) => (
              <div key={i} style={{ borderTop: i ? '1px solid var(--hairline)' : 'none', padding: '10px 0' }}>
                <div style={{ fontWeight: 600, fontSize: 13 }}>
                  <span className="chip" style={{ marginRight: 8 }}>Round {t.round}</span>{t.speaker}
                </div>
                <p className="muted" style={{ fontSize: 14, margin: '4px 0 0' }}>{t.statement}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
