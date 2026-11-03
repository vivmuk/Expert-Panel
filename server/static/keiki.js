(function () {
  "use strict";
  document.addEventListener("click", function (e) {
    var opener = e.target.closest && e.target.closest("[data-open-dialog]");
    if (opener) {
      var dialog = document.getElementById(opener.getAttribute("data-open-dialog"));
      if (dialog && dialog.showModal) dialog.showModal();
      return;
    }
    if (e.target.tagName === "DIALOG") e.target.close();
  });

  var form = document.getElementById("keiki-signup");
  if (!form) return;
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var status = document.getElementById("keiki-signup-status");
    var out = document.getElementById("keiki-key-out");
    status.textContent = "Issuing a key.";
    fetch("/api/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: document.getElementById("keiki-email").value })
    })
      .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
      .then(function (result) {
        if (!result.ok) {
          status.textContent = (result.data.error && result.data.error.message) || "Sign-up did not finish.";
          out.hidden = true;
          return;
        }
        status.textContent = "Copy it into Keiki's Secrets as AI_PARTNER_API_KEY. It is not shown again.";
        document.getElementById("keiki-key").textContent = result.data.key;
        out.hidden = false;
      })
      .catch(function () { status.textContent = "The request failed. Try again."; });
  });
})();
