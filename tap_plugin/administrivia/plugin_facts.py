"""Per-plugin facts — the single derivation behind the plugin detail page.

Two panels render one plugin from two angles: `plugin_detail` as prose and tables,
`plugin_taxonomy` as a type-level graph. They read the SAME facts object. A second
derivation of "how many `zizmor__finding` entities exist" is a second place for that
number to be wrong, so there is exactly one (`req-administrivia-v0-plugin-facts`).

Where each fact comes from:

- identity / provenance / surfaces / dependencies — `tap_plugins.report.get_plugin_report()`.
  That service function authorizes `plugins.read` BEFORE building, so the capability gate
  lives in the service layer and is never re-implemented here.
- declared types — the plugin's `tap-plugin.toml` manifest off its `AppConfig`. This is the
  only surface that knows what a plugin DECLARED, as opposed to what actually registered;
  the difference between the two is the whole point of the page.
- registered types — `tap_grid.models.EntityType`.
- edge endpoint topology — `tap_grid.services.describe_edge_type()`, the service-layer
  discovery verb. The topology lives ONLY in the in-process constraints registry the plugin
  loader wrote: `EntityType` has no sources/targets column and this module adds none.
- live counts — `Entity` grouped by `entity_type`, `Edge` grouped by `edge_type`.
- activity — `tap_cares` collectors scoped to the plugin, and `tap_grid` batches whose
  `source` is `plugins.<slug>`.

THREE STATES, NEVER TWO. Every count and every endpoint list is `observed` (a number),
`never_observed` (registered, nothing has ever used it) or `not_observable` (declared but
never registered, or the read was refused). A type that failed to register is not a type
with zero instances, and absence of evidence must never render as evidence of absence.

Named deviations:

- Gryphon cannot express these counts. COUNT is implemented, but its executor requires at
  least one edge in the MATCH pattern, so a node-only count grouped by `entity_type` is
  rejected before it runs. The counts are ORM aggregates until Gryphon grows a node-only
  aggregate path — which is Gryphon's work, not Administrivia's (unified-systems-com/tap#465).
  `Entity` is deliberately outside the ORM read backstop; `Edge` is inside it and needs `grid.read`, which
  `tap_web.views.panel_view` authorizes before any panel type resolves.
- The manifest is read off the `AppConfig` (`tap_plugins.report` reads it the same way).
  When the plugin report grows a declared-type-slug field, this module reads that instead.

Read-only: no grid writes, no mutation of any kind.

Spec: specs/spec-administrivia-v0.md req-administrivia-v0-plugin-facts.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tap_plugins.manifest import PluginManifest

logger = logging.getLogger(__name__)

# The three states a count or an endpoint list can be in. Exported so templates and
# tests name them rather than matching strings (req-administrivia-v0-plugin-facts-4).
OBSERVED = "observed"
NEVER_OBSERVED = "never_observed"
NOT_OBSERVABLE = "not_observable"

# A plugin slug is a Django AppConfig label: an identifier, never free text. Both panels
# take it straight off the query string, so it is validated HERE — once — before it reaches
# a query, a log line or a message. Anything else is refused as a bad slug rather than
# passed along: an unconstrained value in a log record lets a caller forge log entries
# (Sonar S5145), and the cheap edge is to never let the value through in the first place.
_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$", re.IGNORECASE)


def normalize_slug(raw: str) -> str:
    """Return `raw` if it is a syntactically valid plugin slug, else the empty string."""
    candidate = (raw or "").strip()
    return candidate if _SLUG_RE.match(candidate) else ""


# Why a whole SECTION may be unreadable. A section that could not be read is not a section
# with nothing in it, and the difference is the entire point of this page. These strings are
# rendered to the operator, so they say what went wrong and what it does NOT mean.
MANIFEST_UNAVAILABLE = (
    "this plugin's manifest is not available on its AppConfig, so what it declares cannot be "
    "read — this is not the same as declaring nothing"
)
CATALOG_UNREADABLE = "the type catalog could not be read, so registration could not be checked"
COLLECTORS_UNREADABLE = "the collector read failed, so whether this plugin ships collectors is unknown"
BATCHES_UNREADABLE = "the batch read failed, so this plugin's produced batches are unknown"
RUNS_UNREADABLE = "this collector's run history could not be read"


# How many batches the detail page shows. A plugin with a busy collector produces
# thousands; the page wants the recent shape, not the archive.
RECENT_BATCH_LIMIT = 12


@dataclass(frozen=True)
class CountState:
    """One count in one of the three states.

    `value` is meaningful only when `state == OBSERVED`. `label` is the display string;
    `reason` explains a `NOT_OBSERVABLE` so the reader is told WHY rather than being left
    to guess whether it means zero.
    """

    state: str
    value: int | None = None
    reason: str = ""

    @property
    def label(self) -> str:
        if self.state == OBSERVED:
            return f"{self.value:,}"
        if self.state == NEVER_OBSERVED:
            return "declared, never observed"
        return "not observable"

    @property
    def is_observed(self) -> bool:
        return self.state == OBSERVED

    @property
    def is_never_observed(self) -> bool:
        return self.state == NEVER_OBSERVED

    @property
    def is_not_observable(self) -> bool:
        return self.state == NOT_OBSERVABLE


def _absent_reason(registered: bool, catalog_readable: bool, noun: str) -> str:
    """Say WHY a count is not observable, truthfully.

    "Declared but not registered" is a strong claim, and it is false when the type catalog
    simply could not be read — the type may be registered perfectly well. Distinguishing the
    two is the same discipline as distinguishing zero from unknown.
    """
    if not catalog_readable:
        return CATALOG_UNREADABLE
    if not registered:
        return "declared in the manifest but not registered in the type catalog"
    return f"the {noun} count could not be read"


def _count_state(registered: bool, count: int | None, *, absent_reason: str) -> CountState:
    """Fold (is it registered, how many are there) into one of the three states."""
    if not registered or count is None:
        return CountState(NOT_OBSERVABLE, reason=absent_reason)
    if count == 0:
        return CountState(NEVER_OBSERVED, value=0)
    return CountState(OBSERVED, value=count)


@dataclass(frozen=True)
class TypeFact:
    """One declared node or edge type, with everything the two panels need about it."""

    slug: str
    name: str
    kind: str  # "node" | "edge" | "" (unclassified — unknown, NEVER defaulted to node)
    description: str
    registered: bool
    count: CountState
    owner_slug: str  # plugin slug that owns the type ("" when unknown)
    # Edge types only. `None` means the endpoint list was not observable (wildcard is a
    # LIST containing the sentinel, which is a real declaration and renders as such).
    sources: list[str] | None = None
    targets: list[str] | None = None
    endpoints_reason: str = ""

    @property
    def kind_label(self) -> str:
        return self.kind or "unclassified"

    @property
    def search_text(self) -> str:
        """Lowercase haystack the per-table filter matches against.

        Derived here rather than in the template so the filter searches exactly what the
        row displays — a row that shows an endpoint the filter cannot find is a filter
        that lies about what it looked at. Lowercased once, server-side, because the
        client compares with a plain `indexOf` (the pattern git_serious's query pack uses).
        """
        parts = [self.slug, self.name, self.kind_label, self.description, self.owner_slug, self.count.label]
        parts += self.sources or []
        parts += self.targets or []
        return " ".join(p for p in parts if p).lower()

    @property
    def endpoints_observable(self) -> bool:
        """Whether this edge type's declared endpoints could be read at all.

        Exists because Django templates have no `None` literal: a template cannot ask
        `sources is None`, and an empty list ("declares none") must not be confused with
        an unreadable one ("we could not look").
        """
        return self.sources is not None and self.targets is not None


@dataclass(frozen=True)
class CollectorFact:
    """One collector the plugin ships, with its most recent run."""

    entity_id: str
    name: str
    registry_key: str
    local_key: str
    last_status: str
    last_status_label: str
    last_run_at: Any
    last_summary: str
    run_count: int
    # A collector whose run history could not be read has an UNKNOWN last run, not "never
    # run". Carried per collector so one unreadable history does not blank the section.
    runs_observable: bool = True
    runs_reason: str = ""


@dataclass(frozen=True)
class BatchFact:
    entity_id: str
    name: str
    status: str
    started_at: Any
    closed_at: Any
    source: str = ""


@dataclass
class PluginFacts:
    """Everything the detail page and the taxonomy panel know about one plugin."""

    slug: str
    found: bool = False
    error: str = ""
    record: dict[str, Any] = field(default_factory=dict)
    node_types: list[TypeFact] = field(default_factory=list)
    edge_types: list[TypeFact] = field(default_factory=list)
    collectors: list[CollectorFact] = field(default_factory=list)
    batches: list[BatchFact] = field(default_factory=list)
    grift_bundles: list[dict[str, str]] = field(default_factory=list)
    boot_records: list[dict[str, str]] = field(default_factory=list)
    # slug -> owning plugin slug, for every type this plugin's edges touch (including
    # foreign endpoints the taxonomy panel draws).
    type_owners: dict[str, str] = field(default_factory=dict)
    manifest_available: bool = False
    # section key -> why it could not be read. A key present here means the section's list is
    # EMPTY BECAUSE WE COULD NOT LOOK, and the surface must say so instead of rendering an
    # empty state. Keys: "types", "grift", "boot_records", "collectors", "batches".
    # (Templates read this as `facts.unobservable.<key>`.)
    unobservable: dict[str, str] = field(default_factory=dict)

    @property
    def has_declared_types(self) -> bool:
        return bool(self.node_types or self.edge_types)

    @property
    def types_observable(self) -> bool:
        """False when the declarations could not be read at all.

        `has_declared_types` is False both for a plugin that declares nothing and for one
        whose manifest could not be read. Only this tells them apart, and every consumer
        MUST consult it before saying "declares no types".
        """
        return "types" not in self.unobservable


# ---------------------------------------------------------------------------
# Plugin / app-config plumbing
# ---------------------------------------------------------------------------


def _app_configs_by_slug() -> dict[str, Any]:
    """Loaded TapPluginConfig instances keyed by plugin slug (the AppConfig label)."""
    from django.apps import apps

    from tap_plugins.base import TapPluginConfig

    return {ac.label: ac for ac in apps.get_app_configs() if isinstance(ac, TapPluginConfig)}


def _module_path_to_slug() -> dict[str, str]:
    """Map a Django app `name` back to its plugin slug.

    `EntityType.plugin_name` stores the app's dotted module path (`tap_plugin.zizmor`,
    written by `tap_plugins.base._register_types_from_manifest` as `self.name`), NOT the
    slug. Every consumer that wants "which plugin owns this type" has to invert it.
    """
    from django.apps import apps

    return {ac.name: ac.label for ac in apps.get_app_configs()}


def _manifest_for(app_config: Any) -> PluginManifest | None:
    """The plugin's parsed manifest, or None when it failed to load.

    Private-attribute read, matching `tap_plugins.report.build_report()`. A plugin whose
    manifest did not load reports `manifest_valid: False` in the plugin report, so the
    page can say so rather than silently showing zero declared types.
    """
    manifest = getattr(app_config, "_manifest", None)
    return manifest  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Counts
# ---------------------------------------------------------------------------


def _node_counts(slugs: list[str]) -> dict[str, int] | None:
    """Live entity count per node-type slug. None when the read failed entirely."""
    if not slugs:
        return {}
    from django.db.models import Count

    from tap_grid.models import Entity

    try:
        rows = (
            Entity.objects.filter(entity_type__in=slugs, deleted_at__isnull=True)
            .values("entity_type")
            .annotate(n=Count("id"))
        )
        counts = {row["entity_type"]: row["n"] for row in rows}
    except Exception:
        logger.exception("[5251] node-type counts failed for %s slug(s)", len(slugs))
        return None
    return {s: counts.get(s, 0) for s in slugs}


def _edge_counts(slugs: list[str]) -> dict[str, int] | None:
    """Live edge count per edge-type slug. None when the read failed entirely.

    `Edge` is inside the ORM read backstop, so this needs `grid.read` — which the panel
    view authorizes before resolving any panel. A refusal here degrades the counts to
    not-observable rather than blanking the page.
    """
    if not slugs:
        return {}
    from django.db.models import Count

    from tap_grid.models import Edge

    try:
        rows = Edge.objects.filter(edge_type__in=slugs).values("edge_type").annotate(n=Count("id"))
        counts = {row["edge_type"]: row["n"] for row in rows}
    except Exception:
        logger.exception("[8192] edge-type counts failed for %s slug(s)", len(slugs))
        return None
    return {s: counts.get(s, 0) for s in slugs}


# ---------------------------------------------------------------------------
# Topology
# ---------------------------------------------------------------------------

# What `describe_edge_type` returns for an unconstrained end. Kept as a drawable value
# rather than dropped: "this edge accepts anything" is a real declaration, and omitting
# it would render an unconstrained edge identically to one whose read was refused.
WILDCARD_ENDPOINT = "*any*"


def _endpoints(edge_slug: str) -> tuple[list[str] | None, list[str] | None, str]:
    """Declared (sources, targets) for one edge type, via the service layer.

    Returns `(None, None, reason)` when the topology is not observable — the edge type is
    not registered, or the caller lacks `grid.discover`. Never raises.
    """
    from tap_auth.errors import AuthzError
    from tap_grid.exceptions import ServiceNotFoundError
    from tap_grid.services import describe_edge_type

    try:
        desc = describe_edge_type(edge_slug)
    except ServiceNotFoundError:
        return None, None, "edge type is not registered in the constraints registry"
    except AuthzError:
        logger.warning("[b01c] topology read refused for edge type %s (grid.discover)", edge_slug)
        return None, None, "topology read refused: grid.discover required"
    except Exception:
        logger.exception("[bedd] topology read failed for edge type %s", edge_slug)
        return None, None, "topology read failed"

    return _endpoint_list(desc.allowed_sources), _endpoint_list(desc.allowed_targets), ""


def _endpoint_list(raw: Any) -> list[str]:
    """Normalize `describe_edge_type`'s endpoint value into a drawable list."""
    if raw == "wildcard":
        return [WILDCARD_ENDPOINT]
    if raw == "none" or not raw:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    return [str(raw)]


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------


