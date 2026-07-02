import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

const MODE_NAMES: Record<string, string> = {
  deep_dive: 'Deep Dive',
  red_team: 'Red Team',
  quick_pulse: 'Quick Pulse',
  board_meeting: 'Board Meeting',
  workchart: 'Work Chart',
}

export default function Engagements() {
  const [modeFilter, setModeFilter] = useState('')
  const [search, setSearch] = useState('')
  const queryClient = useQueryClient()
  const { data: engagements, isLoading } = useQuery({
    queryKey: ['engagements', modeFilter, search],
    queryFn: () => api.engagements({ mode: modeFilter || undefined, q: search || undefined }),
  })

  const remove = async (id: number) => {
    if (!confirm('Delete this engagement and all its revisions?')) return
    await api.deleteEngagement(id)
    queryClient.invalidateQueries({ queryKey: ['engagements'] })
  }

  return (
    <div className="fade-up">
      <h1 style={{ marginTop: 8 }}>Engagements</h1>
      <div style={{ display: 'flex', gap: 10, margin: '16px 0', flexWrap: 'wrap' }}>
        <input
          className="input"
          style={{ maxWidth: 320 }}
          placeholder="Search titles…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select className="select" style={{ maxWidth: 200 }} value={modeFilter} onChange={(e) => setModeFilter(e.target.value)}>
          <option value="">All modes</option>
          {Object.entries(MODE_NAMES).map(([id, name]) => (
            <option key={id} value={id}>{name}</option>
          ))}
        </select>
      </div>

      {isLoading && <p className="dim">Loading…</p>}
      {!isLoading && !engagements?.length && (
        <div className="card" style={{ textAlign: 'center', padding: 48 }}>
          <div style={{ fontSize: 30, color: 'var(--star-gold)' }}>✦</div>
          <p className="muted">No engagements yet. Launch your first from <Link to="/new">New Engagement</Link>.</p>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 14 }}>
        {(engagements ?? []).map((e) => (
          <div key={e.id} className="card" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <span className="chip">{MODE_NAMES[e.mode] ?? e.mode}</span>
              <span
                className="chip"
                style={{
                  color: e.status === 'completed' ? 'var(--status-good)' : e.status === 'failed' ? 'var(--status-critical)' : 'var(--ink-mid)',
                }}
              >
                {e.status}
              </span>
            </div>
            <Link to={`/e/${e.id}`} style={{ color: 'var(--ink-hi)', fontWeight: 600, fontSize: 15 }}>
              {e.title}
            </Link>
            <div className="dim" style={{ fontSize: 12 }}>
              {new Date(e.updated_at + 'Z').toLocaleString()} · {e.revision_count} revision{e.revision_count === 1 ? '' : 's'} ·{' '}
              <span className="mono">${(e.total_cost_usd ?? 0).toFixed(2)}</span>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 'auto' }}>
              <Link to={`/e/${e.id}`} className="btn" style={{ padding: '5px 12px', fontSize: 13 }}>Open</Link>
              <button className="btn btn-danger" style={{ padding: '5px 12px', fontSize: 13 }} onClick={() => remove(e.id)}>Delete</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
