(function () {
  var toc = document.querySelector(".toc");
  if (toc && "IntersectionObserver" in window) {
    var links = Array.prototype.slice.call(toc.querySelectorAll("a"));
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        links.forEach(function (link) {
          var on = link.getAttribute("href") === "#" + entry.target.id;
          link.classList.toggle("on", on);
          if (on && toc.scrollWidth > toc.clientWidth) toc.scrollTo({ left: link.offsetLeft - 16, behavior: "smooth" });
        });
      });
    }, { rootMargin: "-25% 0px -65% 0px" });
    links.forEach(function (link) {
      var node = document.querySelector(link.getAttribute("href"));
      if (node) observer.observe(node);
    });
  }

  var q = document.getElementById("expert-q");
  if (q) {
    var cards = document.querySelectorAll("[data-expert]");
    var count = document.getElementById("expert-count");
    var none = document.getElementById("expert-empty");
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

  var tabs = document.querySelectorAll("[data-round-tab]");
  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      var round = tab.getAttribute("data-round-tab");
      tabs.forEach(function (t) {
        t.classList.toggle("on", t === tab);
        t.setAttribute("aria-pressed", t === tab ? "true" : "false");
      });
      document.querySelectorAll("#timeline [data-round]").forEach(function (row) {
        row.hidden = round !== "all" && row.getAttribute("data-round") !== round;
      });
      measure();
    });
  });

  function measure() {
    document.querySelectorAll("#timeline li:not([hidden])").forEach(function (row) {
      var text = row.querySelector(".statement");
      var more = row.querySelector(".read-more");
      if (!text || !more || row.classList.contains("open")) return;
      more.hidden = text.scrollHeight <= text.clientHeight + 2;
    });
  }
  document.querySelectorAll("#timeline .read-more").forEach(function (button) {
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
  var list = document.getElementById("recs");
  var sorts = document.querySelectorAll("[data-sort]");
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
})();
