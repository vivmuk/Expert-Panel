export default function CostBadge({ usd, label = 'spend' }: { usd: number; label?: string }) {
  return (
    <span className="chip mono" title={`Estimated ${label} in USD`}>
      <span style={{ color: 'var(--star-gold)' }}>◈</span> ${usd < 0.01 && usd > 0 ? usd.toFixed(4) : usd.toFixed(2)}
    </span>
  )
}
