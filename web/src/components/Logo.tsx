// AI Partner logo: two stars — the client and the AI — joined in one
// constellation, held in an orbit ring.
export default function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-label="AI Partner logo" role="img">
      <defs>
        <linearGradient id="lg-ring" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#2a5fc4" />
          <stop offset="100%" stopColor="#14b8a6" />
        </linearGradient>
        <linearGradient id="lg-star" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#f0c04a" />
          <stop offset="100%" stopColor="#d9932c" />
        </linearGradient>
      </defs>
      <circle cx="24" cy="24" r="21" fill="none" stroke="url(#lg-ring)" strokeWidth="2.4" strokeDasharray="92 40" strokeLinecap="round" />
      <line x1="16" y1="29" x2="31" y2="17" stroke="#2a5fc4" strokeWidth="1.6" opacity="0.7" />
      {/* large star — the partner */}
      <path d="M31 9.5 L33.2 14.8 L38.5 17 L33.2 19.2 L31 24.5 L28.8 19.2 L23.5 17 L28.8 14.8 Z" fill="url(#lg-star)" />
      {/* small star — you */}
      <circle cx="16" cy="29" r="3.4" fill="#232a4d" />
      <circle cx="34" cy="33" r="1.7" fill="#14b8a6" />
    </svg>
  )
}