def _collectors_for(slug: str) -> tuple[list[CollectorFact], str]:
    """Collectors whose registry key is scoped to this plugin, newest run first.

    `Collector.collector_registry` is `<scope>:<key>` and the scope is mandatorily the
    plugin slug, so the prefix is the ownership test.

    Returns `(collectors, reason)`. A non-empty `reason` means the read FAILED and the empty
    list is ignorance, not absence — logging the failure does not make "ships no collectors"
    a true statement, so the reason travels to the surface.
    """
    from tap_cares.models import CollectionJob, Collector
    from tap_grid.models import Edge

    try:
        collectors = list(Collector.objects.filter(collector_registry__startswith=f"{slug}:").order_by("name"))
    except Exception:
        logger.exception("[b4f3] collector lookup failed for plugin %s", slug)
        return [], COLLECTORS_UNREADABLE

    facts: list[CollectorFact] = []
    for c in collectors:
        registry_key = c.collector_registry
        local_key = registry_key.split(":", 1)[1] if ":" in registry_key else registry_key
        runs_ok = True
        job_ids: list[Any] = []
        latest = None
        try:
            job_ids = list(
                Edge.objects.filter(from_entity_id=c.entity_id, edge_type="HAS_COLLECTION_JOB").values_list(
                    "to_entity_id", flat=True
                )
            )
            if job_ids:
                latest = CollectionJob.objects.filter(entity_id__in=job_ids).order_by("-enqueued_at").first()
        except Exception:
            # One unreadable history must not blank the whole section, and must not render
            # as "never run" — that is the same lie one level down.
            logger.exception("[c3a7] run history read failed for collector %s", c.entity_id)
            runs_ok = False
        facts.append(
            CollectorFact(
                entity_id=str(c.entity_id),
                name=c.name,
                registry_key=registry_key,
                local_key=local_key,
                last_status=latest.status if latest else "",
                last_status_label=(
                    latest.get_status_display() if latest else ("never run" if runs_ok else "run history not observable")
                ),
                last_run_at=(latest.finished_at or latest.started_at or latest.enqueued_at) if latest else None,
                last_summary=latest.summary if latest else "",
                run_count=len(job_ids),
                runs_observable=runs_ok,
                runs_reason="" if runs_ok else RUNS_UNREADABLE,
            )
        )
    return facts, ""


