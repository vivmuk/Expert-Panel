(function () {
  var toc = document.querySelector(".toc");
  if (toc && "IntersectionObserver" in window) {
    var links = Array.prototype.slice.call(toc.querySelectorAll("a"));
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        links.forEach(function (link) {
          link.classList.toggle("on", link.getAttribute("href") === "#" + entry.target.id);
        });
      });
    }, { rootMargin: "-20% 0px -70% 0px" });
    links.forEach(function (link) {
      var node = document.querySelector(link.getAttribute("href"));
      if (node) observer.observe(node);
    });
  }

  document.querySelectorAll(".expert h3 button").forEach(function (button) {
    button.addEventListener("click", function () {
      button.closest(".expert").classList.toggle("open");
    });
  });
  var filters = document.getElementById("expert-filters");
  if (filters) {
    var roles = {};
    document.querySelectorAll(".expert").forEach(function (card) { roles[card.getAttribute("data-role")] = true; });
    Object.keys(roles).forEach(function (role) {
      var button = document.createElement("button");
      button.type = "button";
      button.textContent = role;
      button.setAttribute("data-role", role);
      filters.appendChild(button);
    });
    filters.addEventListener("click", function (event) {
      var button = event.target.closest("button");
      if (!button) return;
      var role = button.getAttribute("data-role");
      document.querySelectorAll(".expert").forEach(function (card) {
        card.hidden = role !== "all" && card.getAttribute("data-role") !== role;
      });
    });
  }

  var rounds = {};
  document.querySelectorAll("[data-round]").forEach(function (node) { rounds[node.getAttribute("data-round")] = true; });
  var roundBar = document.getElementById("rounds");
  if (roundBar) {
    Object.keys(rounds).forEach(function (round) {
      var button = document.createElement("button");
      button.type = "button";
      button.textContent = "Round " + round;
      button.addEventListener("click", function () {
        document.querySelectorAll("[data-round]").forEach(function (node) {
          node.hidden = node.getAttribute("data-round") !== round;
        });
      });
      roundBar.appendChild(button);
    });
  }

  document.querySelectorAll("[data-sort]").forEach(function (button) {
    button.addEventListener("click", function () {
      var key = "data-" + button.getAttribute("data-sort");
      var list = document.getElementById("recs");
      if (!list) return;
      var cards = Array.prototype.slice.call(list.children);
      cards.sort(function (a, b) { return (b.getAttribute(key) || "").localeCompare(a.getAttribute(key) || ""); });
      cards.forEach(function (card) { list.appendChild(card); });
    });
  });
  var toggle = document.getElementById("toggle-sides");
  if (toggle) {
    toggle.addEventListener("click", function () {
      document.querySelectorAll(".sides").forEach(function (node) { node.hidden = !node.hidden; });
    });
  }

  var tip = document.getElementById("market-tip");
  document.querySelectorAll("#market-map .chip").forEach(function (chip) {
    function show() {
      if (!tip) return;
      tip.hidden = false;
      tip.textContent = chip.getAttribute("data-note") || chip.textContent;
      var url = chip.getAttribute("data-url");
      if (url) tip.innerHTML = tip.textContent + ' <a href="' + url + '">Source</a>';
    }
    chip.addEventListener("mouseenter", show);
    chip.addEventListener("focus", show);
    chip.addEventListener("click", function () {
      var url = chip.getAttribute("data-url");
      if (url) window.open(url, "_blank", "noopener");
    });
  });

  var diagram = document.getElementById("diagram");
  var scale = 1;
  function zoom(next) {
    scale = Math.max(0.8, Math.min(next, 2));
    if (diagram) diagram.style.transform = "scale(" + scale + ")";
  }
  var zoomIn = document.getElementById("zoom-in");
  var zoomOut = document.getElementById("zoom-out");
  if (zoomIn) zoomIn.addEventListener("click", function () { zoom(scale + 0.1); });
  if (zoomOut) zoomOut.addEventListener("click", function () { zoom(scale - 0.1); });

  document.querySelectorAll("#pack-tabs button").forEach(function (button) {
    button.addEventListener("click", function () {
      var tab = button.getAttribute("data-tab");
      document.getElementById("pack-tree").hidden = tab !== "tree";
      document.getElementById("pack-skills").hidden = tab !== "skills";
    });
  });
  var tree = document.getElementById("pack-tree");
  if (tree) {
    var copy = document.createElement("button");
    copy.type = "button";
    copy.textContent = "Copy";
    copy.addEventListener("click", function () {
      if (navigator.clipboard) navigator.clipboard.writeText(tree.textContent);
      copy.textContent = "Copied";
      setTimeout(function () { copy.textContent = "Copy"; }, 1500);
    });
    tree.before(copy);
  }

  var modal = document.getElementById("modal");
  var close = document.getElementById("modal-close");
  document.querySelectorAll(".artifact").forEach(function (button) {
    button.addEventListener("click", function () {
      document.getElementById("modal-title").textContent = button.getAttribute("data-title");
      document.getElementById("modal-body").textContent = button.getAttribute("data-body");
      modal.hidden = false;
      close.focus();
    });
  });
  function hide() { if (modal) modal.hidden = true; }
  if (close) close.addEventListener("click", hide);
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") hide();
  });
})();
