// Custom line iconography per engagement mode, drawn on the mode's accent color.
export const MODE_ACCENTS: Record<string, string> = {
  deep_dive: '#2a5fc4',
  red_team: '#c02f2f',
  quick_pulse: '#0e9f8a',
  board_meeting: '#7c3aed',
  workchart: '#d9932c',
  scenario_planning: '#0284c7',
  due_diligence: '#4a3aa7',
  ai_opportunity_scan: '#ca8a04',
  digital_twin: '#0891b2',
}

const PATHS: Record<string, React.ReactNode> = {
  deep_dive: (
    <>
      {/* telescope */}
      <line x1="6" y1="26" x2="24" y2="8" strokeWidth="3.4" />
      <line x1="22" y1="6" x2="27" y2="11" strokeWidth="3.4" />
      <line x1="12" y1="20" x2="8" y2="28" />
      <line x1="12" y1="20" x2="16" y2="28" />
      <circle cx="26" cy="22" r="1.4" fill="currentColor" stroke="none" />
      <circle cx="29" cy="17" r="1" fill="currentColor" stroke="none" />
    </>
  ),
  red_team: (
    <>
      {/* crossed swords */}
      <line x1="7" y1="7" x2="24" y2="24" />
      <line x1="25" y1="7" x2="8" y2="24" />
      <line x1="22" y1="22" x2="27" y2="27" strokeWidth="3.2" />
      <line x1="10" y1="22" x2="5" y2="27" strokeWidth="3.2" />
      <line x1="6" y1="10" x2="10" y2="6" strokeWidth="3.2" />
      <line x1="26" y1="10" x2="22" y2="6" strokeWidth="3.2" />
    </>
  ),
  quick_pulse: (
    <>
      {/* pulse wave */}
      <polyline points="4,17 10,17 13,8 18,26 21,17 28,17" strokeWidth="2.4" fill="none" />
      <circle cx="28" cy="17" r="1.6" fill="currentColor" stroke="none" />
    </>
  ),
  board_meeting: (
    <>
      {/* round table + seats */}
      <circle cx="16" cy="17" r="7" />
      <circle cx="16" cy="5.5" r="2.2" fill="currentColor" stroke="none" />
      <circle cx="27" cy="13" r="2.2" fill="currentColor" stroke="none" />
      <circle cx="23.5" cy="26" r="2.2" fill="currentColor" stroke="none" />
      <circle cx="8.5" cy="26" r="2.2" fill="currentColor" stroke="none" />
      <circle cx="5" cy="13" r="2.2" fill="currentColor" stroke="none" />
    </>
  ),
  workchart: (
    <>
      {/* branching flow */}
      <line x1="16" y1="4" x2="16" y2="12" strokeWidth="2.6" />
      <path d="M16 12 C 16 18, 8 16, 8 24" fill="none" strokeWidth="2.6" />
      <path d="M16 12 C 16 18, 24 16, 24 24" fill="none" strokeWidth="2.6" />
      <circle cx="16" cy="4" r="2.4" fill="currentColor" stroke="none" />
      <rect x="5" y="24" width="6" height="5" rx="1.5" fill="currentColor" stroke="none" />
      <rect x="21" y="24" width="6" height="5" rx="1.5" fill="currentColor" stroke="none" />
    </>
  ),
  scenario_planning: (
    <>
      <line x1="6" y1="26" x2="16" y2="14" />
      <line x1="16" y1="14" x2="12" y2="5" />
      <line x1="16" y1="14" x2="22" y2="6" />
      <line x1="16" y1="14" x2="27" y2="12" />
      <circle cx="12" cy="5" r="2" fill="currentColor" stroke="none" />
      <circle cx="22" cy="6" r="2" fill="currentColor" stroke="none" />
      <circle cx="27" cy="12" r="2" fill="currentColor" stroke="none" />
    </>
  ),
  due_diligence: (
    <>
      <circle cx="14" cy="14" r="8" />
      <line x1="20" y1="20" x2="27" y2="27" strokeWidth="3" />
    </>
  ),
  ai_opportunity_scan: (
    <>
      <polygon points="18,3 8,18 15,18 13,29 24,13 17,13" fill="currentColor" stroke="none" />
    </>
  ),
  digital_twin: (
    <>
      <circle cx="11" cy="16" r="6.5" />
      <circle cx="21" cy="16" r="6.5" strokeDasharray="3 3" />
    </>
  ),
}

export default function ModeIcon({ mode, size = 30 }: { mode: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      style={{ color: MODE_ACCENTS[mode] ?? 'var(--indigo-deep)' }}
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      fill="none"
      aria-hidden
    >
      {PATHS[mode] ?? <circle cx="16" cy="16" r="8" />}
    </svg>
  )
}
