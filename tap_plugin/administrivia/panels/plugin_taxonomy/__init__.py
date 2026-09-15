"""Plugin Taxonomy panel — the type-level graph a plugin declares, with live counts on it.

What this draws is a DICTIONARY, not data. The nodes are node *types*; the edges are the
edge *types* the plugin declares, pointed at the endpoints its `.edge.json` files name. It
is therefore drawable on a grid that has never collected anything — which is the point:
a human can see the shape of the vocabulary a plugin defines before any of it is populated.

The counts overlay is what makes it worth looking at. Each type carries its live instance
count in one of three states — a number, "declared, never observed", or "not observable" —
and a never-observed type is drawn dashed, so an empty grid reads at a glance as a complete
dictionary with nothing in it rather than as a broken page.

Cross-plugin endpoints are drawn and visually distinguished. They are the interesting half:
`zizmor__finding -> github_core__github_workflow` is a plugin reaching into another
plugin's vocabulary, and that relationship exists nowhere else in the UI.

**Deliberately NOT built on `tap_viz`'s graph panel.** That panel is search-/entity-bound —
it executes a Search and renders the grid entities that come back. A type-level graph has
no entities behind it, so there is nothing for a Search to return. This panel synthesizes
the Cytoscape element list server-side and hands it straight to Cytoscape (the vendored
`tap_viz/js/lib/cytoscape.min.js`; no second copy of the library is introduced).

Presentation only: every fact comes from `plugin_facts.build_plugin_facts()`, the same
derivation the detail panel reads (req-administrivia-v0-plugin-facts-1).

Read-only: no grid writes.

Spec: specs/spec-administrivia-v0.md req-administrivia-v0-plugin-taxonomy-panel.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, ClassVar

from tap_plugin.administrivia.plugin_facts import (
    NEVER_OBSERVED,
    NOT_OBSERVABLE,
    OBSERVED,
    WILDCARD_ENDPOINT,
    TypeFact,
    build_plugin_facts,
    foreign_node_facts,
)

from tap_auth.errors import AuthzError

if TYPE_CHECKING:
    from django.http import HttpRequest

    from tap_web.models import Panel

logger = logging.getLogger(__name__)

# `height` reaches an inline style attribute, so it is allowlisted rather than trusted.
_ALLOWED_HEIGHT = re.compile(r"^(100%|[1-9][0-9]{0,3}px)$")
_DEFAULT_HEIGHT = "520px"

# The synthetic node an unconstrained endpoint points at. An edge type that accepts any
# type is a real declaration; dropping it would render it identically to one whose
# topology could not be read, which is exactly the confusion this panel exists to prevent.
_ANY_NODE_ID = "__any__"


def _height(raw: Any) -> str:
    return raw if isinstance(raw, str) and _ALLOWED_HEIGHT.match(raw) else _DEFAULT_HEIGHT


def _node_element(fact: TypeFact, *, own: bool) -> dict[str, Any]:
    """One Cytoscape node for one node type, carrying its own styling inputs.

    Style is data, not stylesheet lookups: `kind_class` and `count_state` are read by the
    stylesheet in plugin_taxonomy.js, so a node's appearance is decided once, here.
    """
    return {
        "data": {
            "id": fact.slug,
            "label": fact.name or fact.slug,
            "slug": fact.slug,
            "owner": fact.owner_slug,
            "own": own,
            "kind_class": "own" if own else "foreign",
            "count_state": fact.count.state,
            "count_label": fact.count.label,
            "count_value": fact.count.value,
            "registered": fact.registered,
            "description": fact.description,
            "reason": fact.count.reason,
            # Second label line: a foreign type is only legible if you can see whose it is.
            "sublabel": ("" if own else (fact.owner_slug or "unknown plugin")),
        }
    }


def _any_node_element() -> dict[str, Any]:
    return {
        "data": {
            "id": _ANY_NODE_ID,
            "label": "any type",
            "slug": "",
            "owner": "",
            "own": False,
            "kind_class": "any",
            "count_state": NOT_OBSERVABLE,
            "count_label": "unconstrained endpoint",
            "count_value": None,
            "registered": True,
            "description": "This edge type declares no constraint on this end — it accepts any type.",
            "reason": "",
            "sublabel": "wildcard",
        }
    }


def _build_elements(facts: Any) -> dict[str, Any]:
    """Synthesize the Cytoscape element list from the plugin's declarations."""
    own_nodes = list(facts.node_types)
    own_slugs = {t.slug for t in own_nodes}
    foreign = foreign_node_facts(facts)

    elements: list[dict[str, Any]] = [_node_element(t, own=True) for t in own_nodes]
    elements += [_node_element(t, own=False) for t in foreign]

    drawn = own_slugs | {t.slug for t in foreign}
    needs_any = False
    edge_elements: list[dict[str, Any]] = []
    unplaced: list[dict[str, str]] = []

    for edge in facts.edge_types:
        sources, targets = edge.sources, edge.targets
        if sources is None or targets is None:
            # The topology was not readable. Say so in the sidebar rather than drawing a
            # line that asserts endpoints nobody verified.
            unplaced.append({"slug": edge.slug, "name": edge.name, "reason": edge.endpoints_reason})
            continue
        if not sources or not targets:
            unplaced.append(
                {
                    "slug": edge.slug,
                    "name": edge.name,
                    "reason": "declares no allowed type on one end",
                }
            )
            continue
        for src in sources:
            for tgt in targets:
                s_id = _ANY_NODE_ID if src == WILDCARD_ENDPOINT else src
                t_id = _ANY_NODE_ID if tgt == WILDCARD_ENDPOINT else tgt
                needs_any = needs_any or _ANY_NODE_ID in (s_id, t_id)
                if s_id not in drawn and s_id != _ANY_NODE_ID:
                    continue
                if t_id not in drawn and t_id != _ANY_NODE_ID:
                    continue
                edge_elements.append(
                    {
                        "data": {
                            "id": f"{edge.slug}::{s_id}::{t_id}",
                            "source": s_id,
                            "target": t_id,
                            "label": edge.name or edge.slug,
                            "slug": edge.slug,
                            "count_state": edge.count.state,
                            "count_label": edge.count.label,
                            "cross_plugin": (
                                s_id != _ANY_NODE_ID
                                and t_id != _ANY_NODE_ID
                                and (s_id not in own_slugs or t_id not in own_slugs)
                            ),
                            "description": edge.description,
                        }
                    }
                )

    if needs_any:
        elements.append(_any_node_element())
    elements += edge_elements
    return {"elements": elements, "unplaced": unplaced, "foreign_count": len(foreign)}


