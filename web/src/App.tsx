import { NavLink, Route, Routes } from 'react-router-dom'
import Starfield from './components/Starfield'
import Landing from './pages/Landing'
import NewEngagement from './pages/NewEngagement'
import RunView from './pages/RunView'
import Engagements from './pages/Engagements'
import EngagementDetail from './pages/EngagementDetail'
import Settings from './pages/Settings'

function SideNav() {
  const item = (to: string, label: string, icon: string) => (
    <NavLink
      key={to}
      to={to}
      style={({ isActive }) => ({
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '10px 14px',
        borderRadius: 10,
        color: isActive ? 'var(--ink-hi)' : 'var(--ink-mid)',
        background: isActive ? 'var(--space-3)' : 'transparent',
        fontWeight: isActive ? 600 : 500,
        fontSize: 14,
        textDecoration: 'none',
      })}
    >
      <span style={{ color: 'var(--star-gold)', width: 16, textAlign: 'center' }}>{icon}</span>
      {label}
    </NavLink>
  )
  return (
    <nav
      style={{
        width: 220,
        flexShrink: 0,
        padding: '20px 12px',
        borderRight: '1px solid var(--hairline)',
        background: 'rgba(255, 255, 255, 0.85)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        position: 'sticky',
        top: 0,
        height: '100vh',
        zIndex: 2,
      }}
    >
      <NavLink to="/" style={{ textDecoration: 'none', color: 'var(--ink-hi)', margin: '4px 10px 20px' }}>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, fontWeight: 600, color: 'var(--indigo-deep)' }}>
          <span style={{ color: 'var(--star-gold)' }}>✦</span> Constellation
        </div>
        <div className="dim" style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          AI Consulting Platform
        </div>
      </NavLink>
      {item('/new', 'New Engagement', '✧')}
      {item('/engagements', 'Engagements', '☰')}
      {item('/settings', 'Settings', '⚙')}
      <div style={{ flex: 1 }} />
      <div className="dim" style={{ fontSize: 11, padding: '0 12px 8px' }}>
        Powered by Venice AI
      </div>
    </nav>
  )
}

export default function App() {
  return (
    <div style={{ display: 'flex', minHeight: '100vh', position: 'relative' }}>
      <Starfield />
      <SideNav />
      <main style={{ flex: 1, padding: '28px 36px', position: 'relative', zIndex: 1, maxWidth: 1240, width: '100%', margin: '0 auto' }}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/new" element={<NewEngagement />} />
          <Route path="/run/:runId" element={<RunView />} />
          <Route path="/engagements" element={<Engagements />} />
          <Route path="/e/:id" element={<EngagementDetail />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  )
}
