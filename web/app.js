// Church Manager: the only script. Six jobs: live search (with a short wait), the print button, the
// file size check, the one-send forms, the month fields that open a month on change (CRIT-8) and the money
// amounts that count up when a page opens (round 4). Pages work
// without it: it marks <html class="js"> first, and only then style.css hides what the script replaces.
// Results are built with textContent, never innerHTML.
// No words live here: the page gives them in its own language (data-text-none, data-text-failed,
// data-text-too-large).
(function () {
  "use strict";

  document.documentElement.classList.add("js");

  document.querySelectorAll("form[data-live-search]").forEach(function (form) {
    var input = form.querySelector("input[name=q]");
    var list = form.querySelector("[data-results]");
    if (!input || !list) { return; }
    var timer = null;
    var seq = 0;

    function hide() { list.hidden = true; list.replaceChildren(); }

    function line(name) {
      var li = document.createElement("li");
      var span = document.createElement("span");
      span.className = "none";
      span.textContent = form.getAttribute("data-text-" + name) || "";
      li.appendChild(span);
      list.replaceChildren(li);
      list.hidden = false;
    }

    function show(rows) {
      if (!rows.length) { line("none"); return; }
      var items = rows.map(function (row) {
        var li = document.createElement("li");
        var a = document.createElement("a");
        a.href = "/people/" + encodeURIComponent(row.id);
        var name = document.createElement("span");
        name.lang = "vi";
        name.textContent = row.full_name;
        var status = document.createElement("span");
        status.className = "status";
        status.textContent = row.status || "—";
        a.append(name, status);
        li.appendChild(a);
        return li;
      });
      list.replaceChildren.apply(list, items);
      list.hidden = false;
    }

    function run() {
      var q = input.value.trim();
      var mine = ++seq;
      if (!q) { hide(); return; }
      fetch("/api/search?q=" + encodeURIComponent(q), { headers: { Accept: "application/json" } })
        .then(function (r) { if (!r.ok) { throw new Error(String(r.status)); } return r.json(); })
        .then(function (rows) { if (mine === seq) { show(rows); } })
        .catch(function () { if (mine === seq) { line("failed"); } });
    }

    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(run, 250);
    });
    input.addEventListener("keydown", function (e) { if (e.key === "Escape") { hide(); } });
    document.addEventListener("click", function (e) { if (!form.contains(e.target)) { list.hidden = true; } });
  });

  // <button type="button" data-print>Print</button> prints the page (print.css hides the navigation).
  document.addEventListener("click", function (e) {
    var button = e.target.closest ? e.target.closest("[data-print]") : null;
    if (button) { e.preventDefault(); window.print(); }
  });

  // <input type="file" data-max-bytes="..." data-text-too-large="..."> stops a file over the limit before
  // the form is sent: the browser's own form check refuses to send while the message is set. Checked on
  // change and once at load (a browser may keep the chosen file after Back).
  document.querySelectorAll("input[type=file][data-max-bytes]").forEach(function (input) {
    var max = Number(input.getAttribute("data-max-bytes"));

    function check() {
      var total = 0;
      Array.prototype.forEach.call(input.files || [], function (file) { total += file.size; });
      if (total > max) {
        input.setCustomValidity(input.getAttribute("data-text-too-large") || "");
        input.reportValidity();
      } else {
        input.setCustomValidity("");
      }
    }

    input.addEventListener("change", check);
    check();
  });

  // <form data-once>: its submit buttons are turned off once the form is sent, so a double click sends it
  // once. The server refuses a second Save anyway; a page shown again by Back gets its buttons back.
  function once(form, off) {
    form.querySelectorAll("button[type=submit]").forEach(function (b) { b.disabled = off; });
  }
  document.addEventListener("submit", function (e) {
    if (e.target.hasAttribute("data-once")) { once(e.target, true); }
  });
  window.addEventListener("pageshow", function () {
    document.querySelectorAll("form[data-once]").forEach(function (form) { once(form, false); });
  });

  // <form data-auto-submit> with an <input type="month">: a chosen month opens at once (no Show click; under
  // html.js style.css hides Show). A pick from the browser's month box sends on change. A typed key fires
  // change too ("1" of "12" is already January), so after a key the form waits for Enter (the browser sends
  // it) or for the field to lose the focus. Only a whole month that passes the field's own check (1900-01 to
  // 9999-12) and is not the month on the page is sent. Back shows the page's month again in the field.
  document.querySelectorAll("form[data-auto-submit]").forEach(function (form) {
    var input = form.querySelector("input[type=month]");
    if (!input) { return; }
    var typed = false;

    function send() {
      typed = false;
      var whole = /^[0-9]{4}-[0-9]{2}$/.test(input.value);
      if (!whole || !input.checkValidity() || input.value === input.defaultValue) { return; }
      if (form.requestSubmit) { form.requestSubmit(); } else { form.submit(); }
    }

    input.addEventListener("pointerdown", function () { typed = false; });
    input.addEventListener("keydown", function (e) { if (e.key !== "Tab" && e.key !== "Enter") { typed = true; } });
    input.addEventListener("change", function () { if (!typed) { send(); } });
    input.addEventListener("blur", function () { if (typed) { send(); } });
    form.addEventListener("submit", function () { typed = false; });
    window.addEventListener("pageshow", function () { input.value = input.defaultValue; typed = false; });
  });

  // Round 4 (the pastor's tweak "numbers count up"): a big money amount (.kpi-value, whole dong with its
  // dots) counts from 0 to its value in 1400ms when the page opens. Only the digits move: the sign and the
  // dong mark stay, and the text ends exactly as the server wrote it. Not when Windows asks for less motion.
  if (window.requestAnimationFrame && !window.matchMedia("(prefers-reduced-motion:reduce)").matches) {
    document.querySelectorAll(".kpi-value").forEach(function (el) {
      var whole = el.textContent;
      var parts = /^(\s*-?)(\d{1,3}(?:\.\d{3})+)(\D*)$/.exec(whole);
      if (!parts) { return; }
      var amount = parseInt(parts[2].replace(/\./g, ""), 10);
      var start = null;
      function step(now) {
        if (start === null) { start = now; }
        var part = Math.min(1, (now - start) / 1400);
        var eased = 1 - Math.pow(1 - part, 3);
        if (part === 1) { el.textContent = whole; return; }
        var shown = String(Math.round(amount * eased)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
        el.textContent = parts[1] + shown + parts[3];
        window.requestAnimationFrame(step);
      }
      window.requestAnimationFrame(step);
    });
  }
})();
