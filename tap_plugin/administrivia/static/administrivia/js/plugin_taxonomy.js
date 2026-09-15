/* Plugin Taxonomy panel — hands a server-synthesized type graph to Cytoscape.
 *
 * This file draws; it never decides. Every node, edge, colour input and count state is
 * resolved server-side in plugin_facts.py / the panel type, so the picture and the tables
 * beside it cannot disagree (req-administrivia-v0-plugin-facts-1).
 *
 * Styling reads fields off each element's data — `kind_class` (own | foreign | any) and
 * `count_state` (observed | never_observed | not_observable) — rather than recomputing
 * anything. A never-observed type is drawn DASHED and a not-observable one GHOSTED, and
 * both are named in the panel's legend: a reader must never have to infer which is which.
 *
 * Cytoscape is the copy tap_viz already vendors; no second copy is introduced.
 *
 * Spec: specs/spec-administrivia-v0.md req-administrivia-v0-plugin-taxonomy-panel.
 */
/* global cytoscape */
/* `cytoscape` is a browser global supplied by the vendored library, loaded from its own
 * <script> tag before this file (the panel type declares it first in `js`). The directive
 * is the same one tap_viz/js/panel-graph.js carries for the same global; `init` still
 * checks it is really there before using it, because a lint directive is a promise to the
 * linter, not a guarantee at runtime. */
