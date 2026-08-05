# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from ...config.settings import APP_NAME, BRAND, VERSION
from ..theme import CORAL, CREAM, FAINT, MARK, MUTED

KEYS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "navigation",
        (
            ("1 - 6", "jump straight to a tab"),
            ("[ ]", "previous / next tab"),
            ("↑ ↓", "move the row cursor"),
            ("pgup pgdn", "move a page at a time"),
            ("home end", "first / last row"),
            ("m", "back to the menu"),
            ("q  ctrl+c", "quit"),
        ),
    ),
    (
        "rows",
        (
            ("enter", "inspect the issue or pull request"),
            ("o", "open the selected row on github.com"),
            ("y", "copy the selected row's URL"),
            ("s", "cycle the sort order"),
            ("S", "reverse the current sort"),
            ("click header", "sort by that column"),
        ),
    ),
    (
        "data",
        (
            ("/", "focus the filter box"),
            ("esc", "clear the filter, then leave the box"),
            ("r", "sync with GitHub"),
            ("R", "clear the cache and do a full sync"),
            ("c", "measure code volume (code tab)"),
            ("e", "export this view to a file"),
            ("?", "this help"),
        ),
    ),
)

FILTERS: tuple[tuple[str, str], ...] = (
    ("repo:api", "repository name contains 'api'"),
    ("owner:acme", "everything under one account"),
    ("author:octocat", "opened by that person"),
    ("label:bug", "carries that label"),
    ("assignee:me", "assigned to a given login"),
    ("reviewer:octocat", "pull requests waiting on that reviewer"),
    ("is:stale", "untouched for more than 30 days"),
    ("is:failing", "pull requests with red CI"),
    ("is:conflicts", "pull requests that cannot merge"),
    ("is:draft", "draft pull requests"),
    ("is:unassigned", "issues with nobody on them"),
    ("lang:rust", "code tab: repositories using a language"),
    ("is:mine", "code tab: repositories you committed to"),
    ("-label:wip", "negate any qualifier with a dash"),
    ("payment retry", "bare words match the title and repository"),
)


class HelpScreen(ModalScreen):

    def compose(self) -> ComposeResult:
        with Vertical(id="help-card"):
            yield Static(self._content(), id="help-body")

    def on_mount(self) -> None:
        card = self.query_one("#help-card")
        card.border_title = f"[{CORAL}]{MARK}[/] keys & filters"
        card.border_subtitle = "press any key to close"

    def _content(self) -> RenderableType:
        layout = Table.grid(padding=(0, 6))
        layout.add_column(justify="left", vertical="top")
        layout.add_column(justify="left", vertical="top")
        layout.add_row(self._keys_column(), self._filters_column())
        return Group(layout, self._about())

    def _about(self) -> Text:
        text = Text(no_wrap=True, overflow="ellipsis")
        text.append(f"\n{APP_NAME.lower()} {VERSION}", style=CREAM)
        text.append(f"  ·  © 2026 {BRAND}", style=MUTED)
        text.append("  ·  ", style=FAINT)
        text.append("GNU GPL v3 or later", style=MUTED)
        text.append("  ·  free software, no warranty", style=FAINT)
        return text

    def _keys_column(self) -> RenderableType:
        blocks: list[RenderableType] = []
        for title, rows in KEYS:
            blocks.append(Text(title, style=CREAM))
            table = Table.grid(padding=(0, 2))
            table.add_column(justify="right", style=CORAL, width=12, no_wrap=True)
            table.add_column(justify="left", style=MUTED, no_wrap=True)
            for key, caption in rows:
                table.add_row(key, caption)
            blocks += [table, Text("")]
        return Group(*blocks)

    def _filters_column(self) -> RenderableType:
        heading = Text("filter grammar", style=CREAM)

        grid = Table.grid(padding=(0, 2))
        grid.add_column(justify="left", style=CORAL, width=17, no_wrap=True)
        grid.add_column(justify="left", style=MUTED, no_wrap=True)
        for query, meaning in FILTERS:
            grid.add_row(query, meaning)

        footer = Text()
        footer.append("\nqualifiers combine with AND, and every tab", style=FAINT)
        footer.append("\nkeeps its own filter box", style=FAINT)

        return Group(heading, grid, footer)

    def on_key(self, event: events.Key) -> None:
        self.dismiss()
        event.stop()
        event.prevent_default()

    def on_click(self, event: events.Click) -> None:
        self.dismiss()
