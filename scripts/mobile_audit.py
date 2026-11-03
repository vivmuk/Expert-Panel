"""Check that every page fits a phone: layout at device width, no horizontal scroll or pan, nothing past the viewport edge.

Usage: python scripts/mobile_audit.py https://ai-partner.up.railway.app [--shots DIR]
"""
import argparse
import sys

from playwright.sync_api import sync_playwright

PAGES = (
    "/", "/chat", "/connect", "/signup", "/catalog", "/about", "/deck", "/demos",
    "/demos/maritime", "/demos/keiki", "/demos/orchid", "/what-you-get", "/no-such-page",
)
WIDTHS = (360, 390, 430)

# Elements past the edge count only when no ancestor clips or scrolls them.
OVERFLOW = """() => {
  const vw = window.innerWidth;
  const clipped = (el) => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (s.overflowX !== 'visible' || s.contain.includes('paint')) {
        const r = p.getBoundingClientRect();
        if (r.left >= -1 && r.right <= vw + 1) return true;
      }
    }
    return false;
  };
  const bad = [];
  for (const el of document.body.querySelectorAll('*')) {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || s.position === 'fixed') continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if ((r.right > vw + 1 || r.left < -1) && !clipped(el)) {
      const name = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/).join('.') : '');
      bad.push(`${name} [${Math.round(r.left)}..${Math.round(r.right)}]`);
    }
  }
  window.scrollTo(400, window.scrollY);
  const panned = window.scrollX;
  window.scrollTo(0, window.scrollY);
  return {vw, scroll: document.documentElement.scrollWidth, panned, bad: bad.slice(0, 8)};
}"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("--shots")
    parser.add_argument("--chrome", default="/usr/local/bin/google-chrome")
    args = parser.parse_args()
    base = args.base.rstrip("/")
    failures = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chrome)
        for width in WIDTHS:
            ctx = browser.new_context(viewport={"width": width, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            page = ctx.new_page()
            for path in PAGES:
                page.goto(base + path, wait_until="networkidle")
                page.evaluate("document.querySelectorAll('.reveal').forEach(e => e.classList.add('in'))")
                page.wait_for_timeout(250)
                got = page.evaluate(OVERFLOW)
                ok = got["vw"] == width and got["scroll"] <= got["vw"] and got["panned"] == 0 and not got["bad"]
                failures += not ok
                print(f"{'ok  ' if ok else 'FAIL'} {width}px {path:<16} innerWidth={got['vw']} scrollWidth={got['scroll']} panX={got['panned']}"
                      + ("" if ok else f"  past edge: {', '.join(got['bad']) or '-'}"))
                if args.shots and width == 390 and path in ("/", "/connect", "/demos/maritime"):
                    slug = path.strip("/").replace("/", "-") or "home"
                    page.screenshot(path=f"{args.shots}/mobile-390-{slug}.png", full_page=True)
            ctx.close()
        browser.close()
    print(f"\n{failures} failing page/width combinations")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
