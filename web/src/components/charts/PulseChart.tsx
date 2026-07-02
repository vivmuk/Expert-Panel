// Quick Pulse results: stance distribution on a diverging scale + hero stats.
import BarChart from './BarChart'

const STANCE_LABELS = ['Strongly oppose', 'Oppose', 'Neutral', 'Support', 'Strongly support']
const STANCE_COLORS = ['var(--div-neg-2)', 'var(--div-neg-1)', 'var(--div-mid)', 'var(--div-pos-1)', 'var(--div-pos-2)']

export interface PulseAggregates {
  count: number
  mean_stance: number
  distribution: Record<string, number>
  support_pct: number
  oppose_pct: number
  by_discipline: Record<string, number>
  top_concerns: string[]
}

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card" style={{ padding: '14px 18px', flex: 1, minWidth: 130 }}>
      <div className="label">{label}</div>
      <div style={{ fontSize: 30, fontWeight: 700 }}>{value}</div>
      {sub && <div className="dim" style={{ fontSize: 12 }}>{sub}</div>}
    </div>
  )
}

export default function PulseChart({ aggregates }: { aggregates: PulseAggregates }) {
  const dist = aggregates.distribution ?? {}
  const bars = STANCE_LABELS.map((label, i) => ({
    label,
    value: dist[String(i + 1)] ?? 0,
    color: STANCE_COLORS[i],
    detail: `${dist[String(i + 1)] ?? 0} of ${aggregates.count} experts`,
  }))
  const disciplineBars = Object.entries(aggregates.by_discipline ?? {}).map(([d, v]) => ({
    label: d,
    value: v,
    color: v >= 3 ? 'var(--div-pos-2)' : 'var(--div-neg-2)',
    detail: `mean stance ${v.toFixed(2)} / 5`,
  }))

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <Tile label="Panel size" value={String(aggregates.count)} />
        <Tile label="Mean stance" value={aggregates.mean_stance?.toFixed(2) ?? '—'} sub="1 = oppose · 5 = support" />
        <Tile label="Support" value={`${aggregates.support_pct}%`} sub="stance 4-5" />
        <Tile label="Oppose" value={`${aggregates.oppose_pct}%`} sub="stance 1-2" />
      </div>
      <div className="card">
        <h3 style={{ margin: '0 0 12px' }}>Stance distribution</h3>
        <BarChart bars={bars} ariaLabel="Distribution of expert stances from strongly oppose to strongly support" />
      </div>
      {disciplineBars.length > 1 && (
        <div className="card">
          <h3 style={{ margin: '0 0 12px' }}>Mean stance by discipline</h3>
          <BarChart bars={disciplineBars} maxValue={5} format={(v) => v.toFixed(2)} ariaLabel="Mean stance per discipline on a 1 to 5 scale" />
        </div>
      )}
    </div>
  )
}
