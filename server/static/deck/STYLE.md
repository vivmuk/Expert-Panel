# Constellation Paper

The presentation style for **{{COMPANY}}** (rendered "AI Partner"). It comes from two places in Vivek Mukhatyar's work:

- the base look of [harness-engineering](https://github.com/vivmuk/harness-engineering) (`app/globals.css`, "viv-design v2 polish"): off-white chroma-0 paper, cobalt accent, big type, bento layout
- interactive components from **vivDesign**, <https://designviv.up.railway.app> ([catalog.json](https://designviv.up.railway.app/catalog.json), repo [vivmuk/DesignSite](https://github.com/vivmuk/DesignSite), specs in `src/data/interactiveAddons.ts`)

The name comes from Expert-Panel's "star chart" UI, where each expert on a panel is drawn as a star. In this style, a cobalt point means an expert, an agent or a step that changed owner.

## Tokens

| Token | Value | Use |
|---|---|---|
| `--paper` | `#FAFAF7` | page background |
| `--paper-2` | `#F0F0EC` | default card |
| `--paper-3` | `#E6E6E0` | "Today" layer, inactive states |
| `--ink` | `#0F0F0F` | text, ink cards |
| `--ink-2` | `#525258` | secondary text |
| `--ink-3` | `#8A8A92` | kickers, captions |
| `--rule` / `--rule-2` | `rgba(15,15,15,.12)` / `.22` | hairlines, card borders |
| `--cobalt` | `#0033CC` | the one accent: emphasis, AI Agent owner, progress |
| `--cobalt-wash` | `#E8EDFB` | soft cobalt card |
| `--magenta` | `#FF2E93` | Hybrid owner, strike-through, ~6% particle sparks |
| `--acid` | `#F5FF40` | "illustrative estimate" labels, fill-in placeholders, numbers on dark cards |
| `--amber` | `#D4760A` | Digital Twin owner |
| `--r` | `14px` | card radius |
| `--ease-out` | `cubic-bezier(.23,1,.32,1)` | every transition |

### Owner colors (Work Chart)

| Owner | Tag |
|---|---|
| Human | ink outline |
| AI Agent | solid cobalt |
| Hybrid | magenta outline |
| Digital Twin | solid amber |
| No owner | dashed grey |

## Type

System stack, no web fonts, so the deck works offline: `Inter, Geist, Helvetica Neue, Arial, system-ui` for text and `JetBrains Mono, Geist Mono, ui-monospace` for labels.

| Role | Size | Weight / tracking |
|---|---|---|
| Hero statement | `clamp(34px, 6vw, 92px)` | 850, -0.035em |
| Slide title (h2) | `clamp(26px, 3.6vw, 52px)` | 800, -0.025em, max 24ch, second clause in cobalt |
| Card title (h3) | `clamp(17px, 1.6vw, 22px)` | 800, -0.01em |
| Body | `clamp(14px, 1.15vw, 17px)` | 400, line-height 1.45 |
| Kicker / label | `clamp(11px, .9vw, 13px)` mono | uppercase, +0.08em |
| Stat numeral | `clamp(40px, 6vw, 96px)` | 850, -0.04em |

## Layout

- One slide fills the viewport. Order inside a slide: kicker (slide number in cobalt, then topic, then any honesty label), title, then a bento grid of cards.
- Bento: unequal columns (for example `1.6fr / 1fr`, `.8fr / 1.1fr / 1.1fr`). Avoid three equal cards unless the content really is three parallel items.
- Card fills, at most one of each per slide: `ink` (black), `cobalt`, `wash`, then default `paper-2` for the rest.
- Chrome: a 4px cobalt progress bar at the top, a brand dot and name top-left, and dot navigation with a counter at the bottom.
- Below 820px, grids stack to one column, slides scroll vertically, secondary paragraphs (`.hide-m`) drop out, and the nav sits in a solid bottom bar.

## Components (re-implemented natively from vivDesign)

All five are vanilla JS and canvas, with no iframes and no libraries. Each runs only while its slide is active.

| vivDesign component | Permalink | Used on | What it does here |
|---|---|---|---|
| Text to Particles | `#/interactive/text-particles` | 01 Title | The company name is sampled into cobalt particles. The pointer repels them and a click scatters them before they reassemble. It rebuilds from `COMPANY`, so a rename re-renders it. |
| Magnetic Dots | `#/interactive/magnetic-dots` | 02 Problem | A background grid that leans toward the pointer and springs back. A ghost pointer drifts when idle. |
| Before / After Slider | `#/interactive/before-after` | 05–07 Use cases | Today vs agent-era Work Chart, with the top layer clipped by `inset(0 0 0 X%)`. A transparent range input handles drag, touch and arrow keys. Today / Agent era buttons sit beside it. On entry it sweeps once from Today to Agent era. |
| Dot Globe | `#/interactive/dot-globe` | 08 Stack | 2,200 golden-spiral points with orthographic projection and depth shading. 100 points are lit cobalt and linked to stand for one staffed panel. Drag to spin, with inertia. |
| Kinetic Type Lab | `#/interactive/kinetic-type` | 12 Ask | Per-letter spans on a sine wave. Pointer proximity adds rotation, scale and lift. A click cycles TRY IT / RUN IT / OWN IT. |

## Rules

1. Use one accent. Cobalt carries emphasis. Magenta, acid and amber only carry meaning: an owner type, an honesty label or a placeholder.
2. No em-dashes in copy, no gradient text, no glassmorphism, no purple, and no eyebrow on every element. These come from the harness-engineering anti-slop list.
3. Label every number. Projections get an acid **Illustrative estimate** label. Pricing gets a black **Aspirational / proposed** label. Repo facts carry no label because they are checkable.
4. Never invent traction, customers, revenue, testimonials or quotes. The only quote is Darshan Golchha's, attributed.
5. Fill-in slots render as acid, dashed-outline mono text (`{{DEMO_URL}}`) so they can't ship unnoticed.
6. Interactions have to prove something: before/after shows the redesign, the globe shows the panel, particles show the name. No decorative motion.
7. Respect `prefers-reduced-motion`. Animations snap to their end state.
8. The deck stays offline-safe: one HTML file, system fonts, no CDN.

## Renaming

`{{COMPANY}}` is defined once at the top of the inline script in `index.html` (source: `src/deck.js`):

```js
const COMPANY = 'AI Partner';
```

Every `[data-company]` slot, the page title and the particle title read from it. `src/style.css` has a matching `--company` CSS variable, which the script sets at runtime.