(function () {
  "use strict";

  var C = {
    own: "#334155",        /* slate-700  — this plugin's own vocabulary */
    ownFill: "#e2e8f0",    /* slate-200 */
    foreign: "#7c5cff",    /* violet     — another plugin's type, the cross-plugin half */
    foreignFill: "#ece9fe",
    any: "#a8a29e",        /* stone-400  — the unconstrained-endpoint sentinel */
    anyFill: "#f5f5f4",
    text: "#1e293b",       /* slate-800 */
    muted: "#64748b",      /* slate-500 */
    edge: "#94a3b8",       /* slate-400 */
    edgeCross: "#7c5cff"
  };

  function stylesheet() {
    return [
      {
        selector: "node",
        style: {
          "shape": "round-rectangle",
          "width": "label",
          "height": "label",
          "padding": "10px",
          "background-color": C.ownFill,
          "border-width": 1.5,
          "border-color": C.own,
          "label": function (n) {
            var d = n.data();
            var lines = [d.label];
            if (d.sublabel) { lines.push(d.sublabel); }
            lines.push(d.count_label);
            return lines.join("\n");
          },
          "text-wrap": "wrap",
          "text-valign": "center",
          "text-halign": "center",
          "font-size": 11,
          "line-height": 1.35,
          "color": C.text,
          "text-max-width": "190px"
        }
      },
      { selector: 'node[kind_class = "foreign"]',
        style: { "background-color": C.foreignFill, "border-color": C.foreign, "border-style": "solid" } },
      { selector: 'node[kind_class = "any"]',
        style: { "background-color": C.anyFill, "border-color": C.any, "border-style": "dotted", "color": C.muted } },

      /* Third state, drawn. Dashed = registered but nothing ever used it. */
      { selector: 'node[count_state = "never_observed"]',
        style: { "border-style": "dashed", "background-opacity": 0.45 } },
      /* Ghosted = we could not look. Deliberately NOT the same as zero. */
      { selector: 'node[count_state = "not_observable"]',
        style: { "border-style": "dotted", "background-opacity": 0.2, "color": C.muted } },

      {
        selector: "edge",
        style: {
          "width": 1.6,
          "line-color": C.edge,
          "target-arrow-color": C.edge,
          "target-arrow-shape": "triangle",
          "arrow-scale": 0.9,
          "curve-style": "bezier",
          "control-point-step-size": 50,
          "label": "data(label)",
          "font-size": 9,
          "color": C.muted,
          "text-background-color": "#ffffff",
          "text-background-opacity": 0.85,
          "text-background-padding": "2px",
          "text-rotation": "autorotate"
        }
      },
      { selector: "edge[?cross_plugin]",
        style: { "line-color": C.edgeCross, "target-arrow-color": C.edgeCross, "line-style": "solid", "width": 2 } },
      { selector: 'edge[count_state = "never_observed"]', style: { "line-style": "dashed", "opacity": 0.75 } },
      { selector: 'edge[count_state = "not_observable"]', style: { "line-style": "dotted", "opacity": 0.45 } },
      { selector: "node:selected", style: { "border-width": 3, "border-color": "#0f172a" } }
    ];
  }

  function init(panelId) {
    var mount = document.getElementById("tap-tax-graph-" + panelId);
    var payload = document.getElementById("tap-tax-elements-" + panelId);
    if (!mount || !payload) { return; }
    if (mount.getAttribute("data-tax-ready") === "1") { return; }
    if (typeof cytoscape !== "function") {
      mount.textContent = "Cytoscape did not load; the taxonomy graph cannot be drawn.";
      return;
    }

    var elements;
    try { elements = JSON.parse(payload.textContent); }
    catch (e) {
      mount.textContent = "The taxonomy graph payload could not be read.";
      return;
    }
    if (!elements || !elements.length) { return; }

    var cy = cytoscape({
      container: mount,
      elements: elements,
      style: stylesheet(),
      wheelSensitivity: 0.25,
      /* breadthfirst reads a declared vocabulary the way a human draws one: sources
         above targets, so a finding-flags-workflow chain runs down the page. */
      layout: { name: "breadthfirst", directed: true, spacingFactor: 1.35, padding: 30, avoidOverlap: true }
    });
    cy.on("layoutstop", function () { cy.fit(undefined, 40); });

    /* Hover tooltip: the type's own description, the honest reason for an unobservable
       count, and the slug — everything the node label had no room for. */
    cy.nodes().forEach(function (n) {
      var d = n.data();
      var bits = [d.slug];
      if (d.owner) { bits.push("owned by " + d.owner); }
      if (d.description) { bits.push(d.description); }
      if (d.reason) { bits.push(d.reason); }
      n.data("tooltip", bits.join(" — "));
    });
    mount.setAttribute("title", "");
    cy.on("mouseover", "node", function (evt) { mount.setAttribute("title", evt.target.data("tooltip") || ""); });
    cy.on("mouseout", "node", function () { mount.setAttribute("title", ""); });

    var refit = document.querySelector('[data-tax-refit="' + panelId + '"]');
    if (refit) { refit.addEventListener("click", function () { cy.fit(undefined, 40); }); }

    wireFullscreen(panelId, cy);

    mount.setAttribute("data-tax-ready", "1");
  }

  /* ---------------------------------------------------------------------------
   * Full screen
   *
   * Two things make this more than a one-liner:
   *
   *  - Cytoscape caches its container's box. After the viewport changes in EITHER
   *    direction it must be told (`cy.resize()`), then re-fitted, or it draws into a
   *    stale rectangle — nodes clipped on the way in, marooned in a corner on the way
   *    out. Both directions, not just entering.
   *  - The button's label must follow the DOCUMENT, not the click. `requestFullscreen()`
   *    returns a promise that can reject (a permissions policy, a user gesture that did
   *    not count), and Escape leaves full screen without touching the button at all. So
   *    every label change hangs off `fullscreenchange`, and the click only ever asks.
   * ------------------------------------------------------------------------- */

  function fsElement() {
    return document.fullscreenElement || document.webkitFullscreenElement || null;
  }

  function fsRequest(el) {
    var fn = el.requestFullscreen || el.webkitRequestFullscreen;
    if (!fn) { return null; }
    try { return fn.call(el); } catch (e) { return null; }
  }

  function fsExit() {
    var fn = document.exitFullscreen || document.webkitExitFullscreen;
    if (!fn) { return null; }
    try { return fn.call(document); } catch (e) { return null; }
  }

  function fsSupported(el) {
    return !!(
      (el.requestFullscreen || el.webkitRequestFullscreen) &&
      (document.fullscreenEnabled === undefined || document.fullscreenEnabled)
    );
  }

  function wireFullscreen(panelId, cy) {
    var stage = document.querySelector('[data-tax-stage="' + panelId + '"]');
    var btn = document.querySelector('[data-tax-fullscreen="' + panelId + '"]');
    if (!stage || !btn) { return; }

    // The button ships hidden and is revealed only where the API is really available —
    // a control that cannot do the thing it names is worse than no control.
    if (!fsSupported(stage)) { return; }
    btn.hidden = false;

    var label = btn.querySelector("[data-tax-fullscreen-label]");
    // The exit control lives INSIDE the stage: the bar button is outside the fullscreened
    // subtree and is unreachable while full screen is active, so it cannot be the way out.
    var exit = stage.querySelector('[data-tax-exit="' + panelId + '"]');

    function isFull() { return fsElement() === stage; }

    function paint() {
      var full = isFull();
      stage.classList.toggle("tap-tax__stage--full", full);
      btn.classList.toggle("is-active", full);
      btn.setAttribute("aria-pressed", full ? "true" : "false");
      btn.setAttribute("aria-label", full ? "Exit full screen" : "Enter full screen");
      btn.setAttribute("title", full ? "Leave full screen (or press Escape)" : "Show the taxonomy full screen");
      if (label) { label.textContent = full ? "Exit full screen" : "Full screen"; }
      if (exit) { exit.hidden = !full; }
    }

    function reflow() {
      // Two frames: one for the browser to settle the new box, one for cytoscape to
      // measure it. Resizing in the same tick reads the OLD rectangle.
      window.requestAnimationFrame(function () {
        window.requestAnimationFrame(function () {
          cy.resize();
          cy.fit(undefined, 40);
        });
      });
    }

    function onChange() {
      paint();
      reflow();
    }

    btn.addEventListener("click", function () {
      var p = isFull() ? fsExit() : fsRequest(stage);
      // A rejected request must not leave the button claiming a state we are not in.
      if (p && typeof p.catch === "function") { p.catch(paint); }
    });

    if (exit) {
      exit.addEventListener("click", function () {
        var p = fsExit();
        if (p && typeof p.catch === "function") { p.catch(paint); }
      });
    }

    document.addEventListener("fullscreenchange", onChange);
    document.addEventListener("webkitfullscreenchange", onChange);
    paint();
  }

  window.TapPluginTaxonomy = { init: init };

  /* HTMX swaps bring the panel back as a fresh fragment; re-init what arrived. */
  document.body &&
    document.body.addEventListener("htmx:afterSwap", function (evt) {
      var el = evt.target && evt.target.querySelector
        ? evt.target.querySelector('[id^="tap-tax-graph-"]')
        : null;
      if (el) { init(el.id.replace("tap-tax-graph-", "")); }
    });
})();
