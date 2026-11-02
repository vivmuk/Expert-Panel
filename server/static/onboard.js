(function () {
  "use strict";
  function copy(text, done) {
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, done);
    else done();
  }
  document.addEventListener("click", function (e) {
    var button = e.target.closest && e.target.closest("[data-copy-text], [data-copy]");
    if (!button) return;
    var text = button.getAttribute("data-copy-text");
    if (text == null) {
      var target = document.getElementById(button.getAttribute("data-copy"));
      text = target ? target.textContent : "";
    }
    copy(text, function () {
      var note = button.querySelector(".copied") || button.querySelector("span:last-child");
      if (!note) return;
      var before = note.textContent;
      note.textContent = "Copied";
      setTimeout(function () { note.textContent = button.classList.contains("copy-btn") ? "" : before; }, 1600);
    });
  });
})();
