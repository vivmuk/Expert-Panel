// Live activity feed: a running log of everything the engagement is doing.
import type { ActivityItem } from '../api/useRun'

const TONE_COLORS: Record<string, string> = {
  info: 'var(--indigo)',
  good: 'var(--status-good)',
  search: 'var(--teal)',
  expert: 'var(--star-gold)',
}

function ago(at: number, now: number) {
  const s = Math.max(0, Math.round((now - at) / 1000))
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

export default function ActivityFeed({ items, live, now }: { items: ActivityItem[]; live: boolean; now: number }) {
  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px', borderBottom: '1px solid var(--hairline)' }}>
        {live && <span style={{ width: 8, height: 8, borderRadius: 999, background: 'var(--status-good)', display: 'inline-block', animation: 'twinkle 1.4s ease-in-out infinite' }} />}
        <strong style={{ fontSize: 13 }}>Live activity</strong>
        <span className="dim" style={{ fontSize: 12, marginLeft: 'auto' }}>{items.length} events</span>
      </div>
      <div style={{ maxHeight: 320, overflowY: 'auto' }}>
        {items.length === 0 && <div className="dim" style={{ padding: 16, fontSize: 13 }}>Waiting for the first event…</div>}
        {items.map((item, i) => (
          <div
            key={item.id}
            className={i === 0 ? 'fade-up' : ''}
            style={{ display: 'flex', gap: 10, padding: '9px 16px', borderBottom: '1px solid var(--hairline)', alignItems: 'flex-start' }}
          >
            <span
              style={{
                flexShrink: 0, width: 22, height: 22, borderRadius: 7, display: 'grid', placeItems: 'center',
                fontSize: 12, color: TONE_COLORS[item.tone], border: `1px solid ${TONE_COLORS[item.tone]}`,
                background: i === 0 ? 'var(--space-1)' : 'transparent',
              }}
            >
              {item.icon}
            </span>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: i === 0 ? 600 : 500 }}>{item.text}</div>
              {item.detail && <div className="dim" style={{ fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.detail}</div>}
            </div>
            <span className="dim mono" style={{ fontSize: 11, flexShrink: 0 }}>{ago(item.at, now)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
