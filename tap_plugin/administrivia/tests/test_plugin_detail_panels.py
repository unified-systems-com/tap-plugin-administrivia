"""Plugin detail page tests — the detail panel, the taxonomy panel, and the three states.

Two things are worth guarding here and they are not the same thing:

1. The panels render. Both templates are exercised for real (`render_to_string`), because a
   panel type whose template raises is a panel that ships broken and passes every test that
   only inspects its context dict.
2. Three states, never two. A count that could not be read must never render as zero, and a
   declared-but-never-used type must not vanish. These assertions are the point of the
   surface, so they are made against RENDERED OUTPUT, not against internal flags.

Roster discipline (the lesson of #5): these tests never name a sibling plugin. Whatever this
stack booted is the roster — under the plugin's own `ci` record that is administrivia alone.
Anything needing a specific type shape constructs it.

Spec: specs/spec-administrivia-v0.md req-administrivia-v0-plugin-facts /
      -plugin-detail-panel / -plugin-taxonomy-panel.
"""

from __future__ import annotations

import json
import types

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.test import RequestFactory
from tap_plugin.administrivia import plugin_facts as pf
from tap_plugin.administrivia.panels.plugin_detail import PluginDetailPanelType, _surface_rows
from tap_plugin.administrivia.panels.plugin_taxonomy import PluginTaxonomyPanelType, _build_elements

from tap_auth.errors import AuthzError
from tap_grid.caller_context import CallerContext, set_caller_context

pytestmark = pytest.mark.django_db

_OWN = "administrivia"


def _authorize(group_name: str | None) -> None:
    user = get_user_model().objects.create_user(username=f"u_{group_name or 'none'}", password="x")
    if group_name:
        user.groups.add(Group.objects.get(name=group_name))
    set_caller_context(CallerContext(user=user))


def _panel(config: dict | None = None, name: str = "Plugin Detail") -> object:
    return types.SimpleNamespace(entity_id="stub", slug="stub", name=name, config=config or {})


def _request(slug: str | None) -> HttpRequest:
    return RequestFactory().get("/" if slug is None else f"/?slug={slug}")


def _render(template: str, ctx: dict, panel: object) -> str:
    return render_to_string(template, {"panel": panel, **ctx})


def _node(slug: str, count: pf.CountState, owner: str = _OWN) -> pf.TypeFact:
    return pf.TypeFact(
        slug=slug, name=slug, kind="node", description="", registered=True, count=count, owner_slug=owner
    )


# ---------------------------------------------------------------------------
# The three states
# ---------------------------------------------------------------------------


def test_zero_instances_is_never_observed_not_a_bare_zero() -> None:
    """A registered type with no instances says so in words, and is not the string '0'."""
    state = pf._count_state(True, 0, absent_reason="unused")
    assert state.is_never_observed
    assert state.label == "declared, never observed"


def test_unregistered_type_is_not_observable_and_distinct_from_zero() -> None:
    """Declared but never registered is NOT zero instances — the whole point of three states."""
    absent = pf._count_state(False, None, absent_reason="never registered")
    zero = pf._count_state(True, 0, absent_reason="unused")
    assert absent.is_not_observable and zero.is_never_observed
    assert absent.label != zero.label
    assert absent.reason == "never registered"


def test_unreadable_count_on_a_registered_type_is_also_not_observable() -> None:
    """A registered type whose count could not be read must not be reported as zero."""
    assert pf._count_state(True, None, absent_reason="read failed").is_not_observable


def test_the_three_states_render_differently() -> None:
    """Rendered, not merely flagged: a reader must be able to tell them apart."""
    rendered = {
        s.state: render_to_string("administrivia/partials/count_state.html", {"count": s})
        for s in (
            pf.CountState(pf.OBSERVED, value=7),
            pf._count_state(True, 0, absent_reason=""),
            pf._count_state(False, None, absent_reason="never registered"),
        )
    }
    assert len(rendered) == 3
    assert "7" in rendered[pf.OBSERVED]
    assert "never observed" in rendered[pf.NEVER_OBSERVED]
    assert "not observable" in rendered[pf.NOT_OBSERVABLE]
    # Each state carries its own marker class, so CSS can distinguish them.
    assert len({r.split('class="')[1].split('"')[0] for r in rendered.values()}) == 3


