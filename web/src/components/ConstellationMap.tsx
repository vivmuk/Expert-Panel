// The live panel rendered as a constellation: each expert is a star, each
// discipline a named constellation; stars ignite as insights complete.
import { useMemo, useState } from 'react'
import type { ExpertState } from '../api/useRun'
import type { Persona } from '../api/client'

const DISCIPLINE_COLORS = [
  'var(--series-1)', 'var(--series-2)', 'var(--series-3)',
  'var(--series-4)', 'var(--series-5)', 'var(--series-6)',
]

function mulberry32(seed: number) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

interface Star {
  index: number
  persona: Persona
  x: number
  y: number
  color: string
  discipline: string
}

export default function ConstellationMap({
  experts,
  onSelect,
}: {
  experts: Record<number, ExpertState>
  onSelect?: (expert: ExpertState) => void
}) {
  const [hover, setHover] = useState<Star | null>(null)

  const { stars, edges, labels } = useMemo(() => {
    const entries = Object.values(experts).filter((e) => e.persona)
    const disciplines = [...new Set(entries.map((e) => e.persona!.discipline ?? 'Panel'))]
    const stars: Star[] = []
    const edges: { x1: number; y1: number; x2: number; y2: number; color: string }[] = []
    const labels: { x: number; y: number; text: string; color: string }[] = []

    // Each discipline gets a cluster region on the canvas
    disciplines.forEach((disc, di) => {
      const members = entries.filter((e) => (e.persona!.discipline ?? 'Panel') === disc)
      const rand = mulberry32(di * 1337 + members.length)
      const cols = Math.ceil(Math.sqrt(disciplines.length))
      const row = Math.floor(di / cols)
      const col = di % cols
      const cx = 14 + (col + 0.5) * (72 / cols) + (rand() - 0.5) * 6
      const cy = 16 + (row + 0.5) * (64 / Math.ceil(disciplines.length / cols)) + (rand() - 0.5) * 5
      const color = DISCIPLINE_COLORS[di % DISCIPLINE_COLORS.length]
      const clusterStars: Star[] = members.map((m, mi) => {
        const angle = (mi / members.length) * Math.PI * 2 + rand() * 0.8
        const radius = 4 + rand() * 7 + members.length * 0.35
        return {
          index: m.index,
          persona: m.persona!,
          x: Math.max(4, Math.min(96, cx + Math.cos(angle) * radius * 1.35)),
          y: Math.max(8, Math.min(92, cy + Math.sin(angle) * radius)),
          color,
          discipline: disc,
        }
      })
      // connect cluster in a loose path (constellation lines)
      for (let i = 0; i < clusterStars.length - 1; i++) {
        edges.push({
          x1: clusterStars[i].x, y1: clusterStars[i].y,
          x2: clusterStars[i + 1].x, y2: clusterStars[i + 1].y,
          color,
        })
      }
      stars.push(...clusterStars)
      if (clusterStars.length) {
        labels.push({
          x: cx,
          y: Math.max(5, cy - (8 + members.length * 0.7)),
          text: disc,
          color,
        })
      }
    })
    return { stars, edges, labels }
  }, [experts])

  return (
    <div style={{ position: 'relative' }}>
      <svg viewBox="0 0 100 100" style={{ width: '100%', display: 'block', aspectRatio: '16/10' }} role="img" aria-label="Expert panel constellation map">
        {edges.map((e, i) => (
          <line key={i} x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2} stroke={e.color} strokeWidth={0.12} opacity={0.45} />
        ))}
        {labels.map((l, i) => (
          <text key={i} x={l.x} y={l.y} fill={l.color} fontSize={2.1} textAnchor="middle" opacity={0.9} style={{ fontFamily: 'var(--font-ui)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' as const }}>
            {l.text}
          </text>
        ))}
        {stars.map((s) => {
          const st = experts[s.index]?.status ?? 'pending'
          return (
            <g
              key={s.index}
              onMouseEnter={() => setHover(s)}
              onMouseLeave={() => setHover(null)}
              onClick={() => onSelect?.(experts[s.index])}
              style={{ cursor: 'pointer' }}
            >
              {/* generous hit target */}
              <circle cx={s.x} cy={s.y} r={3} fill="transparent" />
              {st === 'thinking' && (
                <circle cx={s.x} cy={s.y} r={1.6} fill="none" stroke={s.color} strokeWidth={0.15} style={{ transformOrigin: `${s.x}px ${s.y}px`, animation: 'pulse-ring 1.4s ease-out infinite' }} />
              )}
              <circle
                cx={s.x}
                cy={s.y}
                r={st === 'done' ? 1.05 : 0.65}
                fill={st === 'done' ? s.color : st === 'thinking' ? '#232a4d' : '#8d97c4'}
                opacity={st === 'pending' ? 0.75 : 1}
              />
              {st === 'done' && (
                <circle cx={s.x} cy={s.y} r={1.7} fill={s.color} opacity={0.18} />
              )}
            </g>
          )
        })}
      </svg>
      {hover && (
        <div
          style={{
            position: 'absolute',
            left: `${hover.x}%`,
            top: `${hover.y}%`,
            transform: `translate(${hover.x > 60 ? '-105%' : '8px'}, ${hover.y > 60 ? '-105%' : '8px'})`,
            background: 'var(--space-2)',
            border: '1px solid var(--hairline-strong)',
            borderRadius: 10,
            padding: '10px 12px',
            maxWidth: 280,
            pointerEvents: 'none',
            zIndex: 5,
            boxShadow: '0 8px 30px rgba(24,30,66,0.18)',
          }}
        >
          <div style={{ fontWeight: 700, fontSize: 13 }}>{hover.persona.name}</div>
          <div className="dim" style={{ fontSize: 12 }}>{hover.persona.title}</div>
          <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>{hover.persona.perspective}</div>
        </div>
      )}
    </div>
  )
}
