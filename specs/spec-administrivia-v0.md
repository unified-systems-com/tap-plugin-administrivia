# Administrivia Specification

## Philosophy

Administrivia is TAP's first-party administrative web plugin. It exists to host practical, human-facing administration surfaces for TAP subsystems using TAP's own page and panel system rather than relying on Django admin as the primary operator experience.

Administrivia is an implementation home and navigation shell, not the canonical owner of every subsystem's operational semantics. When an administrative surface belongs conceptually to another TAP app or plugin, the owning subsystem keeps the canonical requirements in its own `specs/` directory. Administrivia references those specs and hosts the page, panel, template, static asset, and route code needed to make the surface usable.

This keeps subsystem requirements close to the models and services they govern while still letting TAP grow a coherent administrative UI.

## Goals

|    |                  |                                                                 |
| :---: | ---           | ---                                                             |
| 1. | Administrivia Shell | Provide a first-party home for TAP operator pages and panels |
| 2. | Spec-Referenced | Point each hosted surface to the canonical spec that owns its behavior |
| 3. | Subsystem-Neutral | Host administration for core apps and plugins without taking over their domain semantics |
| 4. | TAP-Native       | Use TAP pages, panels, GRIFT, and service-layer patterns where practical |

## Requirements

| RID | Name | Status | Notes |
| --- | --- | :---: | --- |
| req-administrivia-v0-scope | [Plugin Scope](#plugin-scope) | Implemented | Defines Administrivia as the first-party TAP operator-pages plugin |
| req-administrivia-v0-spec-index | [Hosted Surface Spec Index](#hosted-surface-spec-index) | Implemented | Administrivia keeps references to canonical subsystem specs |
| req-administrivia-v0-code-layout | [Code Layout](#code-layout) | Implemented | Hosted subsystem code lives under app/package-aligned directories |
| req-administrivia-v0-navigation | [Administrivia Navigation](#administrivia-navigation) | Implemented | Administrivia pages should be reachable through stable TAP Web routes and navigation |
| req-administrivia-v0-plugin-contrib | [Plugin-Contributed Administrivia Paths](#plugin-contributed-administrivia-paths) | Backlog | Formalize how other plugins contribute `/administrivia/...` pages |
| req-administrivia-v0-plugin-facts | [Plugin Detail Facts](#plugin-detail-facts) | Implemented | One resolver derives every per-plugin fact, in three states |
| req-administrivia-v0-plugin-detail-page | [Per-Plugin Detail Page](#per-plugin-detail-page) | Implemented | A routable detail page for one installed plugin |
| req-administrivia-v0-plugin-detail-panel | [Plugin Detail Panel](#plugin-detail-panel) | Implemented | Panel type rendering one plugin's identity, surfaces, dependencies and activity |
| req-administrivia-v0-plugin-taxonomy-panel | [Plugin Taxonomy Panel](#plugin-taxonomy-panel) | Implemented | Panel type drawing the declared type-level graph with a live-count overlay |

### Plugin Scope
----
RID: `req-administrivia-v0-scope`

Status: `Implemented`

Administrivia hosts administrative pages, panels, templates, static assets, and supporting view or panel code for TAP's operator-facing UI.

Administrivia should be used when a feature is primarily an administrative or operator surface and when TAP's page/panel system is a better fit than Django admin. Django admin remains useful for low-level development, emergency inspection, and Django-standard model administration, but it is not the desired long-term UX for normal TAP administration.

Administrivia must not become a dumping ground for subsystem semantics. If a page administers `tap_cares`, `tap_grid`, `tap_api`, or another owning app/plugin, the owning subsystem's spec defines the behavior and Administrivia implements the surface.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-administrivia-v0-scope-1 | First-Party Administrivia Plugin | Implemented | Administrivia is documented as TAP's first-party operator-pages plugin. | |
| req-administrivia-v0-scope-2 | Subsystem Semantics Stay Owned | Implemented | Administrative behavior for another subsystem remains specified in that subsystem's specs. | |
| req-administrivia-v0-scope-3 | Django Admin Not Primary UX | Implemented | Specs may use Administrivia pages instead of Django admin for operator workflows. | |

### Hosted Surface Spec Index
----
RID: `req-administrivia-v0-spec-index`

Status: `Implemented`

Administrivia maintains a lightweight index of administrative surfaces it hosts and points each one at its canonical owning spec.

This index is intentionally not a duplicate specification. It should answer: where is the code, where is the route, and which spec owns the behavior?

| Surface | Code Location | Canonical Spec | Route |
| --- | --- | --- | --- |
| Administrivia landing/grid overview | `plugins/administrivia/grift/grid-landing.grift.json` | This spec; TAP Web page/panel specs | `/administrivia` |
| CARES homepage (collectors table) | `plugins/administrivia/tap_cares/panels/collector_table/`, `plugins/administrivia/grift/cares-administrivia.grift.json` | `tap_cares/specs/spec-tap-cares-administrivia.md` | `/administrivia/cares` |
| CARES collector detail | `plugins/administrivia/tap_cares/panels/collector_detail/`, `plugins/administrivia/grift/cares-administrivia.grift.json` | `tap_cares/specs/spec-tap-cares-administrivia.md` | `/administrivia/cares/collector?entity_id=<uuid>` |
| CARES run detail (per-run deep dive) | `plugins/administrivia/tap_cares/panels/run_detail/`, `plugins/administrivia/grift/cares-administrivia.grift.json` | `tap_cares/specs/spec-tap-cares-administrivia.md` | `/administrivia/cares/run?entity_id=<job_uuid>` |
| Installed plugins table | `tap_plugin/administrivia/panels/plugin_status/`, `tap_plugin/administrivia/grift/plugins-page.grift.json` | `tap_plugins/specs/spec-plugin-architecture.md` (`req-plugin-arch-install-registry-5`) | `/administrivia/plugins` |
| Per-plugin detail + taxonomy | `tap_plugin/administrivia/panels/plugin_detail/`, `tap_plugin/administrivia/panels/plugin_taxonomy/`, `tap_plugin/administrivia/plugin_facts.py`, `tap_plugin/administrivia/grift/plugin-detail-page.grift.json` | This spec (`req-administrivia-v0-plugin-facts` / `-detail-page` / `-detail-panel` / `-taxonomy-panel`) | `/administrivia/plugin?slug=<slug>` |
| User management (roster + control) — *Proposed, not yet built* | _planned_ `plugins/administrivia/tap_auth/panels/...` | `tap_auth/specs/spec-tap-auth-user-management-v0.md` | _planned_ `/administrivia/users` |

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-administrivia-v0-spec-index-1 | Hosted Surfaces Listed | Implemented | Administrivia lists the administrative surfaces it hosts. | |
| req-administrivia-v0-spec-index-2 | Canonical Specs Linked | Implemented | Each hosted subsystem surface references the spec that owns its requirements. | |
| req-administrivia-v0-spec-index-3 | No Requirement Duplication | Implemented | The index summarizes ownership and routing without duplicating subsystem requirements. | |

### Code Layout
----
RID: `req-administrivia-v0-code-layout`

Status: `Implemented`

Administrivia code for subsystem-specific Administrivia surfaces should live under directories named after the exact Django app or plugin package that owns the administered subsystem.

Expected v0 pattern:

```text
plugins/administrivia/
  tap_cares/
    panels/
    templates/
    static/
```

The directory uses `tap_cares`, matching the Django app/package name. Human-facing copy may continue to use "tap-cares" or "CARES" where that reads better.

When a hosted surface needs GRIFT page or panel seeds, those seeds may live in `plugins/administrivia/grift/` or a subsystem subdirectory if the plugin's GRIFT loader supports it. The route and code location should be documented in the hosted surface index.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-administrivia-v0-code-layout-1 | App-Aligned Directories | Implemented | Subsystem-specific Administrivia implementation code lives under `plugins/administrivia/<app-or-plugin-package>/`. | |
| req-administrivia-v0-code-layout-2 | Code Location Documented | Implemented | Each hosted surface records its implementation location in the hosted surface index. | |
| req-administrivia-v0-code-layout-3 | GRIFT Location Clear | Implemented | GRIFT seeds for administrative pages have a documented plugin-owned location. | |

### Administrivia Navigation
----
RID: `req-administrivia-v0-navigation`

Status: `Implemented`

Administrivia pages should have stable TAP Web routes. Top-level Administrivia surfaces should be reachable from `/administrivia` or a future Administrivia navigation menu.

Subsystem surfaces should use route prefixes that make ownership obvious to humans:

```text
/administrivia/cares
/administrivia/cares/collector
```

Route design should follow TAP Web page slug and parameter conventions. If a desired route shape cannot be represented by the current TAP Web page routing model, the owning subsystem spec should explicitly choose between query parameters, a new parameterized page route, or a small custom view.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-administrivia-v0-navigation-1 | Stable Routes | Implemented | Administrivia surfaces expose stable TAP Web routes. | |
| req-administrivia-v0-navigation-2 | Prefix Conventions | Implemented | Subsystem Administrivia pages use `/administrivia/<subsystem>` route prefixes. | |
| req-administrivia-v0-navigation-3 | Routing Gaps Named | Implemented | Specs call out when current TAP Web routing cannot express a desired URL shape. | |

### Plugin-Contributed Administrivia Paths
----
RID: `req-administrivia-v0-plugin-contrib`

Status: `Backlog`

Domain plugins should eventually be able to ship their own Administrivia pages under the shared `/administrivia/...` route space without moving all implementation code into the Administrivia plugin.

The current TAP Web and plugin GRIFT machinery already permits a plugin to declare a Page with a slug such as:

```text
/administrivia/ksi
```

provided the slug is unique and does not use a TAP Web reserved prefix. Current reserved prefixes are `/admin`, `/api`, and `/panel`; `/administrivia` is not reserved.

What remains unspecified is the governance and discovery contract:

- who owns a contributed Administrivia route
- how collisions under `/administrivia/...` are detected before import
- how contributed pages appear in Administrivia navigation
- whether Administrivia keeps a central hosted-surface index for externally contributed pages
- whether route prefixes should use plugin package names, human-friendly slugs, or declared Administrivia aliases
- how specs in the contributing plugin reference Administrivia as the hosting route family

Until this backlog requirement is implemented, first-party subsystem Administrivia surfaces may live in `plugins/administrivia/<app-or-plugin-package>/`, and domain plugins may still seed ordinary TAP Web pages under `/administrivia/...` when the route ownership is explicitly reviewed.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-administrivia-v0-plugin-contrib-1 | Contribution Contract Defined | Backlog | A future spec defines how non-Administrivia plugins contribute `/administrivia/...` pages. | |
| req-administrivia-v0-plugin-contrib-2 | Collision Handling | Backlog | Contributed Administrivia paths have a deterministic collision detection and resolution process. | |
| req-administrivia-v0-plugin-contrib-3 | Navigation Integration | Backlog | Contributed Administrivia paths can appear in Administrivia navigation without hand-editing a central page each time. | |
| req-administrivia-v0-plugin-contrib-4 | Spec Ownership Preserved | Backlog | Contributed pages keep their canonical behavioral specs in the owning plugin or app. | |

### Plugin Detail Facts
----
RID: `req-administrivia-v0-plugin-facts`

Status: `Implemented`

Every per-plugin fact the detail page and the taxonomy panel render is derived **once**, in
`tap_plugin/administrivia/plugin_facts.py`. Two panels render the same plugin from two angles; a
second derivation of "how many `zizmor__finding` entities exist" is a second place for that number
to be wrong. The panels are presentation only.

#### Implementation

`build_plugin_facts(slug: str) -> PluginFacts` resolves, in this order:

1. **Identity, provenance, surfaces, dependencies** — `tap_plugins.report.get_plugin_report()`.
   That service function authorizes `plugins.read` before building, so the capability gate stays in
   the service layer and is never re-implemented here. The plugin record is selected out of
   `report["plugins"]` by slug; an unknown slug is a clean "not installed" state, not an exception.
2. **Declared types** — the plugin's `AppConfig` manifest (`tap_plugins.manifest.PluginManifest`),
   which is the only surface that knows what the plugin *declared* as opposed to what registered.
   `manifest.models` gives the node-type slugs, `manifest.edges` the edge-type slugs (plus the
   `.edge.json`-derived `sources`/`targets` already parsed into `EdgeEntry`).
3. **Registered types** — `tap_grid.models.EntityType`, joined to the declared slugs. `kind == ""`
   means *not yet classified* and is reported as unknown, never as node.
4. **Endpoint topology** — `tap_grid.services.describe_edge_type()`, the service-layer discovery
   verb, which reads the same in-process constraints registry the plugin loader wrote. The registry
   is process memory: `EntityType` carries no sources/targets column, so there is nothing on the
   grid to read and nothing is persisted to make one. `describe_edge_type` is gated on
   `grid.discover`; a refusal degrades that edge's endpoints to *not observable* rather than
   failing the page.
5. **Live counts** — `Entity` grouped by `entity_type` for node types, `Edge` grouped by
   `edge_type` for edge types.
6. **Activity** — `tap_cares.models.Collector` rows whose `collector_registry` is scoped to the
   plugin slug, each with its most recent `CollectionJob`; and recent `tap_grid.models.Batch` rows
   whose `source` is `plugins.<slug>`.

##### Three states, never two

Every count and every endpoint list resolves to exactly one of three states, and the distinction is
the point of the surface:

| State | Rendered as | Means |
| --- | --- | --- |
| `observed` | the number | Registered, and N instances exist on this grid |
| `never_observed` | `declared, never observed` | Registered, zero instances — the type exists and nothing has ever used it |
| `not_observable` | `not observable` | Declared in the manifest but absent from `EntityType`, or the read was refused |

Absence of evidence must never render as evidence of absence: a type that failed to register is
*not* a type with zero instances, and the surface must not let a reader confuse them.

##### Named deviations

- **Gryphon cannot express this read.** COUNT is implemented but its executor requires at least one
  edge in the MATCH pattern, so a node-only count grouped by `entity_type` is rejected at parse
  time. The counts are therefore ORM aggregates. `Entity` is deliberately outside the ORM read
  backstop; `Edge` is inside it and the aggregate requires `grid.read`, which the panel view
  authorizes before any panel type resolves. Closing this belongs to Gryphon, not to Administrivia.
- **The manifest is read off the `AppConfig`.** `tap_plugins.report` reads it the same way. When the
  plugin report grows a declared-type-slug field, this module reads that field instead and nothing
  else changes.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-administrivia-v0-plugin-facts-1 | Single Derivation | Implemented | Both panels obtain every per-plugin fact from `build_plugin_facts`; neither queries the grid itself. | |
| req-administrivia-v0-plugin-facts-2 | Service-Gated Identity | Implemented | Identity/provenance/surfaces/dependencies come from `get_plugin_report()`, so `plugins.read` is enforced in the service layer. | |
| req-administrivia-v0-plugin-facts-3 | Topology From The Service Layer | Implemented | Edge endpoints come from `tap_grid.services.describe_edge_type`; nothing reads `tap_grid.constraints` directly and no migration persists the topology. | |
| req-administrivia-v0-plugin-facts-4 | Three Count States | Implemented | Each type resolves to `observed`, `never_observed` or `not_observable`, and the three are distinguishable by a reader. | |
| req-administrivia-v0-plugin-facts-5 | Unclassified Kind Is Unknown | Implemented | `EntityType.kind == ""` is reported as unknown, never defaulted to node. | |
| req-administrivia-v0-plugin-facts-6 | Unknown Slug Degrades | Implemented | A slug that is not installed yields a facts object marked not-found; no exception reaches the page. | |
| req-administrivia-v0-plugin-facts-7 | Refused Topology Degrades | Implemented | An `AuthzError` from `describe_edge_type` marks that edge's endpoints `not_observable` and the page still renders. | |

### Per-Plugin Detail Page
----
RID: `req-administrivia-v0-plugin-detail-page`

Status: `Implemented`

One page renders one installed plugin, reached from its row in the installed-plugins table.

#### Implementation

Route: `/administrivia/plugin?slug=<plugin-slug>`.

**Routing gap, named per `req-administrivia-v0-navigation-3`.** The desired shape is
`/administrivia/plugin/<slug>`, and TAP Web cannot express it. `tap_web/urls.py` ends in a
`<path:page_slug>` catch-all matched against `Page.slug` by exact string; the only
path-parameterized routes are a hardcoded block of `samsite/<type>/<uuid>` entries, and the root
urlconf includes no plugin-contributed urlconf, so a plugin cannot register one. Of the three
options that requirement offers — query parameters, a new parameterized page route, or a small
custom view — this spec chooses **query parameters**, matching the existing
`/administrivia/cares/collector?entity_id=<uuid>` surface. A generic path-parameter page route is
core work, and it should be taken for the whole page system rather than for this one page.

The Page is seeded `discoverable: false`: a per-item detail page is reached from its parent table,
not from navigation.

**Section order is the page's, not a panel's.** The reader meets identity and surfaces, then the
TAXONOMY DIAGRAM, then dependencies and everything else. The diagram is what makes the page worth
opening, so it sits above the fold rather than below two dependency tables. The page expresses that
by mounting `plugin_detail` **twice** — each instance naming the sections it renders in its
`sections` config (head: `identity`, `surfaces`; body: `dependencies`, `types`, `activity`,
`manifest`) — with the taxonomy panel in the row between them. The panel type therefore never needs
to know a graph exists; a page that wants a different arrangement changes its own layout and
nothing else. Both detail instances set `hide_header`: the identity block is the page's heading,
and a "Plugin Detail" bar above it was redundant.

The `plugin_status` table gains a link formatter on its `Plugin` column pointing at this route, so
a row is no longer a dead end.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-administrivia-v0-plugin-detail-page-1 | Page Routable | Implemented | `/administrivia/plugin?slug=<slug>` renders for every installed plugin. | |
| req-administrivia-v0-plugin-detail-page-2 | Reached From The Table | Implemented | Each `/administrivia/plugins` row links to the detail page for that plugin. | |
| req-administrivia-v0-plugin-detail-page-3 | Out Of Navigation | Implemented | The page is seeded `discoverable: false` and does not appear in nav or the palette. | |
| req-administrivia-v0-plugin-detail-page-4 | Routing Gap Recorded | Implemented | The spec states why the route is a query parameter rather than a path segment. | |
| req-administrivia-v0-plugin-detail-page-5 | Missing Slug Is A State | Implemented | The page with no `slug`, or an unknown one, renders a helpful empty state rather than an error page. | |
| req-administrivia-v0-plugin-detail-page-6 | Diagram Above The Fold | Implemented | The rendered order is identity → surfaces → taxonomy diagram → dependencies → the rest. | |
| req-administrivia-v0-plugin-detail-page-7 | Order Owned By The Page | Implemented | The order is expressed in the page layout and instance `sections` config, not hard-coded in a panel template. | |

### Plugin Detail Panel
----
RID: `req-administrivia-v0-plugin-detail-panel`

Status: `Implemented`

Panel type `plugin_detail` renders everything about one plugin that is not the taxonomy graph.

#### Implementation

- Class: `PluginDetailPanelType` in `tap_plugin/administrivia/panels/plugin_detail/__init__.py`,
  registered as `plugin_detail` in `AdministriviaConfig.ready()`.
- `view = "administrivia/panels/plugin_detail.html"`, `css = ["administrivia/css/plugin_detail.css"]`,
  no JS — the panel is server-rendered.
- `get_view_context` reads `request.GET["slug"]` and returns `build_plugin_facts(slug)` rendered
  into template context. It performs no data access of its own.

Sections, in order:

1. **Identity header** — name, slug, distribution, version + short commit, source, mode, load
   health. Source and mode render as pills; a degraded plugin is visually distinct.
2. **Surfaces** — declared vs loaded for models, edges, editors, searches and GRIFT. A surface whose
   loaded count is below its declared count carries an explicit gap indicator naming the shortfall;
   a surface whose loaded count is not measured renders *not observable*, not `0`.
3. **Dependencies** — both directions. `depends_on` carries each dependency's intent note and
   minimum version; `required_by` is the inversion. Undeclared observed imports are surfaced as a
   warning, because an undeclared import is a load-order defect waiting to happen.
4. **Node types** and **edge types** — one row per declared type: slug, name, kind, and its count in
   one of the three states. Edge-type rows also carry source and target endpoint lists.
5. **Collectors** — every collector scoped to the plugin, with its last run's status and time.
6. **Recent batches** — the most recent batches whose `source` is `plugins.<slug>`, with status and
   start time.
7. **GRIFT bundles** and **boot records** declared in the manifest.

Every section renders an explicit empty state; a plugin that declares no edges says so.

**Sections are configurable.** `config.sections` names which of the six sections
(`identity`, `surfaces`, `dependencies`, `types`, `activity`, `manifest`) an instance renders;
unknown names are ignored and canonical order is always preserved. An instance with no `sections`
renders all six — a panel dropped on a page with no configuration must still be complete, never
silently blank. This is what lets the page interleave the taxonomy diagram between `surfaces` and
`dependencies` without the panel knowing the diagram exists.

**The node-type and edge-type tables carry a text filter.** Rows are narrowed as the reader types,
client-side over rows the server already sent — it never fetches, sorts, or changes what a row
says. The shape is deliberately the one `git_serious`'s query pack already uses
(`spec-git-serious-query-pack`): a pre-lowercased `data-text` attribute per row, an `indexOf`
match, a live "N of M shown" count, and an explicit empty row. An empty result is therefore a
STATED state rather than a blank table — the same three-states discipline the counts follow.
Each table's box is scoped to its own section, and each `data-text` is derived from exactly what
its row DISPLAYS (`TypeFact.search_text`): a filter that matched on text the reader cannot see
would be lying about what it looked at, so edge descriptions are rendered (clamped, full text on
hover) rather than searched invisibly.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-administrivia-v0-plugin-detail-panel-1 | Panel Type Registered | Implemented | `plugin_detail` is registered in `ready()` and its template renders. | |
| req-administrivia-v0-plugin-detail-panel-2 | Identity And Provenance | Implemented | The header renders name, slug, distribution, version, commit, source, mode and load health. | |
| req-administrivia-v0-plugin-detail-panel-3 | Declared-Vs-Loaded Gap Visible | Implemented | A surface with loaded < declared carries a visible gap indicator; an unmeasured surface reads *not observable*. | |
| req-administrivia-v0-plugin-detail-panel-4 | Both Dependency Directions | Implemented | `depends_on` and `required_by` both render, with notes and undeclared-import warnings. | |
| req-administrivia-v0-plugin-detail-panel-5 | Types With Counts | Implemented | Node and edge types render with their count state and, for edges, their endpoints. | |
| req-administrivia-v0-plugin-detail-panel-6 | Activity | Implemented | Collectors with last-run status, and recent batches, render for a plugin that has them. | |
| req-administrivia-v0-plugin-detail-panel-7 | Empty States | Implemented | Every section renders an explicit empty state rather than an empty container. | |
| req-administrivia-v0-plugin-detail-panel-8 | Configurable Sections | Implemented | `config.sections` selects which sections an instance renders; an unconfigured instance renders all of them in canonical order. | |
| req-administrivia-v0-plugin-detail-panel-9 | Per-Table Filter | Implemented | The node-type and edge-type tables each narrow by text as the reader types, independently of each other. | |
| req-administrivia-v0-plugin-detail-panel-10 | Filter States Its Result | Implemented | A live "N of M shown" count and an explicit empty row mean a filter matching nothing is a stated state, not a blank table. | |
| req-administrivia-v0-plugin-detail-panel-11 | Filter Matches What Is Shown | Implemented | Each row's searchable text is derived from what that row displays; the filter never matches on text the reader cannot see. | |

### Plugin Taxonomy Panel
----
RID: `req-administrivia-v0-plugin-taxonomy-panel`

Status: `Implemented`

Panel type `plugin_taxonomy` draws the **type-level** graph a plugin declares — node types as
nodes, declared edge types as directed edges — with the live instance counts painted on. It exists
so a human can see the shape of the dictionary a plugin defines at a glance, on a grid that holds
no data at all.

#### Implementation

- Class: `PluginTaxonomyPanelType` in `tap_plugin/administrivia/panels/plugin_taxonomy/__init__.py`,
  registered as `plugin_taxonomy` in `AdministriviaConfig.ready()`.
- `view = "administrivia/panels/plugin_taxonomy.html"`,
  `css = ["administrivia/css/plugin_taxonomy.css"]`,
  `js = ["tap_viz/js/lib/cytoscape.min.js", "administrivia/js/plugin_taxonomy.js"]`.
- `config_defaults = {"height": "520px"}`; `height` is validated against a narrow allowlist before
  it reaches an inline style attribute.

**This is not the `tap_viz` graph panel, and must not be built on it.** That panel is
search-/entity-bound: it executes a Search and draws the grid entities that come back. A type-level
graph has no entities — its nodes are rows of `tap_entity_type` and its edges are manifest
declarations. The panel therefore synthesizes the Cytoscape element list server-side from
`build_plugin_facts` and hands it to Cytoscape directly. Cytoscape itself is the already-vendored
`tap_viz/js/lib/cytoscape.min.js`; no second copy is introduced.

Drawing rules:

- One node per node type that participates: the plugin's own declared node types, plus any
  **foreign** endpoint type named by one of its declared edges. A foreign endpoint is drawn because
  a cross-plugin edge is the interesting half of the picture — `zizmor__finding` →
  `github_core__github_workflow` is the whole reason the panel exists.
- Own types and foreign types are visually distinct (fill and border), and foreign types carry their
  owning plugin as a second label line.
- One directed edge per declared (source, target) pair of each declared edge type; an edge type with
  wildcard endpoints is drawn against a synthetic `any` node rather than silently omitted.
- Every node carries its count state as a badge: a number, `0 · never observed`, or `not observable`.
  A never-observed type is additionally drawn dashed, so a grid where nothing has been collected
  reads at a glance as a complete dictionary with nothing in it — which is exactly what it is.
- A legend names every visual distinction the panel makes. A reader must not have to infer that
  dashed means never-observed.

##### Full screen

The panel carries a control that takes the graph full screen, because a dictionary of any size
stops being readable in a 620px box.

- The **stage** is the fullscreened element, not the canvas, so the **legend travels with the
  graph**. At full size the legend is worth more, not less: it is what makes the violet
  cross-plugin endpoints and the dashed never-observed types readable. In full screen it stops
  being a floating overlay and becomes a bar beneath the canvas — as an overlay it sat on top of
  whatever the layout put in that corner, and a key that hides the thing it explains is worse than
  no key.
- **Cytoscape is resized and re-fitted in BOTH directions.** It caches its container's box, so
  without `cy.resize()` it draws into a stale rectangle — clipped entering, marooned in a corner
  leaving. The resize happens two animation frames after the change, because measuring in the same
  tick reads the old box.
- **State follows the document, never the click.** Every label, `aria-pressed` and class change
  hangs off `fullscreenchange`. `requestFullscreen()` returns a promise that can reject, and
  Escape leaves full screen without touching the button at all; a button claiming a state the
  document is not in is a small lie.
- **The way out lives inside the stage.** The bar's button is outside the fullscreened subtree and
  is unreachable once full screen starts, so an "Exit full screen" label up there would name a
  control nobody can press. A real exit button sits inside the stage, visible only in full screen,
  and names the Escape key beside itself.
- The control ships hidden and is revealed only where the Fullscreen API is actually available. A
  control that cannot do the thing it names is worse than no control. It carries a visible focus
  ring and an `aria-label` that states the action its current state affords.

#### Acceptance Criteria

| ACID | Title | Status | Description | Notes |
| --- | --- | :---: | --- | --- |
| req-administrivia-v0-plugin-taxonomy-panel-1 | Panel Type Registered | Implemented | `plugin_taxonomy` is registered in `ready()` and its template renders. | |
| req-administrivia-v0-plugin-taxonomy-panel-2 | Declared, Not Sampled | Implemented | The graph is built from manifest declarations and the constraints registry; it draws correctly on a grid with zero instances. | |
| req-administrivia-v0-plugin-taxonomy-panel-3 | Cross-Plugin Endpoints Distinguished | Implemented | Foreign endpoint types are visually distinct and labelled with their owning plugin. | |
| req-administrivia-v0-plugin-taxonomy-panel-4 | Counts Overlay | Implemented | Every node carries its count in one of the three states, and a never-observed type is visibly marked. | |
| req-administrivia-v0-plugin-taxonomy-panel-5 | Legend Present | Implemented | A legend names every visual distinction the graph makes. | |
| req-administrivia-v0-plugin-taxonomy-panel-6 | Not Built On The Viz Graph Panel | Implemented | The panel synthesizes its own element list and does not depend on `tap_viz`'s search-bound graph panel. | |
| req-administrivia-v0-plugin-taxonomy-panel-7 | Empty Declaration State | Implemented | A plugin that declares no types renders an explicit empty state, not an empty canvas. | |
| req-administrivia-v0-plugin-taxonomy-panel-8 | Full Screen | Implemented | A control takes the graph full screen and back, and the graph is re-measured and re-fitted in both directions. | |
| req-administrivia-v0-plugin-taxonomy-panel-9 | Legend Travels And Does Not Occlude | Implemented | The legend is inside the fullscreened element and, at full size, occupies a bar rather than overlaying the graph. | |
| req-administrivia-v0-plugin-taxonomy-panel-10 | Button State Is Truthful | Implemented | Label, `aria-pressed` and styling are driven by `fullscreenchange`, so a rejected request or an Escape exit cannot leave the control claiming the wrong state. | |
| req-administrivia-v0-plugin-taxonomy-panel-11 | Reachable Way Out | Implemented | An exit control lives inside the fullscreened element, is revealed only in full screen, and names the Escape key. | |
| req-administrivia-v0-plugin-taxonomy-panel-12 | Unsupported Means Absent | Implemented | The control stays hidden where the Fullscreen API is unavailable rather than offering an action it cannot perform. | |

## Out Of Scope (v0)

- Writing anything. Every Administrivia plugin surface described here is read-only; nothing mutates
  plugin state, installs, uninstalls or reloads a plugin from the web.
- Persisting the edge-endpoint topology to the grid. `EntityType` gains no sources/targets column;
  the topology stays in the in-process constraints registry read through the service layer. Whether
  the topology belongs on the grid is a grid design decision, not a page's to make.
- A generic path-parameter page route. Named as a routing gap above; it is core `tap_web` work.
- A cross-plugin taxonomy — the whole instance's type graph in one picture. Each detail page draws
  one plugin's neighbourhood.

## Future

- Define a first-class Administrivia navigation menu once `tap_web` navigation behavior stabilizes.
- Decide whether Administrivia should own shared UI primitives such as status badges, empty states, and run-history tables.
- Consider an Administrivia landing page that groups hosted surfaces by subsystem and health state.
- Draw the instance-wide taxonomy: every installed plugin's types in one graph, plugin membership as
  the grouping. The per-plugin panel is the tractable first half of that picture.
- Let a taxonomy node navigate: a click on a node type opens a filtered list of its instances.
- Surface the pages and panels a plugin seeds, derived from the entities its GRIFT batches produced.
