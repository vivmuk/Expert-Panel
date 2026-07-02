import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { getModelSettings, setModelSettings, type ModelSettings } from '../lib/settings'

const ROLES: { id: keyof ModelSettings; name: string; hint: string }[] = [
  { id: 'architect', name: 'Panel Architect', hint: 'designs the panel blueprint — use the strongest reasoning model' },
  { id: 'persona_writer', name: 'Persona Writer', hint: 'casts the experts' },
  { id: 'expert', name: 'Expert Analysis', hint: 'runs once per expert — quality vs cost tradeoff lives here' },
  { id: 'market_agent', name: 'Market Intelligence', hint: 'needs web search support; X search needs a capable model' },
  { id: 'synthesizer', name: 'Synthesis', hint: 'writes the final report — large context helps' },
  { id: 'workchart', name: 'Work Chart', hint: 'generates and revises process charts' },
  { id: 'breakthrough', name: 'Breakthrough Thinking', hint: 'type-2 opportunities — use a thinking model' },
  { id: 'pulse', name: 'Quick Pulse', hint: 'runs 50-100×; a small fast model keeps pulses cheap' },
]

export default function Settings() {
  const { data: models, isError } = useQuery({ queryKey: ['models'], queryFn: api.models })
  const [settings, setSettings] = useState<ModelSettings>(getModelSettings())

  const update = (role: keyof ModelSettings, value: string) => {
    const next = { ...settings, [role]: value || undefined }
    setSettings(next)
    setModelSettings(next)
  }

  return (
    <div className="fade-up" style={{ maxWidth: 780 }}>
      <h1 style={{ marginTop: 8 }}>Settings</h1>
      <p className="muted">
        Models are discovered live from the Venice API — new releases appear here automatically.
        Leave a role on “server default” to let the platform pick a capable model.
      </p>
      {isError && (
        <div className="card" style={{ borderColor: 'var(--status-serious)', margin: '12px 0' }}>
          Could not reach the Venice models API. Check that VENICE_API_KEY is configured on the server.
        </div>
      )}
      <div style={{ display: 'grid', gap: 12, marginTop: 16 }}>
        {ROLES.map((role) => (
          <div className="card" key={role.id} style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 220px' }}>
              <div style={{ fontWeight: 600 }}>{role.name}</div>
              <div className="dim" style={{ fontSize: 12 }}>{role.hint}</div>
            </div>
            <select
              className="select"
              style={{ flex: '1 1 260px' }}
              value={settings[role.id] ?? ''}
              onChange={(e) => update(role.id, e.target.value)}
            >
              <option value="">server default</option>
              {(models ?? [])
                .filter((m) => role.id !== 'market_agent' || m.supportsWebSearch)
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                    {m.pricing.inputPerMtok != null ? ` — $${m.pricing.inputPerMtok}/$${m.pricing.outputPerMtok} per Mtok` : ''}
                    {m.supportsXSearch ? ' · X search' : ''}
                  </option>
                ))}
            </select>
          </div>
        ))}
      </div>
    </div>
  )
}
