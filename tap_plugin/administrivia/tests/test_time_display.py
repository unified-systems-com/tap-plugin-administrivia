"""Human-facing times localize to the viewer (spec-web-time-display).

Every timestamp this plugin renders for a human must go through the ONE helper —
`tap_web.timefmt.render_local_time`, reached from templates as the `tap_localtime` filter —
so `localtime.js` can rewrite it to the viewer's browser zone.

Why this file exists: a raw `{{ x|date:"Y-m-d H:i:s" }}` formats in the ACTIVE timezone,
which falls back to `settings.TIME_ZONE` = "UTC". It looks right in review, renders fine,
and silently shows every operator a time that is not theirs. Eight templates in this plugin
had it, including the CARES run history and the run-detail page.

Two tests, deliberately:

- a RENDER test, because the bug lives in template output, not in a helper's unit behavior;
- a SWEEP test over every template in the package, because the render test only covers the
  templates someone remembered to write a test for, and the next panel is the one that
  regresses. The sweep is a guard against the whole class.

The machine-surface exception (`req-web-time-machine-utc`) is respected by scope: this only
looks at rendered human-facing templates, never at JSON payloads.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import tap_plugin.administrivia as administrivia_pkg
from django.template.loader import render_to_string

pytestmark = pytest.mark.django_db

TEMPLATES = Path(administrivia_pkg.__file__).resolve().parent / "templates"

# A fixed instant whose UTC rendering is unmistakable in the output.
WHEN = datetime(2026, 9, 15, 18, 23, 0, tzinfo=UTC)


def _panel() -> object:
    import types

    return types.SimpleNamespace(entity_id="stub", slug="stub", name="Panel", config={})


def _run_row() -> dict[str, object]:
    return {
        "entity_id": "00000000-0000-0000-0000-000000000001",
        "name": "a run",
        "status": "successful",
        "status_display": "Successful",
        "enqueued_at": WHEN,
        "started_at": WHEN,
        "finished_at": WHEN,
        "duration": "1.00 s",
        "task_result_id": "",
        "grift_imported_count": 0,
        "grift_skipped_count": 0,
        "grift_imported": [],
        "grift_skipped": [],
        "summary": "",
        "is_failed": False,
        "is_running": False,
        "is_successful": True,
    }


def test_collector_detail_run_history_renders_localizing_time_elements() -> None:
    """The run history George named: each timestamp is a `<time>` localtime.js can rewrite."""
    html = render_to_string(
        "administrivia/panels/collector_detail.html",
        {
            "panel": _panel(),
            "collector": {
                "entity_id": "x",
                "name": "c",
                "description": "",
                "registry_key": "a:b",
                "registry_scope": "a",
                "registry_local_key": "b",
                "available": True,
                "is_running": False,
                "readiness": {
                    "known": False, "status": "unknown", "status_label": "unknown",
                    "pill_class": "neutral", "summary": "", "runnable": True,
                    "checked_at": None, "checks": [],
                },
            },
            "latest_run": _run_row(),
            "runs": [_run_row()],
            "detail_error": "", "run_message": "", "run_error": "",
        },
    )
    # The marker localtime.js selects on (`time[data-tap-localtime]`), plus the machine
    # instant that keeps the exact UTC time recoverable (req-web-time-zone-disclosure).
    assert "data-tap-localtime" in html
    assert '<time datetime="2026-09-15T18:23:00Z"' in html
    # The no-JS fallback is LABELED UTC, never a bare ambiguous local-looking string
    # (req-web-time-local-display-3).
    assert "2026-09-15 18:23 UTC" in html
    # And the raw-filter shape that caused the bug is gone from the output.
    assert ">2026-09-15 18:23:00<" not in html


def test_run_detail_page_renders_localizing_time_elements() -> None:
    """The `cares run entity` page George named."""
    html = render_to_string(
        "administrivia/panels/run_detail.html",
        {
            "panel": _panel(),
            "job": {
                "entity_id": "x", "name": "r", "status": "successful",
                "status_display": "Successful", "enqueued_at": WHEN,
                "started_at": WHEN, "finished_at": WHEN, "duration": "1 s",
                "task_result_id": "", "summary": "", "self_test": None,
            },
            "detail_error": "",
        },
    )
    assert "data-tap-localtime" in html
    assert '<time datetime="2026-09-15T18:23:00Z"' in html


def test_plugin_detail_timestamps_use_the_shared_helper() -> None:
    """The new page's own timestamps ride the helper too — not a hand-rolled `<time>`."""
    from tap_plugin.administrivia.plugin_facts import BatchFact

    html = render_to_string(
        "administrivia/panels/plugin_detail.html",
        {
            "panel": _panel(),
            "sections": ["activity"],
            "plugin": {"slug": "x", "name": "x", "healthy": True, "health_label": "ok",
                       "distribution": "", "version": "0", "commit": "", "commit_short": "",
                       "source": "git", "mode": "package", "app_config": "", "health_detail": ""},
            "detail_error": "", "facts": None, "surface_rows": [],
            "dependencies": {"depends_on": [], "required_by": [], "undeclared_imports": [], "observed_imports": []},
            "node_types": [], "edge_types": [], "collectors": [],
            "batches": [BatchFact(entity_id="b", name="n", status="closed",
                                  started_at=WHEN, closed_at=WHEN, source="plugins.x")],
            "grift_bundles": [], "boot_records": [], "manifest_note": "",
        },
    )
    assert '<time datetime="2026-09-15T18:23:00Z"' in html


def test_no_template_in_this_plugin_formats_a_time_with_a_raw_date_filter() -> None:
    """Sweep guard: `|date` on a human-facing timestamp is the bug, in any template.

    A render test only covers the template someone wrote a test for. This covers the class,
    so the NEXT panel cannot quietly reintroduce a UTC timestamp. If a genuinely
    non-datetime `|date` use ever appears, narrow this — do not delete it.
    """
    offenders: list[str] = []
    for path in sorted(TEMPLATES.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            if "|date" in line:
                offenders.append(f"{path.name}:{number}: {line.strip()[:90]}")
    assert not offenders, (
        "These render a time in settings.TIME_ZONE (UTC), not the viewer's zone. "
        "Use `{{ value|tap_localtime }}` (load tap_time) — spec-web-time-display, "
        "req-web-time-single-helper:\n" + "\n".join(offenders)
    )


def test_every_template_that_localizes_loads_the_filter() -> None:
    """A `tap_localtime` without `{% load tap_time %}` renders EMPTY, silently."""
    missing: list[str] = []
    for path in sorted(TEMPLATES.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        if "tap_localtime" in text and "{% load tap_time %}" not in text:
            missing.append(path.name)
    assert not missing, missing
