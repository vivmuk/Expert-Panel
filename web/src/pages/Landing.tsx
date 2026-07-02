import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { useBranding } from '../api/useBranding'
import ModeIcon, { MODE_ACCENTS } from '../components/ModeIcon'

function Hero({ heroUrl }: { heroUrl: string | null }) {
  return (
    <header
      className="card"
      style={{
        padding: '52px 48px',
        marginTop: 10,
        position: 'relative',
        overflow: 'hidden',
        border: 'none',
        boxShadow: 'var(--shadow-2)',
      }}
    >
      {heroUrl ? (
        <div
          aria-hidden
          style={{
            position: 'absolute',
            inset: 0,
            backgroundImage: `linear-gradient(90deg, rgba(255,255,255,0.96) 34%, rgba(255,255,255,0.55) 62%, rgba(255,255,255,0.15)), url(${heroUrl})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center right',
          }}
        />
      ) : (
        <svg viewBox="0 0 400 160" style={{ position: 'absolute', right: -10, top: 0, width: 460, opacity: 0.9 }} aria-hidden>
          <g stroke="#8d97c4" strokeWidth="0.7">
            <line x1="40" y1="120" x2="120" y2="45" /><line x1="120" y1="45" x2="210" y2="85" />
            <line x1="210" y1="85" x2="290" y2="30" /><line x1="290" y1="30" x2="360" y2="95" />
            <line x1="120" y1="45" x2="180" y2="130" /><line x1="210" y1="85" x2="180" y2="130" />
          </g>
          {[[40, 120, '#d9932c'], [120, 45, '#232a4d'], [210, 85, '#2a5fc4'], [290, 30, '#0e9f8a'], [360, 95, '#d9932c'], [180, 130, '#4a3aa7']].map(([x, y, c], i) => (
            <circle key={i} cx={x as number} cy={y as number} r={i % 2 ? 4 : 2.8} fill={c as string}
              style={{ animation: `twinkle ${3 + i}s ease-in-out infinite` }} />
          ))}
        </svg>
      )}
      <div style={{ position: 'relative', maxWidth: 560 }}>
        <div className="chip" style={{ background: '#fff', marginBottom: 14 }}>
          <span style={{ color: 'var(--teal)', fontWeight: 700 }}>●</span> Your consulting firm, on demand
        </div>
        <h1 style={{ margin: 0 }}>
          Every expert you need.<br />
          <span className="gradient-text">One constellation.</span>
        </h1>
        <p className="muted" style={{ fontSize: 17, marginTop: 16 }}>
          AI Partner assembles panels of up to 100 bespoke expert minds, grounded in live web and X
          intelligence — deep dives, red teams, board debates, and agent-era work charts, in minutes.
        </p>
        <div style={{ display: 'flex', gap: 12, marginTop: 26 }}>
          <Link to="/new" className="btn btn-primary" style={{ fontSize: 15, padding: '12px 24px' }}>
            Start an engagement →
          </Link>
          <Link to="/engagements" className="btn" style={{ padding: '12px 20px' }}>Browse past work</Link>
        </div>
      </div>
    </header>
  )
}

export default function Landing() {
  const { data: modes } = useQuery({ queryKey: ['modes'], queryFn: api.modes })
  const branding = useBranding()

  return (
    <div className="fade-up">
      <Hero heroUrl={branding.hero?.url ?? null} />
      <h2 style={{ margin: '34px 0 16px' }}>Engagement modes</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(270px, 1fr))', gap: 16 }}>
        {(modes ?? []).map((m) => {
          const disabled = m.status !== 'available'
          const accent = MODE_ACCENTS[m.id] ?? 'var(--indigo)'
          const art = branding[m.id]?.url
          const card = (
            <div
              className={`card ${disabled ? '' : 'card-hover'}`}
              style={{
                height: '100%',
                opacity: disabled ? 0.6 : 1,
                cursor: disabled ? 'default' : 'pointer',
                borderTop: `3px solid ${accent}`,
                overflow: 'hidden',
                position: 'relative',
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              {art && (
                <div
                  aria-hidden
                  style={{
                    height: 110,
                    margin: '-20px -20px 14px',
                    backgroundImage: `url(${art})`,
                    backgroundSize: 'cover',
                    backgroundPosition: 'center',
                    borderBottom: '1px solid var(--hairline)',
                  }}
                />
              )}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <ModeIcon mode={m.id} />
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
