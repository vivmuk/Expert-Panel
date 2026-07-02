// Minimal spec-compliant horizontal bar chart: thin marks, rounded data ends,
// hairline grid, per-mark hover tooltip, direct value labels.
import { useState } from 'react'

export interface Bar {
  label: string
  value: number
  color: string
  detail?: string
}

export default function BarChart({
  bars,
  format = (v: number) => String(v),
  maxValue,
  ariaLabel,
}: {
  bars: Bar[]
  format?: (v: number) => string
  maxValue?: number
  ariaLabel: string
}) {
  const [hover, setHover] = useState<number | null>(null)
  const max = maxValue ?? Math.max(...bars.map((b) => b.value), 1)
  const rowH = 30

  return (
    <div role="img" aria-label={ariaLabel} style={{ position: 'relative' }}>
      <svg width="100%" height={bars.length * rowH} style={{ display: 'block' }}>
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <line
            key={f}
            x1={`${28 + f * 58}%`}
            x2={`${28 + f * 58}%`}
            y1={0}
            y2={bars.length * rowH}
            stroke="var(--hairline)"
            strokeWidth={1}
          />
        ))}
        {bars.map((b, i) => {
          const w = (b.value / max) * 58
          const y = i * rowH + rowH / 2
          return (
            <g
              key={b.label}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
            >
              <rect x="0" y={i * rowH} width="100%" height={rowH} fill={hover === i ? 'rgba(214,222,255,0.04)' : 'transparent'} />
              <text x="0" y={y + 4} fill="var(--ink-mid)" fontSize={12} style={{ fontFamily: 'var(--font-ui)' }}>
                {b.label.length > 22 ? b.label.slice(0, 21) + '…' : b.label}
              </text>
              <rect
                x="28%"
                y={y - 6}
                width={`${Math.max(w, 0.5)}%`}
                height={12}
                rx={4}
                fill={b.color}
              />
              <text
                x={`${28 + Math.max(w, 0.5) + 1.2}%`}
                y={y + 4}
                fill="var(--ink-hi)"
                fontSize={12}
                className="mono"
                style={{ fontFamily: 'var(--font-ui)', fontVariantNumeric: 'tabular-nums' }}
              >
                {format(b.value)}
              </text>
            </g>
          )
        })}
      </svg>
      {hover !== null && bars[hover]?.detail && (
        <div
          style={{
            position: 'absolute',
            top: hover * rowH - 4,
            right: 0,
            background: 'var(--space-3)',
            border: '1px solid var(--hairline-strong)',
            borderRadius: 8,
            padding: '6px 10px',
            fontSize: 12,
            pointerEvents: 'none',
            zIndex: 4,
          }}
        >
          {bars[hover].detail}
        </div>
      )}
    </div>
  )
}