def batch_source_filter(slug: str) -> Any:
    """Q object matching every `Batch.source` string convention that names this plugin.

    There is NO single convention for attributing a batch to a plugin, and assuming one
    is how this surface would have shipped a lie. Observed on a live grid (2026-09-15):

        plugins.zizmor.grift.pages              GRIFT seed, slug-scoped
        plugins.administrivia                   GRIFT seed, bare
        tap_plugin.zizmor.collectors.zizmor_collector   collector runs, module path
        github_core                             bare slug
        ""                                      1895 batches, attributable to nothing

    An exact `source == "plugins.<slug>"` match reports zero for a plugin whose collector
    has run fifteen times — a false "this plugin has produced nothing", which is worse
    than no section at all. So match all three shapes. The unattributed `""` batches stay
    unattributed: they belong to no plugin and are never claimed by one.

    Upstream defect filed as unified-systems-com/tap#464 — the attribution string should
    be derived once rather than authored by each producer.
    """
    from django.db.models import Q

    return (
        Q(source=slug)
        | Q(source=f"plugins.{slug}")
        | Q(source__startswith=f"plugins.{slug}.")
        | Q(source=f"tap_plugin.{slug}")
        | Q(source__startswith=f"tap_plugin.{slug}.")
    )


def _batches_for(slug: str) -> tuple[list[BatchFact], str]:
    """The most recent batches attributable to this plugin, newest first.

    Returns `(batches, reason)`; a non-empty reason means the read failed and the empty list
    must not be rendered as "this plugin has produced nothing".
    """
    from tap_grid.models import Batch

    try:
        rows = list(Batch.objects.filter(batch_source_filter(slug)).order_by("-started_at")[:RECENT_BATCH_LIMIT])
    except Exception:
        logger.exception("[688a] batch lookup failed for plugin %s", slug)
        return [], BATCHES_UNREADABLE
    return [
        BatchFact(
            entity_id=str(b.entity_id),
            name=b.name or "(unnamed)",
            status=b.status,
            started_at=b.started_at,
            closed_at=b.closed_at,
            source=b.source,
        )
        for b in rows
    ], ""


