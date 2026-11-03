"""Headless checks for the chat pill, the modal, and careless chat use.

Venice and Exa stay on a local stub. Run from the repo root:

    python3 scripts/ui_break.py
"""
import json
import os
import sys
import threading
from http.server import ThreadingHTTPServer

from werkzeug.serving import make_server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tests.test_running_app import _Handler  # noqa: E402

OUT = os.environ.get("UI_BREAK_OUT", "/opt/cursor/artifacts")


def _serve():
    stub = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    stub.lock = threading.Lock()
    stub.hits = []
    stub.bodies = []
    stub.errors = []
    stub.venice_mode = "ok"
    stub.exa_mode = "ok"
    stub.delay = 0
    threading.Thread(target=stub.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{stub.server_address[1]}/api/v1"
    os.environ["VENICE_API_KEY"] = "test-not-a-real-key"
    os.environ["VENICE_BASE_URL"] = base
    os.environ["EXA_URL"] = base + "/augment/search"
    os.environ["AI_PARTNER_SIGNING_SECRETS"] = "v1:test-signing-secret"
    os.environ["AI_PARTNER_DAILY_ENGAGEMENTS"] = "100"
    os.environ["VERCEL"] = "1"
    os.environ.pop("SUPERMEMORY_API_KEY", None)
    os.environ.pop("KEIKI_SELF_CHECK_URL", None)
    from server.config import Config
    from server.venice import client as venice_client

    Config.VENICE_BASE_URL = base
    venice_client._default_client = None
    from server import create_app

    httpd = make_server("127.0.0.1", 0, create_app())
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{httpd.server_port}", stub, httpd


OVERFLOW_JS = """
() => {
  const vw = document.documentElement.clientWidth;
  const nodes = document.querySelectorAll(".channel-pill, .channel-pill *, .connect-pill, .connect-pill *, .keiki-dialog, .keiki-dialog *, header.top, header.top *");
  const bad = [];
  for (const el of nodes) {
    const style = getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden") continue;
    const box = el.getBoundingClientRect();
    if (box.width < 1 || box.height < 1) continue;
    if (box.right > vw + 1 || box.left < -1) {
      bad.push({tag: el.tagName, cls: String(el.className).slice(0, 80), left: Math.round(box.left), right: Math.round(box.right), text: (el.innerText || "").replace(/\\s+/g, " ").slice(0, 60)});
    }
  }
  const pill = document.querySelector(".channel-pill");
  const dialog = document.querySelector(".keiki-dialog");
  return {
    vw,
    offenders: bad.slice(0, 12),
    pill: pill ? {scroll: pill.scrollWidth, client: pill.clientWidth, right: Math.round(pill.getBoundingClientRect().right)} : null,
    dialog: dialog && dialog.open ? {scroll: dialog.scrollWidth, client: dialog.clientWidth, right: Math.round(dialog.getBoundingClientRect().right)} : null
  };
}
"""


def _shot(page, name):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    page.screenshot(path=path, full_page=False)
    return path


def main():
    from playwright.sync_api import sync_playwright

    origin, stub, httpd = _serve()
    report = {"origin": origin, "shots": [], "overflow": {}, "flows": {}}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for width in (360, 390):
                page = browser.new_page(viewport={"width": width, "height": 800}, device_scale_factor=2, is_mobile=True, has_touch=True)
                page.goto(origin + "/chat", wait_until="networkidle")
                page.locator(".channel-pill").wait_for()
                closed = page.evaluate(OVERFLOW_JS)
                report["overflow"][f"pill-{width}"] = closed
                report["shots"].append(_shot(page, f"pill-{width}.png"))
                page.locator(".pill-stack").screenshot(path=os.path.join(OUT, f"pill-stack-{width}.png"))
                page.locator(".pill-open").click()
                page.locator(".keiki-dialog").wait_for(state="visible")
                opened = page.evaluate(OVERFLOW_JS)
                report["overflow"][f"modal-{width}"] = opened
                report["shots"].append(_shot(page, f"modal-{width}.png"))
                page.close()
            print(json.dumps({"overflow": report["overflow"], "shots": report["shots"]}), flush=True)

            page = browser.new_page(viewport={"width": 390, "height": 800}, is_mobile=True, has_touch=True)
            page.goto(origin + "/chat", wait_until="networkidle")
            hits = {"n": 0}

            def count(route):
                hits["n"] += 1
                route.continue_()

            page.route("**/api/chat", count)
            page.fill("#box", "Pricing for a B2B analytics product")
            page.locator("button.send").dblclick()
            page.wait_for_timeout(400)
            report["flows"]["double_submit_requests"] = hits["n"]
            page.unroute("**/api/chat")
            page.wait_for_selector(".log .msg", timeout=15000)
            page.reload(wait_until="networkidle")
            report["flows"]["refresh_keeps_problem"] = "Pricing for a B2B analytics product" in page.inner_text("body")

            page.route("**/api/chat", lambda route: route.abort())
            page.fill("#box", "A second problem for the dropped connection check")
            page.locator("button.send").click()
            page.wait_for_selector("text=connection dropped", timeout=10000)
            report["flows"]["dropped_connection"] = "connection dropped" in page.inner_text("body").lower()
            page.close()

            context = browser.new_context(viewport={"width": 390, "height": 800})
            first = context.new_page()
            second = context.new_page()
            first.goto(origin + "/chat", wait_until="networkidle")
            first.fill("#box", "Maritime hosting. Team: 4 engineers. Tools: git. Maturity 2.")
            first.locator("button.send").click()
            first.wait_for_selector(".log >> text=Maritime hosting", timeout=15000)
            first.wait_for_timeout(800)
            first.evaluate("localStorage.getItem('ai-partner-chat') && true")
            second.goto(origin + "/chat", wait_until="networkidle")
            report["flows"]["second_tab_sees_first"] = "Maritime hosting" in second.inner_text("body")
            browser.close()
    finally:
        httpd.shutdown()
        stub.shutdown()

    print(json.dumps(report, indent=2))
    overflow = []
    for name, item in report["overflow"].items():
        if item["offenders"] or (item["pill"] and item["pill"]["scroll"] > item["pill"]["client"] + 1):
            overflow.append(name)
        if item["dialog"] and item["dialog"]["scroll"] > item["dialog"]["client"] + 1:
            overflow.append(name + "-dialog")
    if overflow or report["flows"].get("double_submit_requests") != 1 or not report["flows"].get("dropped_connection"):
        raise SystemExit("ui break failed: " + json.dumps({"overflow": overflow, "flows": report["flows"]}))


if __name__ == "__main__":
    main()