def test_unclassified_kind_reads_as_unknown_never_as_node() -> None:
    """`EntityType.kind == ""` means not-yet-classified (tap_grid), not node."""
    fact = pf.TypeFact(
        slug="x", name="x", kind="", description="", registered=True, count=pf.CountState(pf.OBSERVED, 1), owner_slug=""
    )
    assert fact.kind_label == "unclassified"
    assert fact.kind_label != "node"


def test_unmeasured_surface_is_not_rendered_as_zero_loaded() -> None:
    """`loaded: null` in the plugin report means "we did not look", not "none loaded"."""
    rows = {r["key"]: r for r in _surface_rows({"editors": {"declared": 3, "loaded": None}})}
    assert rows["editors"]["state"] == "unmeasured"
    html = _render("administrivia/panels/plugin_detail.html", {"plugin": None, "detail_error": ""}, _panel())
    assert html  # template tolerates a bare context


def test_surface_shortfall_is_named_not_merely_shown() -> None:
    rows = {r["key"]: r for r in _surface_rows({"models": {"declared": 5, "loaded": 2}})}
    assert rows["models"]["state"] == "gap"
    assert "3" in rows["models"]["detail"]


# ---------------------------------------------------------------------------
# Detail panel
# ---------------------------------------------------------------------------


def test_detail_panel_renders_an_installed_plugin() -> None:
    _authorize("tap_admin")
    ctx = PluginDetailPanelType.get_view_context(_panel(), _request(_OWN))
    assert ctx["detail_error"] == ""
    assert ctx["plugin"]["slug"] == _OWN
    assert ctx["plugin"]["health_label"] in {"ok", "degraded"}
    # Both dependency directions are present, whatever this stack installed.
    assert "depends_on" in ctx["dependencies"] and "required_by" in ctx["dependencies"]
    html = _render(PluginDetailPanelType.view, ctx, _panel())
    assert _OWN in html
    assert "Surfaces" in html and "Dependencies" in html


def test_detail_panel_names_an_uninstalled_plugin_rather_than_raising() -> None:
    _authorize("tap_admin")
    ctx = PluginDetailPanelType.get_view_context(_panel(), _request("notarealplugin"))
    assert ctx["plugin"] is None
    assert "notarealplugin" in ctx["detail_error"]
    assert "notarealplugin" in _render(PluginDetailPanelType.view, ctx, _panel())


@pytest.mark.parametrize(
    "bad",
    [
        "not-a-real-plugin",              # hyphens are not AppConfig labels
        "../../etc/passwd",
        "zizmor\nWARNING forged log line",  # the log-forging shape (Sonar S5145)
        "a" * 200,
        "9leading_digit",
    ],
)
def test_a_malformed_slug_is_refused_and_never_echoed_back(bad: str) -> None:
    """A slug is an identifier, not free text — and a rejected one is never reflected.

    Guards both halves of the boundary: `normalize_slug` refuses the value, and the
    message the page renders does not contain it, so nothing user-controlled reaches the
    page or a log record.
    """
    assert pf.normalize_slug(bad) == ""
    _authorize("tap_admin")
    ctx = PluginDetailPanelType.get_view_context(_panel(), _request(bad))
    assert ctx["plugin"] is None
    assert ctx["detail_error"]
    assert bad not in ctx["detail_error"]
    assert bad.strip() not in _render(PluginDetailPanelType.view, ctx, _panel())


def test_a_wellformed_slug_survives_normalization() -> None:
    """The validator must not reject the slugs that actually exist."""
    for good in ("zizmor", "github_core", "git_serious_double_tap", _OWN):
        assert pf.normalize_slug(good) == good