# ---------------------------------------------------------------------------
# The one entry point
# ---------------------------------------------------------------------------


def build_plugin_facts(slug: str) -> PluginFacts:
    """Resolve every fact the plugin detail surfaces render, for one plugin slug.

    Routes identity through `tap_plugins.report.get_plugin_report()`, which authorizes
    `plugins.read` — so an unauthorized caller is refused in the service layer before any
    of this runs. Every other read degrades to a stated three-state value rather than
    raising, so one unavailable fact never blanks the page.
    """
    from tap_grid.models import EntityType
    from tap_plugins.report import get_plugin_report

    safe = normalize_slug(slug)
    facts = PluginFacts(slug=safe)
    if not slug:
        facts.error = "No plugin selected."
        return facts
    if not safe:
        # Never echo the rejected value back — not into the page, not into a log line.
        facts.error = "That is not a valid plugin slug. Open this page from a row on the plugins table."
        return facts
    slug = safe

    report = get_plugin_report()
    record = next((p for p in report["plugins"] if p["slug"] == slug), None)
    if record is None:
        facts.error = f"No plugin named '{slug}' is installed on this instance."
        return facts

    facts.found = True
    facts.record = record

    app_config = _app_configs_by_slug().get(slug)
    manifest = _manifest_for(app_config) if app_config is not None else None
    facts.manifest_available = manifest is not None
    if manifest is None:
        # The plugin loaded but its manifest did not. EVERYTHING the manifest would have told
        # us is now unknown — not zero. Marking the sections is what stops the surface saying
        # "declares no types" / "seeds no GRIFT" / "ships no boot records" about a plugin that
        # may well do all three (#12).
        facts.error = (
            "This plugin's manifest is not available on its AppConfig, so its declared "
            "types, GRIFT bundles and boot records are not observable."
        )
        for key in ("types", "grift", "boot_records"):
            facts.unobservable[key] = MANIFEST_UNAVAILABLE
        # Identity, provenance and activity do not come from the manifest, so they stay
        # readable: a section that cannot be read says so while the rest of the page renders.
        facts.collectors, collectors_reason = _collectors_for(slug)
        if collectors_reason:
            facts.unobservable["collectors"] = collectors_reason
        facts.batches, batches_reason = _batches_for(slug)
        if batches_reason:
            facts.unobservable["batches"] = batches_reason
        return facts

    declared_nodes = [m.slug for m in manifest.models]
    declared_edges = [e.slug for e in manifest.edges]

    # Registered types, and who owns them. Look up every slug the graph might draw —
    # this plugin's own declarations AND the foreign endpoint types its edges name.
    endpoints_by_edge: dict[str, tuple[list[str] | None, list[str] | None, str]] = {
        e: _endpoints(e) for e in declared_edges
    }
    foreign: set[str] = set()
    for sources, targets, _reason in endpoints_by_edge.values():
        for end in (sources or []) + (targets or []):
            if end != WILDCARD_ENDPOINT:
                foreign.add(end)
    wanted = set(declared_nodes) | set(declared_edges) | foreign

    module_to_slug = _module_path_to_slug()
    catalog_readable = True
    try:
        rows = {et.slug: et for et in EntityType.objects.filter(slug__in=sorted(wanted))}
    except Exception:
        logger.exception("[1cd5] EntityType lookup failed for plugin %s", slug)
        rows = {}
        catalog_readable = False
        # Every declared type will look unregistered. It is not — we could not check.
        facts.unobservable["types"] = CATALOG_UNREADABLE
    facts.type_owners = {s: module_to_slug.get(et.plugin_name, et.plugin_name) for s, et in rows.items()}

    node_counts = _node_counts(sorted(wanted & set(rows) | set(declared_nodes)))
    edge_counts = _edge_counts(declared_edges)

    def _node_fact(type_slug: str) -> TypeFact:
        et = rows.get(type_slug)
        registered = et is not None
        count = None if node_counts is None else node_counts.get(type_slug)
        return TypeFact(
            slug=type_slug,
            name=et.name if et else type_slug,
            # "" means not-yet-classified. Report it as unknown; never default to node.
            kind=et.kind if et else "",
            description=et.description if et else "",
            registered=registered,
            count=_count_state(
                registered,
                count,
                absent_reason=_absent_reason(registered, catalog_readable, "entity"),
            ),
            owner_slug=facts.type_owners.get(type_slug, ""),
        )

    facts.node_types = [_node_fact(s) for s in sorted(declared_nodes)]

    edge_facts: list[TypeFact] = []
    for edge_slug in sorted(declared_edges):
        et = rows.get(edge_slug)
        registered = et is not None
        sources, targets, reason = endpoints_by_edge[edge_slug]
        count = None if edge_counts is None else edge_counts.get(edge_slug)
        edge_facts.append(
            TypeFact(
                slug=edge_slug,
                name=et.name if et else edge_slug,
                kind=et.kind if et else "",
                description=et.description if et else "",
                registered=registered,
                count=_count_state(
                    registered,
                    count,
                    absent_reason=_absent_reason(registered, catalog_readable, "edge"),
                ),
                owner_slug=facts.type_owners.get(edge_slug, slug),
                sources=sources,
                targets=targets,
                endpoints_reason=reason,
            )
        )
    facts.edge_types = edge_facts

    facts.collectors, collectors_reason = _collectors_for(slug)
    if collectors_reason:
        facts.unobservable["collectors"] = collectors_reason
    facts.batches, batches_reason = _batches_for(slug)
    if batches_reason:
        facts.unobservable["batches"] = batches_reason
    facts.grift_bundles = [{"name": g.name, "path": g.path} for g in manifest.grift]
    facts.boot_records = [
        {"name": b.name, "description": b.description, "sha256": b.sha256} for b in manifest.boot_records
    ]

    # Foreign endpoint types the taxonomy draws but this plugin does not declare — the
    # cross-plugin half of the picture. Resolved here so the panel stays presentation-only.
    for type_slug in sorted(foreign - set(declared_nodes)):
        facts.type_owners.setdefault(type_slug, "")

    return facts


