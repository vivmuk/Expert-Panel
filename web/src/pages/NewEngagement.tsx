import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api, type Estimate } from '../api/client'
import { getModelSettings } from '../lib/settings'
import CostBadge from '../components/CostBadge'

const COST_CONFIRM_THRESHOLD = 2.0

export default function NewEngagement() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { data: modes } = useQuery({ queryKey: ['modes'], queryFn: api.modes })

  const [modeId, setModeId] = useState(params.get('mode') ?? 'deep_dive')
  const [problem, setProblem] = useState('')
  const [urls, setUrls] = useState('')
  const [panelSize, setPanelSize] = useState<number | null>(null)
  const [pinned, setPinned] = useState('')
  const [excluded, setExcluded] = useState('')
  const [seed, setSeed] = useState('')
  const [webSearch, setWebSearch] = useState(true)
  const [xSearch, setXSearch] = useState(false)
  const [industry, setIndustry] = useState('')
  const [constraints, setConstraints] = useState('')
  const [estimate, setEstimate] = useState<Estimate | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const mode = useMemo(() => modes?.find((m) => m.id === modeId), [modes, modeId])
  const isWorkchart = mode?.flow === 'workchart'
  const size = panelSize ?? mode?.defaults.panelSize ?? 20

  useEffect(() => {
    if (!mode) return
    let live = true
    api.estimate({ mode: modeId, panelSize: size, models: getModelSettings() })
      .then((e) => live && setEstimate(e))
      .catch(() => live && setEstimate(null))
    return () => { live = false }
  }, [modeId, size, mode])

  const buildPayload = () => ({
    mode: modeId,
    input: {
      problem,
      urls: urls.split(/\s+/).filter(Boolean),
      industry: industry || undefined,
      constraints: constraints || undefined,
    },
    panel: {
      size,
      pinnedExperts: pinned.split('\n').map((s) => s.trim()).filter(Boolean),
      excludedDomains: excluded.split(',').map((s) => s.trim()).filter(Boolean),
      seedPerspectives: seed || undefined,
    },
    search: { web: webSearch, x: xSearch, scrapeUrls: true },
    models: getModelSettings(),
  })

  const launch = async () => {
    setSubmitting(true)
    setError('')
    try {
      const res = await api.createRun(buildPayload())
      navigate(`/run/${res.runId}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start run')
      setSubmitting(false)
      setConfirming(false)
    }
  }

  const onSubmit = () => {
    if (!problem.trim()) { setError('Describe the problem or process first.'); return }
    if ((estimate?.totalCostUsd ?? 0) >= COST_CONFIRM_THRESHOLD) setConfirming(true)
    else void launch()
  }

  return (
    <div className="fade-up" style={{ maxWidth: 780 }}>
      <h1 style={{ marginTop: 8 }}>New engagement</h1>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '18px 0' }}>
        {(modes ?? []).filter((m) => m.status === 'available').map((m) => (
          <button
            key={m.id}
            className="btn"
            onClick={() => setModeId(m.id)}
            style={modeId === m.id ? { borderColor: 'var(--star-gold)', color: 'var(--star-gold)' } : {}}
          >
            {m.name}
          </button>
        ))}
      </div>
      {mode && <p className="muted" style={{ marginTop: -6 }}>{mode.description}</p>}

      <div className="card" style={{ display: 'grid', gap: 16, marginTop: 12 }}>
        <div>
          <label className="label">{isWorkchart ? 'Describe the process' : 'The problem, decision, or plan'}</label>
          <textarea
            className="textarea"
            rows={5}
            value={problem}
            onChange={(e) => setProblem(e.target.value)}
            placeholder={
              isWorkchart
                ? 'e.g. Our claims intake process: customers email documents, an ops team keys them into the CRM, adjusters triage…'
                : 'e.g. Should we expand our B2B analytics product into the EU healthcare market next year?'
            }
          />
        </div>

        {isWorkchart ? (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div>
              <label className="label">Industry</label>
              <input className="input" value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="e.g. insurance" />
            </div>
            <div>
              <label className="label">Constraints</label>
              <input className="input" value={constraints} onChange={(e) => setConstraints(e.target.value)} placeholder="e.g. no customer data leaves the EU" />
            </div>
          </div>
        ) : (
          <>
            <div>
              <label className="label">Context URLs (scraped live — company site, competitors, docs)</label>
              <input className="input" value={urls} onChange={(e) => setUrls(e.target.value)} placeholder="https://yourcompany.com https://competitor.com" />
            </div>
            <div>
              <label className="label">Panel size — {size} experts</label>
              <input
                type="range"
                min={3}
                max={mode?.defaults.maxPanelSize ?? 100}
                value={size}
                onChange={(e) => setPanelSize(Number(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--indigo-deep)' }}
              />
              <div className="dim" style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                <span>3</span><span>{mode?.defaults.maxPanelSize ?? 100}</span>
              </div>
            </div>
            <details>
              <summary style={{ cursor: 'pointer', color: 'var(--ink-mid)', fontSize: 14 }}>Panel guardrails (optional)</summary>
              <div style={{ display: 'grid', gap: 14, marginTop: 14 }}>
                <div>
                  <label className="label">Must-have experts (one per line)</label>
                  <textarea className="textarea" rows={2} value={pinned} onChange={(e) => setPinned(e.target.value)} placeholder="CFO with private-equity background&#10;Former hospital procurement director" />
                </div>
                <div>
                  <label className="label">Excluded domains (comma-separated)</label>
                  <input className="input" value={excluded} onChange={(e) => setExcluded(e.target.value)} placeholder="crypto, quantum computing" />
                </div>
                <div>
                  <label className="label">Perspectives to represent</label>
                  <input className="input" value={seed} onChange={(e) => setSeed(e.target.value)} placeholder="e.g. emerging-market growth view; privacy-first counterweight" />
                </div>
              </div>
            </details>
            {mode?.flow === 'panel' && (
              <div style={{ display: 'flex', gap: 18 }}>
                <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 14 }}>
                  <input type="checkbox" checked={webSearch} onChange={(e) => setWebSearch(e.target.checked)} style={{ accentColor: 'var(--indigo-deep)' }} />
                  Live web search + citations
                </label>
                <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 14 }}>
                  <input type="checkbox" checked={xSearch} onChange={(e) => setXSearch(e.target.checked)} style={{ accentColor: 'var(--indigo-deep)' }} />
                  X / social sentiment
                </label>
              </div>
            )}
          </>
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: 14, borderTop: '1px solid var(--hairline)', paddingTop: 16 }}>
          <button className="btn btn-primary" onClick={onSubmit} disabled={submitting}>
            {submitting ? 'Launching…' : 'Launch engagement'}
          </button>
          {estimate && <CostBadge usd={estimate.totalCostUsd} label="estimated cost" />}
          {estimate && <span className="dim" style={{ fontSize: 12 }}>estimated · actuals tracked live</span>}
          {error && <span style={{ color: 'var(--status-critical)', fontSize: 13 }}>{error}</span>}
        </div>
      </div>

      {confirming && estimate && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(23,26,43,0.45)', display: 'grid', placeItems: 'center', zIndex: 20 }}>
          <div className="card" style={{ maxWidth: 460, background: 'var(--space-2)' }}>
            <h3 style={{ marginTop: 0 }}>Confirm spend</h3>
            <p className="muted">
              This {estimate.panelSize}-expert engagement is estimated at{' '}
              <strong style={{ color: 'var(--star-gold)' }}>${estimate.totalCostUsd.toFixed(2)}</strong> in Venice API usage.
              A circuit breaker aborts the run if spend exceeds 3× this estimate.
            </p>
            <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
              <tbody>
                {estimate.stages.map((s) => (
                  <tr key={s.stage}>
                    <td style={{ padding: '3px 0', color: 'var(--ink-mid)' }}>{s.stage}</td>
                    <td className="mono" style={{ textAlign: 'right' }}>{s.calls}×</td>
                    <td className="mono" style={{ textAlign: 'right', paddingLeft: 16 }}>${s.estCostUsd.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
              <button className="btn btn-primary" onClick={launch} disabled={submitting}>
                {submitting ? 'Launching…' : 'Proceed'}
              </button>
              <button className="btn" onClick={() => setConfirming(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
