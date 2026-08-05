# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

import webbrowser

from rich.console import Group, RenderableType
from rich.text import Text
from textual import events
from textual.widget import Widget

from ...config.settings import APP_NAME, BRAND, TAGLINE, VERSION
from ..theme import (
    CORAL,
    CREAM,
    FAINT,
    GREEN,
    LINE,
    LOGO,
    LOGO_SHADES,
    LOGO_SHADOW,
    LOGO_WIDTH,
    MARK,
    MUTED,
)

LINKS: tuple[tuple[str, str, str], ...] = (
    ("project", "source, issues and releases", "https://github.com/TheHolyOneZ/ZGitHubDeckPy"),
    ("author", "everything else I have built", "https://github.com/TheHolyOneZ"),
    ("more projects", "the rest of my work", "https://zsync.eu/"),
)

CREDITS: tuple[tuple[str, str], ...] = (
    ("Textual", "the terminal UI framework"),
    ("Rich", "the rendering underneath it"),
    ("httpx", "the async HTTP client"),
)


class AboutPanel(Widget, can_focus=True):

    BINDINGS = [
        ("up,k", "move(-1)", "up"),
        ("down,j", "move(1)", "down"),
        ("enter", "open", "open"),
        ("y", "copy", "copy url"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.cursor = 0


    def action_move(self, step: int) -> None:
        self.cursor = (self.cursor + step) % len(LINKS)
        self.refresh()

    @property
    def selected_url(self) -> str:
        return LINKS[self.cursor][2]

    def action_open(self) -> None:
        url = self.selected_url
        try:
            webbrowser.open(url)
            self.app.notify(f"Opened {url}")
        except Exception:
            self.app.notify(f"Open this yourself: {url}", severity="warning", timeout=10)

    def action_copy(self) -> None:
        self.app.copy_to_clipboard(self.selected_url)
        self.app.notify("Link copied to the clipboard.")

    def on_click(self, event: events.Click) -> None:
        first_row = len(LOGO) + 5
        index = event.y - first_row
        if 0 <= index < len(LINKS):
            self.cursor = index
            self.refresh()
            self.action_open()


    def render(self) -> RenderableType:
        return Group(
            self._logo(),
            Text(""),
            self._identity(),
            Text(""),
            *self._links(),
            Text(""),
            self._hint(),
            Text(""),
            self._licence(),
            self._credits(),
        )

    def _logo(self) -> Text:
        if self.size.width < LOGO_WIDTH + 4:
            small = Text()
            small.append(f"  {MARK} ", style=f"bold {CORAL}")
            small.append(APP_NAME, style=f"bold {CREAM}")
            return small

        art = Text(no_wrap=True, overflow="crop")
        for index, line in enumerate(LOGO):
            shade = LOGO_SHADES[index % len(LOGO_SHADES)]
            art.append("  ")
            for char in line.ljust(LOGO_WIDTH):
                art.append(char, style=shade if char == "█" else LOGO_SHADOW)
            if index < len(LOGO) - 1:
                art.append("\n")
        return art

    def _identity(self) -> Group:
        title = Text(no_wrap=True)
        title.append("  ")
        title.append(f"{APP_NAME.lower()} {VERSION}", style=f"bold {CREAM}")
        title.append("  ·  ", style=LINE)
        title.append(TAGLINE, style=MUTED)

        blurb = Text(no_wrap=True, overflow="ellipsis")
        blurb.append(
            "  A GitHub management and activity dashboard for the terminal — every "
            "repository you own, in one place.",
            style=FAINT,
        )
        return Group(title, blurb)

    def _links(self) -> list[Text]:
        rows: list[Text] = []
        label_width = max(len(label) for label, _, _ in LINKS)
        url_width = max(len(url) for _, _, url in LINKS)

        for index, (label, blurb, url) in enumerate(LINKS):
            selected = index == self.cursor and self.has_focus
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append("  ▸ " if index == self.cursor else "    ", style=CORAL)
            row.append(
                f"{label:<{label_width}}   ",
                style=f"bold {CREAM}" if selected else CREAM,
            )
            row.append(url, style=f"bold {CORAL}" if selected else CORAL)
            row.append(" " * (url_width - len(url)))
            row.append(f"   {blurb}", style=MUTED if selected else FAINT)
            rows.append(row)
        return rows

    def _hint(self) -> Text:
        text = Text(no_wrap=True)
        text.append("    ", style=FAINT)
        text.append("↑↓", style=CORAL)
        text.append(" choose  ", style=FAINT)
        text.append("enter", style=CORAL)
        text.append(" open in browser  ", style=FAINT)
        text.append("y", style=CORAL)
        text.append(" copy the link", style=FAINT)
        return text

    def _licence(self) -> Text:
        text = Text(no_wrap=True, overflow="ellipsis")
        text.append("  © 2026 ", style=FAINT)
        text.append(BRAND, style=MUTED)
        text.append("  ·  ", style=LINE)
        text.append("GNU General Public License v3.0 or later", style=GREEN)
        text.append("  ·  free software, no warranty", style=FAINT)
        return text

    def _credits(self) -> Text:
        text = Text(no_wrap=True, overflow="ellipsis")
        text.append("  built with ", style=FAINT)
        for index, (name, what) in enumerate(CREDITS):
            if index:
                text.append(", ", style=FAINT)
            text.append(name, style=MUTED)
            text.append(f" ({what})", style=FAINT)
        return text
