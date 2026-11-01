// Church Manager: the only script. Two jobs: live search (with a short wait) and the print button.
// Pages work without it. Results are built with textContent, never innerHTML.
(function () {
  "use strict";

  document.querySelectorAll("form[data-live-search]").forEach(function (form) {
    var input = form.querySelector("input[name=q]");
    var list = form.querySelector("[data-results]");
    if (!input || !list) { return; }
    var timer = null;
    var seq = 0;

    function hide() { list.hidden = true; list.replaceChildren(); }

    function line(text) {
      var li = document.createElement("li");
      var span = document.createElement("span");
      span.className = "none";
      span.textContent = text;
      li.appendChild(span);
      list.replaceChildren(li);
      list.hidden = false;
    }

    function show(rows) {
      if (!rows.length) { line("No Person found. Press Search to see the page."); return; }
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
        .catch(function () { if (mine === seq) { line("Could not search right now. Press Search to try again."); } });
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
})();
