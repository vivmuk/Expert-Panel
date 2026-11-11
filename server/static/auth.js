(function () {
  var bar = document.getElementById("account-bar");
  if (!bar) return;

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function text(tag, value, className) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    node.textContent = value;
    return node;
  }

  function showSignedOut(note) {
    clear(bar);
    var form = document.createElement("form");
    var label = text("label", "Email");
    label.setAttribute("for", "account-email");
    label.className = "sr-only";
    var input = document.createElement("input");
    input.id = "account-email";
    input.type = "email";
    input.required = true;
    input.autocomplete = "email";
    input.placeholder = "you@company.com";
    var button = document.createElement("button");
    button.className = "btn small primary";
    button.type = "submit";
    button.textContent = "Email me a sign-in link";
    var status = text("p", note || "Three questions are included. Sign in to use them.", "account-note");
    form.appendChild(label);
    form.appendChild(input);
    form.appendChild(button);
    bar.appendChild(form);
    bar.appendChild(status);
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      status.textContent = "Sending a sign-in link.";
      fetch("/api/auth/request", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({email: input.value})
      }).then(function (res) {
        return res.json().then(function (data) { return {ok: res.ok, data: data}; });
      }).then(function (result) {
        if (!result.ok) {
          status.textContent = (result.data.error && result.data.error.message) || "Sign-in did not send.";
          return;
        }
        status.textContent = "Check your email for the sign-in link.";
      }).catch(function () {
        status.textContent = "Sign-in did not send.";
      });
    });
  }

  function showSignedIn(me) {
    clear(bar);
    var remaining = Number(me.questions_remaining);
    bar.appendChild(text("span", me.email, "account-email"));
    bar.appendChild(text("span", remaining + " questions left", "account-note"));
    var button = document.createElement("button");
    button.type = "button";
    button.className = "btn small ghost";
    button.textContent = "Sign out";
    button.addEventListener("click", function () {
      fetch("/api/auth/logout", {method: "POST"}).then(function () { showSignedOut("Signed out."); });
    });
    bar.appendChild(button);
  }

  fetch("/api/auth/me", {headers: {"Accept": "application/json"}}).then(function (res) {
    return res.json().then(function (data) { return {ok: res.ok, data: data}; });
  }).then(function (result) {
    if (result.ok && result.data.email) showSignedIn(result.data);
    else showSignedOut();
  }).catch(function () {
    showSignedOut();
  });
})();
