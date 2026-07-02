// Stage progress rail for a live run.
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
              className="chip"
              style={{
                borderColor: done ? 'var(--star-gold)' : active ? 'var(--star-blue)' : 'var(--hairline)',
                color: done ? 'var(--star-gold)' : active ? 'var(--ink-hi)' : 'var(--ink-low)',
                background: active ? 'var(--space-3)' : 'var(--space-1)',
              }}
            >
              {done ? '✦' : active ? '◌' : '·'} {STAGE_LABELS[stage] ?? stage}
            </div>
            {i < stages.length - 1 && <span className="dim">→</span>}
          </div>
        )
      })}
    </div>
  )
}
