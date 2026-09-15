"""Plugin Detail panel — everything about one installed plugin except its taxonomy graph.

A row in the installed-plugins table used to be a dead end. This is the other end of that
link: identity and provenance, declared-vs-loaded surfaces with the gap made visible, both
dependency directions, the node and edge types the plugin declares with their live counts,
its collectors, the batches it has produced, its GRIFT bundles and boot records.

The panel is PRESENTATION ONLY. Every fact comes from `plugin_facts.build_plugin_facts()`,
which is also what the taxonomy panel reads — one derivation, so the two views of the same
plugin cannot disagree (req-administrivia-v0-plugin-facts-1). Capability gating rides along
for free: `build_plugin_facts` routes identity through `tap_plugins.report.get_plugin_report()`,
which authorizes `plugins.read` in the service layer.

Read-only: no grid writes.

Spec: specs/spec-administrivia-v0.md req-administrivia-v0-plugin-detail-panel.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from tap_plugin.administrivia.plugin_facts import build_plugin_facts

from tap_auth.errors import AuthzError

if TYPE_CHECKING:
    from django.http import HttpRequest

    from tap_web.models import Panel

logger = logging.getLogger(__name__)

# Surfaces whose "loaded" count the plugin report genuinely measures. The others report
# `loaded: null`, which is NOT zero — it is "we did not look". Rendering an unmeasured
# surface as 0/N would be a declaration that is present and false.
_SURFACE_ORDER: tuple[tuple[str, str], ...] = (
    ("models", "Node types"),
    ("edges", "Edge types"),
    ("editors", "Editors"),
    ("searches", "Searches"),
    ("grift", "GRIFT bundles"),
)


def _surface_rows(surfaces: dict[str, Any]) -> list[dict[str, Any]]:
    """Declared-vs-loaded rows, each carrying its own honest state.

    Three outcomes per surface:
      - measured and equal          -> `ok`
      - measured and loaded < declared -> `gap`, with the shortfall named
      - not measured (loaded is None)  -> `unmeasured`; renders as "not measured",
                                          never as 0 (req-administrivia-v0-plugin-detail-panel-3)
    """
    rows: list[dict[str, Any]] = []
    for key, label in _SURFACE_ORDER:
        counts = surfaces.get(key) or {}
        declared = counts.get("declared", 0)
        loaded = counts.get("loaded")
        if loaded is None:
            state, detail = "unmeasured", "the plugin report does not measure whether these loaded"
        elif loaded < declared:
            state, detail = "gap", f"{declared - loaded} declared but not registered"
        else:
            state, detail = "ok", ""
        rows.append(
            {
                "key": key,
                "label": label,
                "declared": declared,
                "loaded": loaded,
                "state": state,
                "detail": detail,
            }
        )
    return rows


def _dependency_rows(dependencies: dict[str, Any]) -> dict[str, Any]:
    """Both dependency directions, plus the undeclared-import warning.

    An observed import that is not declared is a load-order defect waiting to happen: the
    plugin works today only because something else happens to load first.
    """
    detail = {d["slug"]: d for d in dependencies.get("declared_detail", [])}
    return {
        "depends_on": [
            {
                "slug": s,
                "min_version": detail.get(s, {}).get("min_version") or "",
                "optional": bool(detail.get(s, {}).get("optional")),
                "note": detail.get(s, {}).get("note") or "",
            }
            for s in dependencies.get("depends_on", [])
        ],
        "required_by": list(dependencies.get("required_by", [])),
        "undeclared_imports": list(dependencies.get("undeclared_imports", [])),
        "observed_imports": list(dependencies.get("observed_imports", [])),
    }


# Every return path yields the same keys, so the template never depends on a missing
# variable resolving to empty — a context whose shape changes with the outcome is how a
# section quietly disappears instead of rendering its empty state.
_EMPTY: dict[str, Any] = {
    "detail_error": "",
    "facts": None,
    "plugin": None,
    "surface_rows": [],
    "dependencies": {"depends_on": [], "required_by": [], "undeclared_imports": [], "observed_imports": []},
    "node_types": [],
    "edge_types": [],
    "collectors": [],
    "batches": [],
    "grift_bundles": [],
    "boot_records": [],
    "manifest_note": "",
}


class PluginDetailPanelType:
    slug = "plugin_detail"
    label = "Plugin Detail"
    view = "administrivia/panels/plugin_detail.html"
    editor_view = ""
    css: ClassVar[list[str]] = ["administrivia/css/plugin_detail.css"]
    js: ClassVar[list[str]] = []
    config_defaults: ClassVar[dict[str, Any]] = {}

    @classmethod
    def get_view_context(cls, panel: Panel, request: HttpRequest) -> dict[str, Any]:
        slug = request.GET.get("slug", "").strip()
        try:
            facts = build_plugin_facts(slug)
        except AuthzError:
            # Never disguise a refusal as a render failure. tap_web.views.panel_view
            # re-raises AuthzError for exactly this reason, and tap_auth's middleware
            # turns it into a clean 403 — a panel that caught it here would render
            # "something went wrong" over a working authorization decision.
            raise
        except Exception as exc:  # noqa: BLE001 — a panel must never take the page down
            logger.exception("[84f9] plugin detail facts failed for slug %r", slug)
            return {**_EMPTY, "detail_error": f"{type(exc).__name__}: {exc}"}

        if not facts.found:
            return {**_EMPTY, "detail_error": facts.error}

        record = facts.record
        version = record.get("version") or "unknown"
        commit = record.get("commit") or ""
        health = record.get("load_health") or {}
        healthy = bool(health.get("loaded")) and bool(health.get("manifest_valid"))

        return {
            **_EMPTY,
            "facts": facts,
            "plugin": {
                "slug": facts.slug,
                "name": record.get("name") or facts.slug,
                "distribution": record.get("distribution") or "",
                "version": version,
                "commit": commit,
                "commit_short": commit[:8] if commit else "",
                "source": record.get("source") or "unknown",
                "mode": record.get("mode") or "unknown",
                "app_config": record.get("app_config") or "",
                "healthy": healthy,
                "health_label": "ok" if healthy else "degraded",
                "health_detail": health.get("detail") or "",
            },
            "surface_rows": _surface_rows(record.get("surfaces") or {}),
            "dependencies": _dependency_rows(record.get("dependencies") or {}),
            "node_types": facts.node_types,
            "edge_types": facts.edge_types,
            "collectors": facts.collectors,
            "batches": facts.batches,
            "grift_bundles": facts.grift_bundles,
            "boot_records": facts.boot_records,
            "manifest_note": facts.error,
        }
