# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Input, Static

from ..theme import CORAL, FAINT, MUTED


class FilterBar(Horizontal):

    class Changed(Message):
        def __init__(self, bar: "FilterBar", value: str) -> None:
            super().__init__()
            self.bar = bar
            self.value = value

    def __init__(self, placeholder: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.placeholder = placeholder
        self._shown = 0
        self._total = 0

    def compose(self) -> ComposeResult:
        yield Input(placeholder=self.placeholder, classes="filter-input")
        yield Static(classes="filter-summary")

    def on_mount(self) -> None:
        self.set_counts(0, 0)


    @property
    def input(self) -> Input:
        return self.query_one(Input)

    @property
    def value(self) -> str:
        return self.input.value

    def clear(self) -> None:
        self.input.value = ""

    def focus_input(self) -> None:
        self.input.focus()

    def set_counts(self, shown: int, total: int) -> None:
        self._shown, self._total = shown, total
        text = Text(no_wrap=True, justify="right")
        if total and shown != total:
            text.append(f"{shown:,}", style=CORAL)
            text.append(f" of {total:,}", style=MUTED)
        elif total:
            text.append(f"{total:,}", style=MUTED)
            text.append(" rows", style=FAINT)
        else:
            text.append("no rows", style=FAINT)
        self.query_one(Static).update(text)


    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self.post_message(self.Changed(self, event.value))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.screen.focus_next()
