from __future__ import annotations

from typing import Any, Callable

from ..audit import AuditResult
from . import to_html, to_json, to_markdown

RENDERERS: dict[str, Callable[[AuditResult], str]] = {
    "md": to_markdown.render,
    "html": to_html.render,
    "json": to_json.render,
}

EXTENSIONS = {"md": ".md", "html": ".html", "json": ".json"}


def format_value(value: Any, limit: int = 6) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        shown = [(key, val) for key, val in value.items() if val not in (None, "", [], {})]
        items = [f"{key}: {format_value(val, limit)}" for key, val in shown[:limit]]
        extra = len(shown) - limit
        return ", ".join(items) + (f" … (+{extra})" if extra > 0 else "")
    if isinstance(value, (list, tuple, set)):
        items = [format_value(v, limit) for v in list(value)[:limit]]
        extra = len(value) - limit
        return ", ".join(items) + (f" … (+{extra})" if extra > 0 else "")
    return str(value)
