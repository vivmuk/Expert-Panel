(function () {
  var slot = document.getElementById("onboard-slot");
  if (!slot || localStorage.getItem("ai-partner-onboard-dismissed") === "1") return;

  var logos = [
    ["/img/marks/claude.svg", "Claude mark"],
    ["/img/marks/openai-blossom.svg", "OpenAI blossom"],
    ["/img/marks/cursor.svg", "Cursor cube"],
    ["/img/marks/claude-code.png", "Claude Code mark"],
    ["/img/marks/gemini.svg", "Gemini mark"],
    ["/img/marks/copilot.svg", "GitHub Copilot mark"],
    ["/img/marks/opencode.png", "OpenCode mark"]
  ];

  var root = document.createElement("div");
  root.className = "onboard";
  root.innerHTML = ''
    + '<button type="button" class="onboard-main" id="onboard-copy">'
    + '<span class="onboard-logos"></span>'
    + '<span class="onboard-label">Onboard Your Agent</span>'
    + '<svg class="onboard-copy" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">'
    + '<rect x="8" y="8" width="12" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.6"/>'
    + '<path d="M6 16H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" fill="none" stroke="currentColor" stroke-width="1.6"/>'
    + '</svg></button>'
    + '<button type="button" class="onboard-x" aria-label="Dismiss">×</button>'
    + '<p class="onboard-toast" role="status" hidden>Copied</p>';
  var holder = root.querySelector(".onboard-logos");
  logos.forEach(function (logo) {
    var img = document.createElement("img");
    img.src = logo[0];
    img.alt = logo[1];
    img.width = 28;
    img.height = 28;
    holder.appendChild(img);
  });
  slot.appendChild(root);

  var toast = root.querySelector(".onboard-toast");
  document.getElementById("onboard-copy").addEventListener("click", function () {
    var text = "Set up AI Partner for me. Fetch " + location.origin + "/get-started.md and follow it.";
    var done = function () {
      toast.hidden = false;
      window.setTimeout(function () { toast.hidden = true; }, 2200);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, done);
    } else {
      done();
    }
  });
  root.querySelector(".onboard-x").addEventListener("click", function () {
    localStorage.setItem("ai-partner-onboard-dismissed", "1");
    root.remove();
  });
})();
