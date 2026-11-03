(function () {
  function spy(nav, root) {
    if (!nav || !("IntersectionObserver" in window)) return;
    if (nav._spy) nav._spy.disconnect();
    var links = Array.prototype.slice.call(nav.querySelectorAll('a[href^="#"]'));
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        links.forEach(function (link) {
          var on = link.getAttribute("href") === "#" + entry.target.id;
          link.classList.toggle("on", on);
          if (on) link.setAttribute("aria-current", "true"); else link.removeAttribute("aria-current");
          if (on && nav.scrollWidth > nav.clientWidth) nav.scrollTo({ left: link.offsetLeft - 16, behavior: "smooth" });
        });
      });
    }, { rootMargin: "-25% 0px -65% 0px" });
    links.forEach(function (link) {
      var node = root.querySelector(link.getAttribute("href")) || document.querySelector(link.getAttribute("href"));
      if (node) observer.observe(node);
    });
    nav._spy = observer;
  }

  function init(root, nav) {
    root = root || document;
    spy(nav || document.querySelector(".toc"), root);

    var q = root.querySelector("#expert-q");
    if (q) {
      var cards = root.querySelectorAll("[data-expert]");
      var count = root.querySelector("#expert-count");
      var none = root.querySelector("#expert-empty");
      q.addEventListener("input", function () {
        var term = q.value.trim().toLowerCase();
        var shown = 0;
        cards.forEach(function (card) {
          var hit = !term || card.getAttribute("data-expert").indexOf(term) >= 0;
          card.hidden = !hit;
          if (hit) shown += 1;
        });
        count.textContent = term ? shown + " of " + cards.length + " experts" : cards.length + " experts";
        if (none) none.hidden = shown > 0;
      });
    }

    root.querySelectorAll("[data-expand]").forEach(function (button) {
      button.addEventListener("click", function () {
        var open = button.getAttribute("aria-pressed") !== "true";
        var list = root.querySelector("#" + button.getAttribute("data-expand"));
        if (list) list.querySelectorAll("details").forEach(function (d) { d.open = open; });
        button.setAttribute("aria-pressed", open ? "true" : "false");
        button.lastChild.textContent = open ? "Collapse all" : "Expand all";
      });
    });

    var tabs = root.querySelectorAll("[data-round-tab]");
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        var round = tab.getAttribute("data-round-tab");
        tabs.forEach(function (t) {
          t.classList.toggle("on", t === tab);
          t.setAttribute("aria-pressed", t === tab ? "true" : "false");
        });
        root.querySelectorAll("#timeline [data-round]").forEach(function (row) {
          row.hidden = round !== "all" && row.getAttribute("data-round") !== round;
        });
        measure();
      });
    });

    function measure() {
      root.querySelectorAll("#timeline li:not([hidden])").forEach(function (row) {
        var text = row.querySelector(".statement");
        var more = row.querySelector(".read-more");
        if (!text || !more || row.classList.contains("open")) return;
        more.hidden = text.scrollHeight <= text.clientHeight + 2;
      });
    }
    root.querySelectorAll("#timeline .read-more").forEach(function (button) {
      button.addEventListener("click", function () {
        var row = button.closest("li");
        var open = row.classList.toggle("open");
        button.textContent = open ? "Show less" : "Read all";
      });
    });
    measure();
    window.addEventListener("resize", function () { window.requestAnimationFrame(measure); });

    var RANK = { high: 3, medium: 2, low: 1 };
    function level(card, key) { return RANK[(card.getAttribute("data-" + key) || "").toLowerCase()] || 0; }
    var list = root.querySelector("#recs");
    var sorts = root.querySelectorAll("[data-sort]");
    sorts.forEach(function (button) {
      button.addEventListener("click", function () {
        if (!list) return;
        var key = button.getAttribute("data-sort");
        var cards = Array.prototype.slice.call(list.children);
        cards.sort(function (a, b) {
          var rank = Number(a.getAttribute("data-rank")) - Number(b.getAttribute("data-rank"));
          if (key === "rank") return rank;
          var diff = key === "effort" ? level(a, key) - level(b, key) : level(b, key) - level(a, key);
          return diff || rank;
        });
        cards.forEach(function (card) { list.appendChild(card); });
        sorts.forEach(function (b) {
          b.classList.toggle("on", b === button);
          b.setAttribute("aria-pressed", b === button ? "true" : "false");
        });
      });
    });
  }

  window.initReport = init;
  window.reportSpy = spy;
  if (document.querySelector(".report-body")) init(document);
})();
