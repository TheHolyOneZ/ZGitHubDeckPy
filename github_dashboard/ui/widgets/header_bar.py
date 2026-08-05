# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

import time

from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text
from textual.widget import Widget

from ...api.store import DataStore
from ...config.settings import APP_NAME
from ...utils.formatters import (
    compact_number,
    countdown,
    meter,
    rate_colour,
    time_ago,
)
from ..theme import CORAL, CREAM, FAINT, GREEN, LINE, MARK, MUTED, RED, SPINNER_FRAMES, YELLOW


class HeaderBar(Widget):

    def __init__(self, store: DataStore, **kwargs) -> None:
        super().__init__(**kwargs)
        self.store = store
        self._spin_timer = None

    def on_mount(self) -> None:
        self.set_interval(15.0, self.refresh)


    def set_busy(self, busy: bool) -> None:
        if busy and self._spin_timer is None:
            self._spin_timer = self.set_interval(0.09, self.refresh)
        elif not busy and self._spin_timer is not None:
            self._spin_timer.stop()
            self._spin_timer = None
        self.refresh()

    @property
    def _spinner(self) -> str:
        return SPINNER_FRAMES[int(time.monotonic() * 11) % len(SPINNER_FRAMES)]


    def render(self) -> RenderableType:
        return Group(self._identity_line(), self._counter_line(), self._rate_line())

    def _grid(self, left: Text, right: Text) -> Table:
        grid = Table.grid(expand=True, padding=0)
        grid.add_column(justify="left", ratio=1, overflow="ellipsis", no_wrap=True)
        grid.add_column(justify="right", width=max(right.cell_len, 1), no_wrap=True)
        grid.add_row(left, right)
        return grid

    def _identity_line(self) -> Table:
        store = self.store
        left = Text(no_wrap=True)
        left.append(f"{MARK} ", style=f"bold {CORAL}")
        left.append(APP_NAME.lower(), style=f"bold {CREAM}")
        left.append("  ·  ", style=LINE)

        if store.viewer:
            left.append(f"@{store.viewer.login}", style=CREAM)
            if store.viewer.name:
                left.append(f"  {store.viewer.name}", style=FAINT)
        else:
            left.append("not signed in", style=FAINT)

        return self._grid(left, self._sync_text())

    def _sync_text(self) -> Text:
        state = self.store.sync_state
        text = Text(no_wrap=True)

        if state.running:
            text.append(f"{self._spinner} ", style=CORAL)
            text.append(state.label(), style=CREAM)
            if state.detail:
                text.append(f" · {state.detail}", style=MUTED)
            text.append(f"  {int(state.fraction * 100)}%", style=FAINT)
            return text

        if state.errors:
            text.append("! ", style=RED)
            text.append(f"{len(state.errors)} issue(s)", style=RED)
            text.append("  ·  ", style=LINE)

        if self.store.synced_at:
            marker = "cached" if self.store.loaded_from_snapshot else "synced"
            text.append(marker, style=FAINT)
            text.append(f" {time_ago(self.store.synced_at)}", style=MUTED)
        else:
            text.append("never synced", style=FAINT)
        return text

    def _counter_line(self) -> Table:
        store = self.store
        left = Text(no_wrap=True)

        def stat(label: str, value: str, style: str = CREAM, warn: bool = False) -> None:
            if left.plain:
                left.append("   ", style=LINE)
            left.append(value, style=f"bold {RED if warn else style}")
            left.append(f" {label}", style=MUTED)

        stat("repos", str(store.repo_count))
        stat("issues", str(len(store.issues)), CORAL)
        stat("pulls", str(len(store.pulls)), CORAL)
        if store.review_requests:
            stat("to review", str(store.review_requests), YELLOW)
        if store.failing_pulls:
            stat("failing", str(store.failing_pulls), RED, warn=True)
        stat("stars", compact_number(store.total_stars), YELLOW)
        if store.unread_count:
            stat("unread", str(store.unread_count), GREEN)

        right = Text(no_wrap=True)
        if store.sync_state.truncated:
            right.append("partial results", style=YELLOW)
        elif store.repos:
            forks = store.total_forks
            right.append(f"{compact_number(forks)} forks", style=FAINT)
        return self._grid(left, right)

    def _rate_line(self) -> Table:
        rate = self.store.rate
        left = Text(no_wrap=True)
        left.append("api ", style=FAINT)

        if rate is None or rate.limit <= 0:
            left.append("rate limit unknown", style=FAINT)
            return self._grid(left, Text())

        colour = rate_colour(rate.fraction)
        left.append_text(meter(rate.fraction, width=16, colour=colour))
        left.append(f"  {rate.remaining}", style=colour)
        left.append(f"/{rate.limit}", style=FAINT)
        left.append("  ·  ", style=LINE)
        left.append(f"resets in {countdown(rate.reset_at)}", style=MUTED)

        right = Text(no_wrap=True)
        if rate.fraction <= 0.1:
            right.append("throttling — using cache", style=RED)
        return self._grid(left, right)
