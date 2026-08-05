# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from ...config.settings import PREFERENCES
from ...utils.formatters import keyhint
from ..theme import CORAL, FAINT, LINE, MARK, MUTED
from ..widgets.common import ChoiceRow, RowCycle, RowHover, brand_line

INVALIDATES_CACHE = {
    "affiliation",
    "include_forks",
    "include_archived",
    "max_search_pages",
    "notifications_all",
}


class SettingsScreen(Screen):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.index = 0
        self.dirty = False

    def compose(self) -> ComposeResult:
        self.add_class("-centered")
        with Vertical(id="shell"):
            with Vertical(id="topbar"):
                yield Static(id="brand")
            with Vertical(id="options"):
                for preference in PREFERENCES:
                    yield ChoiceRow(preference)
            yield Static(id="help-line")
            yield Static(id="hint")

    def on_mount(self) -> None:
        left, _ = brand_line()
        self.query_one("#brand", Static).update(left)

        options = self.query_one("#options")
        options.border_title = f"[{CORAL}]{MARK}[/] settings"

        self.query_one("#hint", Static).update(
            keyhint(
                [
                    ("↑↓", "row"),
                    ("←→", "change"),
                    ("c", "clear cache"),
                    ("esc", "back"),
                ]
            )
        )
        self.refresh_rows()


    def refresh_rows(self) -> None:
        settings = self.app.settings
        for position, row in enumerate(self.query(ChoiceRow)):
            preference = row.preference
            row.value_label = preference.label_for(getattr(settings, preference.key))
            row.selected = position == self.index
            row.refresh()

        help_line = Text(justify="center", no_wrap=True, overflow="ellipsis")
        help_line.append(PREFERENCES[self.index].help, style=FAINT)
        if self.dirty:
            help_line.append("   ·   ", style=LINE)
            help_line.append("press r on the dashboard to resync", style=MUTED)
        self.query_one("#help-line", Static).update(help_line)

    def cycle(self, key: str, step: int) -> None:
        settings = self.app.settings
        preference = next((p for p in PREFERENCES if p.key == key), None)
        if preference is None:
            return

        current = preference.index_of(getattr(settings, preference.key))
        value = preference.values[(current + step) % len(preference.values)]
        setattr(settings, preference.key, value)
        settings.save()

        if preference.key in INVALIDATES_CACHE:
            self.dirty = True
        self.app.settings_changed(preference.key)
        self.refresh_rows()

    def move(self, step: int) -> None:
        self.index = (self.index + step) % len(PREFERENCES)
        self.refresh_rows()


    def on_row_hover(self, message: RowHover) -> None:
        keys = [preference.key for preference in PREFERENCES]
        if message.key in keys:
            self.index = keys.index(message.key)
            self.refresh_rows()

    def on_row_cycle(self, message: RowCycle) -> None:
        keys = [preference.key for preference in PREFERENCES]
        if message.key in keys:
            self.index = keys.index(message.key)
        self.cycle(message.key, message.step)

    def on_key(self, event: events.Key) -> None:
        key = event.key
        letter = (event.character or "").lower()
        current = PREFERENCES[self.index].key

        if key in ("up", "k", "shift+tab"):
            self.move(-1)
        elif key in ("down", "j", "tab"):
            self.move(1)
        elif key in ("left", "h"):
            self.cycle(current, -1)
        elif key in ("right", "l", "enter", "space"):
            self.cycle(current, 1)
        elif letter == "c":
            removed = self.app.cache.clear()
            self.app.notify(f"Cleared {removed} cached responses.", severity="warning")
            self.refresh_rows()
        elif key in ("escape", "backspace") or letter == "q":
            self.dismiss()
        else:
            return

        event.stop()
        event.prevent_default()
