// Church Manager: the only script. Three jobs: live search (with a short wait), the print button and the
// file size check. Pages work without it. Results are built with textContent, never innerHTML.
// No words live here: the page gives them in its own language (data-text-none, data-text-failed,
// data-text-too-large).
(function () {
  "use strict";

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
})();
