(function () {
  var PAGES = {
    navigate: true
  };
  var root = document.createElement("div");
  root.id = "guide";
  root.innerHTML = ''
    + '<button type="button" id="guide-talk" aria-pressed="false" aria-label="Push to talk">'
    + '<img src="/img/brand/avatar.webp" alt="" width="48" height="48">'
    + '</button>'
    + '<div id="guide-panel" hidden>'
    + '<p id="guide-heard"></p>'
    + '<p id="guide-caption"></p>'
    + '<label class="kicker" for="guide-text">Or type</label>'
    + '<input id="guide-text" type="text" autocomplete="off">'
    + '<div class="row"><button type="button" id="guide-send">Send</button>'
    + '<button type="button" id="guide-tour" class="ghost">Tour</button></div>'
    + '</div>';
  document.body.appendChild(root);
  var talk = document.getElementById("guide-talk");
  var panel = document.getElementById("guide-panel");
  var heard = document.getElementById("guide-heard");
  var caption = document.getElementById("guide-caption");
  var box = document.getElementById("guide-text");
  var recorder = null;
  var chunks = [];
  var started = 0;

  talk.addEventListener("click", function () {
    panel.hidden = false;
    if (recorder && recorder.state === "recording") stop();
    else start();
  });
  document.getElementById("guide-send").addEventListener("click", function () {
    var text = box.value.trim();
    if (!text) return;
    plan(text);
  });
  box.addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
      event.preventDefault();
      document.getElementById("guide-send").click();
    }
  });
  document.getElementById("guide-tour").addEventListener("click", playTour);
  document.addEventListener("keydown", function (event) {
    if (event.key === "g" && event.altKey) {
      event.preventDefault();
      panel.hidden = !panel.hidden;
      if (!panel.hidden) box.focus();
    }
  });

  function start() {
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      caption.textContent = "This browser has no microphone. Type instead.";
      box.focus();
      return;
    }
    navigator.mediaDevices.getUserMedia({audio: true}).then(function (stream) {
      chunks = [];
      started = Date.now();
      recorder = new MediaRecorder(stream);
      recorder.ondataavailable = function (event) { if (event.data.size) chunks.push(event.data); };
      recorder.onstop = function () {
        stream.getTracks().forEach(function (track) { track.stop(); });
        var blob = new Blob(chunks, {type: recorder.mimeType || "audio/webm"});
        var seconds = (Date.now() - started) / 1000;
        sendAudio(blob, seconds);
      };
      recorder.start();
      talk.setAttribute("aria-pressed", "true");
      setTimeout(function () { if (recorder && recorder.state === "recording") stop(); }, 30000);
    }).catch(function () {
      caption.textContent = "Microphone permission was blocked. Type instead.";
      box.focus();
    });
  }

  function stop() {
    if (recorder && recorder.state === "recording") recorder.stop();
    talk.setAttribute("aria-pressed", "false");
  }

  function sendAudio(blob, seconds) {
    var body = new FormData();
    body.append("audio", blob, "turn.webm");
    body.append("duration", String(seconds));
    fetch("/api/voice/turn", {method: "POST", body: body}).then(read).then(apply).catch(fail);
  }

  function plan(text) {
    fetch("/api/voice/plan", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text: text})
    }).then(read).then(apply).catch(fail);
  }

  function read(res) { return res.json().then(function (data) { data.ok = res.ok; return data; }); }

  function apply(data) {
    if (!data.ok) {
      caption.textContent = (data.error && data.error.message) || "The guide did not answer.";
      return;
    }
    heard.textContent = "I heard: " + (data.heard || "");
    caption.textContent = data.captions || "";
    run(data.action || {});
    if (data.audio_mpeg_base64) play64(data.audio_mpeg_base64);
  }

  function fail() { caption.textContent = "The guide did not answer."; }

  function run(action) {
    if (action.action === "navigate" && PAGES.navigate) location.href = action.page;
    if (action.action === "scroll_to") {
      var node = document.getElementById(action.section);
      if (node) node.scrollIntoView();
    }
    if (action.action === "fill_problem") {
      var problem = document.getElementById("box");
      if (problem) problem.value = action.text || "";
    }
    if (action.action === "set_depth") sessionStorage.setItem("ai-partner-depth", action.depth || "strategy");
    if (action.action === "start_engagement") {
      var form = document.getElementById("form");
      if (form) form.requestSubmit ? form.requestSubmit() : form.submit();
    }
    if (action.action === "open_demo") location.href = "/demos/" + action.slug;
    if (action.action === "copy_snippet") {
      var snippet = document.querySelector('[data-snippet="' + action.id + '"]');
      if (snippet && navigator.clipboard) navigator.clipboard.writeText(snippet.textContent);
    }
  }

  function play64(encoded) {
    var audio = new Audio("data:audio/mpeg;base64," + encoded);
    audio.play();
  }

  function playTour() {
    panel.hidden = false;
    var lines = [
      "This is the start. Describe the business problem, then press Solve it.",
      "Demos shows three public engagements: Maritime, Keiki, and Orchid.",
      "The deck is the thesis, from the invoice to the resident model.",
      "The catalog lists every artifact a consulting engagement can produce.",
      "Connect has the setup you paste into ChatGPT, Claude, or Cursor.",
      "Pricing is ten dollars for a strategy engagement. Harness Build is contact us."
    ];
    var index = 0;
    function next() {
      if (index >= lines.length) return;
      caption.textContent = lines[index];
      var audio = new Audio("/voice/tour-" + (index + 1) + ".mp3");
      index += 1;
      audio.onended = next;
      audio.onerror = next;
      audio.play().catch(next);
    }
    var welcome = new Audio("/voice/welcome.mp3");
    caption.textContent = "I am the AI Partner guide.";
    welcome.onended = next;
    welcome.onerror = next;
    welcome.play().catch(next);
  }
})();
