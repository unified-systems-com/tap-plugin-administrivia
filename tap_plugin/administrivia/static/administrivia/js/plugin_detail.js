/* Plugin Detail panel — per-table text filter for the node-type and edge-type tables.
 *
 * Deliberately the same shape as git_serious's query pack
 * (git_serious/js/queries.js, spec-git-serious-query-pack): rows carry a pre-lowercased
 * `data-text`, the box narrows by `indexOf`, and a live "N of M shown" count plus an
 * explicit empty row mean a filter that matches nothing is a STATED state, never a blank
 * table. Reused rather than reinvented so this page behaves like the rest of the product.
 *
 * Content only: this hides and shows rows the server already sent. It never fetches, never
 * sorts, and never changes what a row says.
 *
 * Scoped per panel instance, because the detail panel is mounted TWICE on the plugin page
 * (head sections above the taxonomy graph, the rest below it) and a document-wide query
 * would wire one panel's box to the other's rows.
 *
 * Spec: specs/spec-administrivia-v0.md req-administrivia-v0-plugin-detail-panel.
 */
(function () {
  "use strict";

  function wire(section) {
    if (section.getAttribute("data-pd-filter-ready") === "1") { return; }
    var input = section.querySelector("[data-pd-filter-input]");
    var count = section.querySelector("[data-pd-filter-count]");
    var none = section.querySelector("[data-pd-none]");
    var rows = Array.prototype.slice.call(section.querySelectorAll("[data-pd-row]"));
    if (!input || !rows.length) { return; }

    function apply() {
      var text = (input.value || "").trim().toLowerCase();
      var shown = 0;
      rows.forEach(function (tr) {
        var ok = !text || (tr.getAttribute("data-text") || "").indexOf(text) !== -1;
        tr.hidden = !ok;
        if (ok) { shown += 1; }
      });
      if (count) {
        // Silent when nothing is filtered: a count that always reads "12 of 12 shown"
        // is noise, and the heading already carries the total.
        count.textContent = text ? shown + " of " + rows.length + " shown" : "";
      }
      if (none) { none.hidden = shown !== 0; }
    }

    input.addEventListener("input", apply);
    // Escape clears the box — the same gesture that dismisses a search everywhere else.
    input.addEventListener("keydown", function (evt) {
      if (evt.key === "Escape" && input.value) {
        evt.stopPropagation();
        input.value = "";
        apply();
      }
    });
    apply();
    section.setAttribute("data-pd-filter-ready", "1");
  }

  function init(panelId) {
    var scope = document;
    if (panelId) {
      var owned = document.querySelectorAll('[id$="-' + panelId + '"][data-pd-filterable]');
      Array.prototype.slice.call(owned).forEach(wire);
      if (owned.length) { return; }
    }
    Array.prototype.slice.call(scope.querySelectorAll("[data-pd-filterable]")).forEach(wire);
  }

  window.TapPluginDetail = { init: init };

  /* HTMX swaps bring the panel back as a fresh fragment; wire whatever arrived. */
  document.body &&
    document.body.addEventListener("htmx:afterSwap", function (evt) {
      if (evt.target && evt.target.querySelectorAll) {
        Array.prototype.slice.call(evt.target.querySelectorAll("[data-pd-filterable]")).forEach(wire);
      }
    });
})();
