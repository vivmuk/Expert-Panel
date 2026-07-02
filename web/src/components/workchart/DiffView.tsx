// Revision diff: renders the model-produced changeLog between chart revisions.
const TYPE_STYLES: Record<string, { color: string; icon: string }> = {
  added: { color: 'var(--status-good)', icon: '+' },
  removed: { color: 'var(--status-critical)', icon: '−' },
  modified: { color: 'var(--star-blue)', icon: '~' },
  reassigned: { color: 'var(--star-gold)', icon: '⇄' },
}

export default function DiffView({
  changeLog,
}: {
  changeLog: { stepRef: string; changeType: string; before: string; after: string; rationale: string }[]
}) {
  if (!changeLog?.length) return null
  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>What changed in this revision</h3>
      <div style={{ display: 'grid', gap: 10 }}>
        {changeLog.map((c, i) => {
          const s = TYPE_STYLES[c.changeType] ?? TYPE_STYLES.modified
          return (
            <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'start' }}>
              <span
                className="mono"
                style={{
                  color: s.color,
                  border: `1px solid ${s.color}`,
                  borderRadius: 6,
                  width: 22,
                  height: 22,
                  display: 'grid',
                  placeItems: 'center',
                  flexShrink: 0,
                  fontWeight: 700,
                }}
              >
                {s.icon}
              </span>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>
                  {c.stepRef} <span className="dim" style={{ fontWeight: 400 }}>· {c.changeType}</span>
                </div>
                {c.changeType !== 'added' && <div className="dim" style={{ fontSize: 13, textDecoration: 'line-through' }}>{c.before}</div>}
                {c.changeType !== 'removed' && <div className="muted" style={{ fontSize: 13 }}>{c.after}</div>}
                <div className="dim" style={{ fontSize: 12, fontStyle: 'italic' }}>{c.rationale}</div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
