"""Administrivia Plugin Status panel tests.

The panel routes through the capability-gated service function
`tap_plugins.report.get_plugin_report()` (plugins.read), so these tests exercise both
the authorized data path (rows carry BOTH dependency directions) and the denial path.
"""

from __future__ import annotations

import json
import types

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import RequestFactory
from tap_plugin.administrivia.panels.plugin_status import PluginStatusPanelType

from tap_auth.errors import AuthzError
from tap_grid.caller_context import CallerContext, set_caller_context

pytestmark = pytest.mark.django_db


def _authorize(group_name: str | None) -> None:
    user = get_user_model().objects.create_user(username=f"u_{group_name or 'none'}", password="x")
    if group_name:
        user.groups.add(Group.objects.get(name=group_name))
    set_caller_context(CallerContext(user=user))


def _panel_stub() -> object:
    # get_view_context does not read panel fields — a stub keeps the test focused.
    return types.SimpleNamespace(entity_id="stub", name="Installed Plugins", config={})


def test_panel_context_builds_rows_for_authorized_caller() -> None:
    _authorize("tap_admin")
    ctx = PluginStatusPanelType.get_view_context(_panel_stub(), RequestFactory().get("/"))
    assert ctx["plugin_count"] >= 1
    rows = json.loads(ctx["table_nodes_json"])
    assert len(rows) == ctx["plugin_count"]
    # Every row consolidates both dependency directions (the bidirectional requirement).
    for row in rows:
        assert "depends_on" in row and "required_by" in row
    columns = json.loads(ctx["table_columns_json"])
    fields = {c["field"] for c in columns}
    assert {"depends_on", "required_by", "slug", "health"} <= fields


def _names(cell: str) -> set[str]:
    """The panel joins a direction's slugs with ", " and renders an empty one as an em dash."""
    return set() if cell == "\u2014" else {name.strip() for name in cell.split(",") if name.strip()}


def test_panel_bidirectional_edges_present() -> None:
    """Every dependency the panel shows appears from BOTH ends, whatever is installed.

    The roster is whatever this stack booted — under the plugin's own `ci` record that is
    administrivia alone (#5); under a product profile it is the product's set. The invariant is
    the same in both: if A lists B under depends_on and B is a row, B lists A under
    required_by, and the converse. Naming a sibling (samsite, github_core) here assumed the
    monorepo's everything-installed world and failed with KeyError when the sibling was absent.
    """
    _authorize("tap_admin")
    ctx = PluginStatusPanelType.get_view_context(_panel_stub(), RequestFactory().get("/"))
    rows = {r["slug"]: r for r in json.loads(ctx["table_nodes_json"])}
    assert "administrivia" in rows  # the panel's own plugin is always on the roster it renders
    for slug, row in rows.items():
        for dep in _names(row["depends_on"]):
            if dep in rows:
                assert slug in _names(rows[dep]["required_by"]), (slug, dep)
        for user in _names(row["required_by"]):
            assert user in rows, (slug, user)  # required_by is derived from installed rows only
            assert slug in _names(rows[user]["depends_on"]), (slug, user)


def test_panel_denies_caller_without_plugins_read() -> None:
    _authorize("tap_viewer")  # grid.read only
    with pytest.raises(AuthzError):
        PluginStatusPanelType.get_view_context(_panel_stub(), RequestFactory().get("/"))
