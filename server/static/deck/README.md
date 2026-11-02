# AI Partner: The First 1,000 pitch deck

Open `index.html` in any browser. It is self-contained (inline CSS and JS, system fonts, no network).

- Navigate with ← / →, Space, PageUp/PageDown, Home/End, the dots, the arrow buttons, or a swipe on mobile. `#5` deep-links to slide 5.
- Rename the company: edit `const COMPANY = 'AI Partner';` near the top of the `<script>` (or in `src/deck.js` and run `src/build.sh`).
- Before sending, fill in `{{DEMO_URL}}` and `{{DEMO_ACCESS}}` on slide 12 (search `index.html` or `src/body2.html`).
- Style guide: `STYLE.md` ("Constellation Paper").
- Sources live in `src/` (`style.css`, `body.html`, `usecases.py`, `body2.html`, `deck.js`). `src/build.sh` regenerates `index.html`. `src/shoot.py` takes screenshots and runs the overflow check at 1280x800 and 390x844.
