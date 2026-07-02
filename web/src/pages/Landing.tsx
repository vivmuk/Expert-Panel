import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

const MODE_ICONS: Record<string, string> = {
  deep_dive: '✦',
  red_team: '⚔',
  quick_pulse: '◉',
  board_meeting: '♜',
  workchart: '⇄',
  scenario_planning: '⑂',
  due_diligence: '🔍',
  ai_opportunity_scan: '⚡',
  digital_twin: '◍',
}

function Hero() {
  return (
    <header style={{ padding: '48px 0 40px', position: 'relative' }}>
      <svg viewBox="0 0 400 120" style={{ position: 'absolute', right: 0, top: 10, width: 380, opacity: 0.9 }} aria-hidden>
        <g stroke="#8d97c4" strokeWidth="0.7">
          <line x1="40" y1="90" x2="120" y2="30" /><line x1="120" y1="30" x2="210" y2="60" />
          <line x1="210" y1="60" x2="290" y2="20" /><line x1="290" y1="20" x2="360" y2="70" />
          <line x1="120" y1="30" x2="180" y2="100" /><line x1="210" y1="60" x2="180" y2="100" />
        </g>
        {[[40, 90, '#d9a63c'], [120, 30, '#232a4d'], [210, 60, '#2a5fc4'], [290, 20, '#232a4d'], [360, 70, '#d9a63c'], [180, 100, '#4a3aa7']].map(([x, y, c], i) => (
          <circle key={i} cx={x as number} cy={y as number} r={i % 2 ? 3.5 : 2.5} fill={c as string}
            style={{ animation: `twinkle ${3 + i}s ease-in-out infinite` }} />
        ))}
      </svg>
      <h1 style={{ maxWidth: 560, margin: 0 }}>
        A constellation of experts.<br />
        <span style={{ color: 'var(--star-gold)' }}>On demand.</span>
      </h1>
      <p className="muted" style={{ maxWidth: 520, fontSize: 17, marginTop: 16 }}>
        Assemble panels of up to 100 bespoke expert minds, grounded in live web and X intelligence.
        Deep dives, red teams, board debates, and agent-era work charts — the output of a consulting
        firm, in minutes.
      </p>
      <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
        <Link to="/new" className="btn btn-primary" style={{ fontSize: 15 }}>Start an engagement</Link>
        <Link to="/engagements" className="btn">Browse past work</Link>
      </div>
    </header>
  )
}

export default function Landing() {
  const { data: modes } = useQuery({ queryKey: ['modes'], queryFn: api.modes })
  return (
    <div className="fade-up">
      <Hero />
      <h2 style={{ margin: '10px 0 16px' }}>Engagement modes</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 14 }}>
        {(modes ?? []).map((m) => {
          const disabled = m.status !== 'available'
          const card = (
            <div
              className="card"
              style={{
                height: '100%',
                opacity: disabled ? 0.55 : 1,
                transition: 'border-color 0.15s, transform 0.15s',
                cursor: disabled ? 'default' : 'pointer',
              }}
              onMouseEnter={(e) => !disabled && (e.currentTarget.style.borderColor = 'var(--star-gold)')}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--hairline)')}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <div style={{ fontSize: 22, color: 'var(--star-gold)' }}>{MODE_ICONS[m.id] ?? '✦'}</div>
                {disabled && <span className="chip">coming soon</span>}
              </div>
              <h3 style={{ margin: '10px 0 6px' }}>{m.name}</h3>
              <p className="muted" style={{ fontSize: 13, margin: 0 }}>{m.description}</p>
            </div>
          )
          return disabled ? (
            <div key={m.id}>{card}</div>
          ) : (
            <Link key={m.id} to={`/new?mode=${m.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
              {card}
            </Link>
          )
        })}
      </div>
    </div>
  )
}