def foreign_node_facts(facts: PluginFacts) -> list[TypeFact]:
    """Node-type facts for the endpoint types this plugin's edges touch but do not own.

    Cross-plugin endpoints are the interesting half of a taxonomy (`zizmor__finding` ->
    `github_core__github_workflow`), so the graph draws them — but they are not the
    plugin's declared surface and never appear in its own type tables.
    """
    from tap_grid.models import EntityType

    own = {t.slug for t in facts.node_types}
    wanted: set[str] = set()
    for edge in facts.edge_types:
        for end in (edge.sources or []) + (edge.targets or []):
            if end != WILDCARD_ENDPOINT and end not in own:
                wanted.add(end)
    if not wanted:
        return []

    try:
        rows = {et.slug: et for et in EntityType.objects.filter(slug__in=sorted(wanted))}
    except Exception:
        logger.exception("[6358] foreign endpoint lookup failed for plugin %s", facts.slug)
        rows = {}
    counts = _node_counts(sorted(wanted))

    out: list[TypeFact] = []
    for type_slug in sorted(wanted):
        et = rows.get(type_slug)
        registered = et is not None
        count = None if counts is None else counts.get(type_slug)
        out.append(
            TypeFact(
                slug=type_slug,
                name=et.name if et else type_slug,
                kind=et.kind if et else "",
                description=et.description if et else "",
                registered=registered,
                count=_count_state(
                    registered,
                    count,
                    absent_reason="named as an endpoint but not registered in the type catalog",
                ),
                owner_slug=facts.type_owners.get(type_slug, ""),
            )
        )
    return out
