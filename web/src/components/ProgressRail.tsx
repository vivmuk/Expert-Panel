// Stage progress rail for a live run: completed stages seal in gold, the
// active stage flows with the brand gradient.
const STAGE_LABELS: Record<string, string> = {
  architect: 'Panel Architect',
  personas: 'Casting Experts',
  market: 'Market Intelligence',
  insights: 'Expert Analysis',
  synthesis: 'Synthesis',
  debate: 'Board Debate',
  minutes: 'Minutes & Vote',
  draft: 'Drafting Chart',
  clarify: 'Clarifications',
  refine: 'Refining',
  revise: 'Revising',
  breakthrough: 'Breakthroughs',
  workchart: 'Work Chart',
}

export default function ProgressRail({
  stages,
  currentStage,
  completedStages,
}: {
  stages: string[]
  currentStage?: string
  completedStages: string[]
}) {
  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
      {stages.map((stage, i) => {
        const done = completedStages.includes(stage)
        const active = currentStage === stage && !done
        return (
          <div key={stage} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div
              className={`chip ${active ? 'stage-live' : ''}`}
              style={{
                borderColor: done ? 'var(--star-gold-bright)' : active ? 'var(--indigo)' : 'var(--hairline)',
                color: done ? 'var(--star-gold)' : active ? 'var(--indigo-deep)' : 'var(--ink-low)',
                fontWeight: active || done ? 600 : 400,
                background: done ? 'rgba(232, 182, 76, 0.10)' : active ? undefined : 'var(--space-1)',
                padding: '5px 12px',
              }}
            >
              {done ? '✦' : active ? <span className="orbit" style={{ display: 'inline-block', fontSize: 11 }}>◐</span> : '·'}{' '}
              {STAGE_LABELS[stage] ?? stage}
            </div>
            {i < stages.length - 1 && (
              <span style={{ color: done ? 'var(--star-gold-bright)' : 'var(--ink-low)' }}>→</span>
            )}
          </div>
        )
      })}
    </div>
  )
}