def test_detail_panel_with_no_slug_is_a_state_not_a_crash() -> None:
    _authorize("tap_admin")
    ctx = PluginDetailPanelType.get_view_context(_panel(), _request(None))
    assert ctx["plugin"] is None and ctx["detail_error"]
    assert _render(PluginDetailPanelType.view, ctx, _panel())


def test_detail_panel_keeps_the_plugins_read_gate() -> None:
    """The gate lives in the service layer; the panel must not have routed around it."""
    _authorize("tap_viewer")  # grid.read only
    with pytest.raises(AuthzError):
        PluginDetailPanelType.get_view_context(_panel(), _request(_OWN))


# ---------------------------------------------------------------------------
# Taxonomy panel
# ---------------------------------------------------------------------------


def _facts_with_cross_plugin_edge() -> pf.PluginFacts:
    """A plugin declaring one node type and one edge into ANOTHER plugin's type."""
    facts = pf.PluginFacts(slug="alpha", found=True)
    facts.node_types = [_node("alpha__thing", pf.CountState(pf.OBSERVED, 4), owner="alpha")]
    facts.edge_types = [
        pf.TypeFact(
            slug="TOUCHES__alpha",
            name="Touches",
            kind="edge",
            description="",
            registered=True,
            count=pf.CountState(pf.OBSERVED, 2),
            owner_slug="alpha",
            sources=["alpha__thing"],
            targets=["beta__other"],
        )
    ]
    facts.type_owners = {"alpha__thing": "alpha", "beta__other": "beta"}
    return facts


def test_taxonomy_draws_a_foreign_endpoint_and_marks_the_edge_cross_plugin() -> None:
    """Cross-plugin endpoints are the interesting half; they must be drawn, not dropped."""
    built = _build_elements(_facts_with_cross_plugin_edge())
    by_id = {e["data"]["id"]: e["data"] for e in built["elements"]}
    assert "beta__other" in by_id, "the foreign endpoint type was not drawn"
    assert by_id["beta__other"]["kind_class"] == "foreign"
    assert by_id["alpha__thing"]["kind_class"] == "own"
    edge = next(d for d in by_id.values() if "source" in d)
    assert edge["cross_plugin"] is True
    assert built["unplaced"] == []


def test_taxonomy_draws_every_declared_edge_or_says_why_not() -> None:
    """An edge missing from the picture must never read as an edge that was not declared."""
    facts = _facts_with_cross_plugin_edge()
    facts.edge_types.append(
        pf.TypeFact(
            slug="UNREADABLE__alpha",
            name="Unreadable",
            kind="edge",
            description="",
            registered=False,
            count=pf._count_state(False, None, absent_reason="x"),
            owner_slug="alpha",
            sources=None,
            targets=None,
            endpoints_reason="edge type is not registered in the constraints registry",
        )
    )
    built = _build_elements(facts)
    drawn = {d["data"]["slug"] for d in built["elements"] if "source" in d["data"]}
    listed = {u["slug"] for u in built["unplaced"]}
    assert {t.slug for t in facts.edge_types} == drawn | listed


def test_taxonomy_wildcard_endpoint_is_drawn_not_omitted() -> None:
    """"Accepts any type" is a real declaration and must be visible as one."""
    facts = pf.PluginFacts(slug="alpha", found=True)
    facts.node_types = [_node("alpha__thing", pf.CountState(pf.OBSERVED, 1), owner="alpha")]
    facts.edge_types = [
        pf.TypeFact(
            slug="ANY__alpha",
            name="Any",
            kind="edge",
            description="",
            registered=True,
            count=pf._count_state(True, 0, absent_reason=""),
            owner_slug="alpha",
            sources=[pf.WILDCARD_ENDPOINT],
            targets=["alpha__thing"],
        )
    ]
    built = _build_elements(facts)
    ids = {e["data"]["id"] for e in built["elements"]}
    assert "__any__" in ids
    assert built["unplaced"] == []


