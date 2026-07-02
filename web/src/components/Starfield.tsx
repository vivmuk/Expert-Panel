// Procedural starfield backdrop: deterministic, lightweight, pure SVG.
import { useMemo } from 'react'

function mulberry32(seed: number) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export default function Starfield({ density = 110, seed = 7 }: { density?: number; seed?: number }) {
  const stars = useMemo(() => {
    const rand = mulberry32(seed)
    return Array.from({ length: density }, (_, i) => ({
      id: i,
      x: rand() * 100,
      y: rand() * 100,
      r: 0.4 + rand() * 1.1,
      delay: rand() * 6,
      dur: 3 + rand() * 5,
      warm: rand() > 0.82,
    }))
  }, [density, seed])

  return (
    <svg
      aria-hidden
      style={{ position: 'fixed', inset: 0, width: '100%', height: '100%', zIndex: 0, pointerEvents: 'none' }}
      preserveAspectRatio="xMidYMid slice"
      viewBox="0 0 100 100"
    >
      {stars.map((s) => (
        <circle
          key={s.id}
          cx={s.x}
          cy={s.y}
          r={s.r * 0.14}
          fill={s.warm ? '#d9a63c' : '#8d97c4'}
          style={{ animation: `twinkle ${s.dur}s ease-in-out ${s.delay}s infinite`, opacity: 0.35 }}
        />
      ))}
    </svg>
  )
}
