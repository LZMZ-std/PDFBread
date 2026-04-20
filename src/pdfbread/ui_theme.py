from __future__ import annotations

import re
from functools import lru_cache

from pdfbread.paths import app_resource

_SECTION_RE = re.compile(
    r"/\*<(?P<name>[a-z0-9_]+)>\*/(?P<body>.*?)/\*</(?P=name)>\*/",
    re.DOTALL,
)


@lru_cache(maxsize=1)
def _theme_sections() -> dict[str, str]:
    theme_path = app_resource("theme.qss")
    text = theme_path.read_text(encoding="utf-8")
    return {match.group("name"): match.group("body").strip() for match in _SECTION_RE.finditer(text)}


def _section(name: str) -> str:
    try:
        return _theme_sections()[name]
    except KeyError as exc:
        raise KeyError(f"Theme section '{name}' not found in theme.qss") from exc


def reload_theme() -> None:
    _theme_sections.cache_clear()


def main_window_stylesheet() -> str:
    return _section("main_window")


def workspace_stylesheet() -> str:
    return _section("workspace")


def settings_stylesheet() -> str:
    return _section("settings")


def preview_label_style() -> str:
    return _section("preview_label")


def empty_preview_label_style() -> str:
    return _section("empty_preview_label")


def slide_card_style(active: bool) -> str:
    template = _section("slide_card")
    border = "transparent" if active else "#30363d"
    bg = "transparent" if active else "#161b22"
    return template.replace("__BORDER__", border).replace("__BG__", bg)


def hint_label_style() -> str:
    return _section("hint_label")


def transport_button_style(is_running: bool, is_ready: bool = False) -> str:
    if is_running:
        return _section("transport_button_running")
    if is_ready:
        return _section("transport_button_ready")
    return _section("transport_button_disabled")


def transport_icon_color(is_ready: bool) -> str:
    return _section("transport_icon_ready" if is_ready else "transport_icon_idle").strip()


def output_status_icon_color(status: str) -> str:
    return _section(f"output_status_icon_{status}").strip()


def ndi_status_style(color: str) -> str:
    return _section("ndi_status").replace("__COLOR__", color)