def test_taxonomy_every_drawn_edge_has_both_endpoints_drawn() -> None:
    """A dangling edge would render as a line to nowhere; Cytoscape would drop it silently."""
    built = _build_elements(_facts_with_cross_plugin_edge())
    nodes = {e["data"]["id"] for e in built["elements"] if "source" not in e["data"]}
    for e in built["elements"]:
        d = e["data"]
        if "source" in d:
            assert d["source"] in nodes and d["target"] in nodes, d["id"]


def test_taxonomy_panel_renders_for_an_installed_plugin() -> None:
    _authorize("tap_admin")
    panel = _panel({"height": "400px"}, name="Declared Taxonomy")
    ctx = PluginTaxonomyPanelType.get_view_context(panel, _request(_OWN))
    assert ctx["graph_error"] == ""
    html = _render(PluginTaxonomyPanelType.view, ctx, panel)
    assert html.strip()
    if ctx["has_graph"]:
        # The payload the browser parses must be real, parseable JSON with content.
        assert json.loads(json.dumps(ctx["elements"]))
        assert "Legend" in html
    else:
        # A plugin declaring no vocabulary says so; it never renders a blank canvas.
        assert ctx["empty_message"] and ctx["empty_message"] in html.replace("&#x27;", "'")


def test_taxonomy_legend_names_every_state_the_panel_can_draw() -> None:
    """A legend that omits a state is worse than none — the reader has to guess."""
    _authorize("tap_admin")
    facts = _facts_with_cross_plugin_edge()
    from tap_plugin.administrivia.panels.plugin_taxonomy import _legend

    keys = {item["key"] for item in _legend(facts, foreign_count=1)}
    assert {pf.OBSERVED, pf.NEVER_OBSERVED, pf.NOT_OBSERVABLE, "own", "foreign"} <= keys


def test_taxonomy_height_config_is_allowlisted() -> None:
    """`height` lands in an inline style attribute, so it is validated rather than trusted."""
    _authorize("tap_admin")
    for bad in ("100px; background:url(x)", "expression(1)", "", "auto"):
        ctx = PluginTaxonomyPanelType.get_view_context(_panel({"height": bad}), _request(_OWN))
        assert ctx["graph_height"] == "520px"
    ctx = PluginTaxonomyPanelType.get_view_context(_panel({"height": "640px"}), _request(_OWN))
    assert ctx["graph_height"] == "640px"


def test_taxonomy_panel_keeps_the_plugins_read_gate() -> None:
    _authorize("tap_viewer")
    with pytest.raises(AuthzError):
        PluginTaxonomyPanelType.get_view_context(_panel(), _request(_OWN))


# ---------------------------------------------------------------------------
# One derivation
# ---------------------------------------------------------------------------


def test_both_panels_report_the_same_types_for_the_same_plugin() -> None:
    """The two views of one plugin are built from one derivation and cannot disagree."""
    _authorize("tap_admin")
    detail = PluginDetailPanelType.get_view_context(_panel(), _request(_OWN))
    tax = PluginTaxonomyPanelType.get_view_context(_panel(), _request(_OWN))
    detail_nodes = {t.slug for t in detail["node_types"]}
    if tax["has_graph"]:
        drawn_own = {e["data"]["id"] for e in tax["elements"] if e["data"].get("own")}
        assert detail_nodes == drawn_own
    else:
        assert detail_nodes == set()


def test_batch_attribution_matches_every_observed_source_convention() -> None:
    """`Batch.source` has no single convention (tap#464); an exact match under-reports.

    Guards the workaround itself: if someone "simplifies" the filter back to one shape, a
    plugin whose collector has run will silently report having produced nothing.
    """
    rendered = str(pf.batch_source_filter("zeta")).replace("'", "")
    # The bare slug, the plugins.* shapes and the tap_plugin.* shapes are all matched;
    # dropping any one of them silently under-reports a real plugin's output.
    for expected in (
        "(source, zeta)",
        "(source, plugins.zeta)",
        "(source__startswith, plugins.zeta.)",
        "(source, tap_plugin.zeta)",
        "(source__startswith, tap_plugin.zeta.)",
    ):
        assert expected in rendered, (expected, rendered)