def _legend(facts: Any, foreign_count: int) -> list[dict[str, str]]:
    """Name every visual distinction the graph makes.

    A reader must never have to infer that dashed means never-observed
    (req-administrivia-v0-plugin-taxonomy-panel-5).
    """
    items = [
        {"key": "own", "label": f"declared by {facts.slug}", "hint": "this plugin's own vocabulary"},
    ]
    if foreign_count:
        items.append(
            {
                "key": "foreign",
                "label": "another plugin's type",
                "hint": "an endpoint this plugin's edges reach into — the cross-plugin half",
            }
        )
    items += [
        {"key": OBSERVED, "label": "observed", "hint": "instances of this type exist on this grid"},
        {
            "key": NEVER_OBSERVED,
            "label": "declared, never observed",
            "hint": "the type is registered and nothing has ever used it — drawn dashed",
        },
        {
            "key": NOT_OBSERVABLE,
            "label": "not observable",
            "hint": "declared but never registered, or the count could not be read — this is NOT zero",
        },
    ]
    return items


class PluginTaxonomyPanelType:
    slug = "plugin_taxonomy"
    label = "Plugin Taxonomy"
    view = "administrivia/panels/plugin_taxonomy.html"
    editor_view = ""
    css: ClassVar[list[str]] = ["administrivia/css/plugin_taxonomy.css"]
    js: ClassVar[list[str]] = [
        "tap_viz/js/lib/cytoscape.min.js",
        "administrivia/js/plugin_taxonomy.js",
    ]
    config_defaults: ClassVar[dict[str, Any]] = {"height": _DEFAULT_HEIGHT}

    @classmethod
    def get_view_context(cls, panel: Panel, request: HttpRequest) -> dict[str, Any]:
        slug = request.GET.get("slug", "").strip()
        height = _height((panel.config or {}).get("height", _DEFAULT_HEIGHT))
        # One context shape on every path (see plugin_detail._EMPTY for why).
        base: dict[str, Any] = {
            "graph_height": height,
            "graph_error": "",
            "has_graph": False,
            "empty_message": "",
            "unplaced": [],
            "legend": [],
            "elements": [],
        }

        try:
            facts = build_plugin_facts(slug)
        except AuthzError:
            # A refusal is a 403, not a broken panel. See the note in plugin_detail.
            raise
        except Exception as exc:  # noqa: BLE001 — a panel must never take the page down
            logger.exception("[6580] taxonomy facts failed for slug %r", slug)
            return {**base, "graph_error": f"{type(exc).__name__}: {exc}"}

        if not facts.found:
            return {**base, "graph_error": facts.error}

        if not facts.has_declared_types:
            return {
                **base,
                "empty_message": (
                    f"'{facts.slug}' declares no node or edge types. It is a pages-and-panels "
                    f"plugin: it contributes surfaces over other plugins' vocabulary rather than "
                    f"vocabulary of its own."
                ),
            }

        try:
            built = _build_elements(facts)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[0502] taxonomy element build failed for slug %r", slug)
            return {**base, "graph_error": f"{type(exc).__name__}: {exc}"}

        return {
            **base,
            "has_graph": True,
            "plugin_slug": facts.slug,
            # Embedded with Django's `json_script` (escaped by the engine), not a
            # hand-rolled serializer — the direction issue #1 asks new panels to take.
            "graph_script_id": f"tap-tax-elements-{panel.entity_id}",
            "elements": built["elements"],
            "unplaced": built["unplaced"],
            "legend": _legend(facts, built["foreign_count"]),
            "node_type_count": len(facts.node_types),
            "edge_type_count": len(facts.edge_types),
            "foreign_count": built["foreign_count"],
        }
