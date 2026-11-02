(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.documentElement.classList.remove("no-js");

  /* Magnetic dots, from the deck (vivDesign #/interactive/magnetic-dots). Each dot has a home and a
     displaced position: inside a radius the pointer pulls it, outside a damped spring returns it, and
     displaced dots draw a line back to their anchor. With data-ghost, an idle ghost pointer drifts. */
  var pointer = { x: -9999, y: -9999, active: false, at: 0 };
  window.addEventListener("pointermove", function (e) {
    if (e.pointerType === "touch") return;
    pointer.x = e.clientX; pointer.y = e.clientY; pointer.active = true; pointer.at = performance.now();
  }, { passive: true });
  document.addEventListener("pointerleave", function () { pointer.active = false; });

  function Field(cv) {
    var ctx = cv.getContext("2d");
    var ghost = cv.hasAttribute("data-ghost");
    var w = 1, h = 1, dots = [], visible = true, raf = 0, running = false;

    function fit() {
      var r = cv.getBoundingClientRect(), dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = Math.max(1, r.width); h = Math.max(1, r.height);
      cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      var g = w < 600 ? 22 : 30;
      dots = [];
      for (var y = g / 2; y < h; y += g) for (var x = g / 2; x < w; x += g) dots.push({ hx: x, hy: y, x: x, y: y, vx: 0, vy: 0 });
    }

    function frame(t) {
      ctx.clearRect(0, 0, w, h);
      var r = cv.getBoundingClientRect();
      var live = pointer.active && performance.now() - pointer.at < 4000;
      var px = pointer.x - r.left, py = pointer.y - r.top;
      if (!live) {
        if (ghost) { px = w * (0.62 + 0.28 * Math.sin(t / 2300)); py = h * (0.3 + 0.16 * Math.sin(t / 1400)); }
        else { px = -9999; py = -9999; }
      }
      var R = Math.min(220, w * 0.24);
      for (var i = 0; i < dots.length; i++) {
        var d = dots[i], dx = px - d.x, dy = py - d.y, dist = Math.sqrt(dx * dx + dy * dy) || 1;
        if (dist < R) { var f = (1 - dist / R) * 0.9; d.vx += dx / dist * f; d.vy += dy / dist * f; }
        d.vx = (d.vx + (d.hx - d.x) * 0.06) * 0.82; d.vy = (d.vy + (d.hy - d.y) * 0.06) * 0.82;
        d.x += d.vx; d.y += d.vy;
        var ox = d.x - d.hx, oy = d.y - d.hy, off = Math.sqrt(ox * ox + oy * oy);
        if (off > 1.5) {
          ctx.strokeStyle = "rgba(0,51,204,.25)"; ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(d.hx, d.hy); ctx.lineTo(d.x, d.y); ctx.stroke();
        }
        ctx.fillStyle = off > 3 ? "#0033CC" : "rgba(15,15,15,.16)";
        ctx.beginPath(); ctx.arc(d.x, d.y, 1.3 + Math.min(off, 18) / 9, 0, 6.283); ctx.fill();
      }
    }

    function tick(t) { if (!running) return; frame(t); raf = requestAnimationFrame(tick); }
    function start() { if (running || reduce || !visible || document.hidden) return; running = true; raf = requestAnimationFrame(tick); }
    function stop() { running = false; cancelAnimationFrame(raf); }

    fit();
    frame(0);
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        visible = entries[0].isIntersecting;
        if (visible) start(); else stop();
      }).observe(cv);
    }
    document.addEventListener("visibilitychange", function () { if (document.hidden) stop(); else start(); });
    var timer = 0;
    window.addEventListener("resize", function () {
      clearTimeout(timer);
      timer = setTimeout(function () { fit(); frame(0); }, 120);
    });
    start();
  }
  document.querySelectorAll("canvas[data-dots]").forEach(function (cv) { Field(cv); });

  /* One delegated spotlight for every .spot surface. */
  if (!reduce) {
    document.addEventListener("pointermove", function (e) {
      var el = e.target.closest && e.target.closest(".spot");
      if (!el) return;
      var r = el.getBoundingClientRect();
      el.style.setProperty("--mx", (e.clientX - r.left) + "px");
      el.style.setProperty("--my", (e.clientY - r.top) + "px");
    }, { passive: true });
  }

  /* Reveal on scroll, staggered within a group. */
  function reveal(root) {
    var items = (root || document).querySelectorAll(".reveal:not(.in)");
    if (reduce || !("IntersectionObserver" in window)) { items.forEach(function (el) { el.classList.add("in"); }); return; }
    var io = new IntersectionObserver(function (entries) {
      var n = 0;
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.style.setProperty("--d", Math.min(n++ * 0.06, 0.36) + "s");
        entry.target.classList.add("in");
        io.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.06 });
    items.forEach(function (el) { io.observe(el); });
  }
  reveal();
  window.aiPartnerReveal = reveal;

  var top = document.querySelector(".top");
  if (top) {
    var onScroll = function () { top.classList.toggle("scrolled", window.scrollY > 4); };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }
})();
