# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from rich.console import Group
from rich.text import Text
from textual import events
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Static

from ...utils.formatters import time_ago
from ..theme import FAINT, LINE, SELECT


@dataclass
class FeedRow:

    text: Text
    payload: Any | None = None


class StreamFeed(VerticalScroll, can_focus=True):
    EMPTY_MESSAGE = "nothing to show yet"
    NO_MATCH_MESSAGE = "nothing matches this filter"

    class RecordSelected(Message):
        def __init__(self, feed: "StreamFeed", record: Any) -> None:
            super().__init__()
            self.feed = feed
            self.record = record

        @property
        def control(self) -> "StreamFeed":
            return self.feed

    class RecordHighlighted(Message):
        def __init__(self, feed: "StreamFeed", record: Any | None) -> None:
            super().__init__()
            self.feed = feed
            self.record = record

        @property
        def control(self) -> "StreamFeed":
            return self.feed

    class CountsChanged(Message):
        def __init__(self, feed: "StreamFeed", shown: int, total: int) -> None:
            super().__init__()
            self.feed = feed
            self.shown = shown
            self.total = total

        @property
        def control(self) -> "StreamFeed":
            return self.feed

    BINDINGS = [
        ("up,k", "move(-1)", "up"),
        ("down,j", "move(1)", "down"),
        ("pageup", "move(-10)", "page up"),
        ("pagedown", "move(10)", "page down"),
        ("home", "jump(0)", "top"),
        ("end", "jump(-1)", "bottom"),
        ("enter", "choose", "open"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.records: list[Any] = []
        self.visible_records: list[Any] = []
        self.rows: list[FeedRow] = []
        self.filter_text: str = ""
        self.date_style: str = "relative"
        self.cursor: int = 0
        self._body: Static | None = None

    def compose(self):
        self._body = Static(id="feed-body", markup=False)
        yield self._body


    def build_rows(self, records: Sequence[Any], width: int) -> list[FeedRow]:
        raise NotImplementedError

    def filter_records(self, records: Sequence[Any], text: str) -> list[Any]:
        raise NotImplementedError


    def set_records(self, records: Sequence[Any]) -> None:
        self.records = list(records)
        self.rebuild()

    def set_filter(self, text: str) -> None:
        if text == self.filter_text:
            return
        self.filter_text = text
        self.cursor = 0
        self.rebuild()

    @property
    def selectable(self) -> list[int]:
        return [index for index, row in enumerate(self.rows) if row.payload is not None]

    @property
    def highlighted_record(self) -> Any | None:
        if 0 <= self.cursor < len(self.rows):
            return self.rows[self.cursor].payload
        return None


    def on_resize(self) -> None:
        self.rebuild()

    def rebuild(self) -> None:
        if self._body is None:
            return

        width = self._content_width()
        self.visible_records = self.filter_records(self.records, self.filter_text)

        self.rows = self.build_rows(self.visible_records, width)
        if not self.rows:
            message = self.EMPTY_MESSAGE if not self.records else self.NO_MATCH_MESSAGE
            self.rows = [FeedRow(Text(f"\n  {message}", style=FAINT))]

        selectable = self.selectable
        if selectable:
            if self.cursor not in selectable:
                self.cursor = selectable[0]
        else:
            self.cursor = -1

        self._paint(width)
        self.post_message(self.RecordHighlighted(self, self.highlighted_record))
        self.post_message(
            self.CountsChanged(self, len(self.visible_records), len(self.records))
        )

    def _paint(self, width: int) -> None:
        if self._body is None:
            return
        lines: list[Text] = []
        for index, row in enumerate(self.rows):
            text = row.text.copy()
            if index == self.cursor and row.payload is not None:
                text.pad_right(max(width - text.cell_len, 0))
                text.stylize(f"on {SELECT}")
            lines.append(text)
        self._body.update(Group(*lines))

    def _content_width(self) -> int:
        return max(self.size.width - 5, 30)

    def _repaint(self) -> None:
        self._paint(self._content_width())
        self.post_message(self.RecordHighlighted(self, self.highlighted_record))

    def _reveal(self) -> None:
        height = self.size.height
        if height <= 0:
            return
        top = self.scroll_offset.y
        if self.cursor < top + 1:
            self.scroll_to(y=max(self.cursor - 1, 0), animate=False)
        elif self.cursor > top + height - 2:
            self.scroll_to(y=max(self.cursor - height + 2, 0), animate=False)


    def action_move(self, step: int) -> None:
        selectable = self.selectable
        if not selectable:
            return
        try:
            position = selectable.index(self.cursor)
        except ValueError:
            position = 0
        position = max(0, min(position + step, len(selectable) - 1))
        self.cursor = selectable[position]
        self._repaint()
        self._reveal()

    def action_jump(self, where: int) -> None:
        selectable = self.selectable
        if not selectable:
            return
        self.cursor = selectable[0] if where == 0 else selectable[-1]
        self._repaint()
        self._reveal()

    def action_choose(self) -> None:
        record = self.highlighted_record
        if record is not None:
            self.post_message(self.RecordSelected(self, record))

    def on_click(self, event: events.Click) -> None:
        target = self.scroll_offset.y + event.y - 1
        if 0 <= target < len(self.rows) and self.rows[target].payload is not None:
            self.cursor = target
            self._repaint()


def day_bucket(moment, style: str = "relative") -> str:
    label = time_ago(moment, style)
    if label in ("now", "—"):
        return "today"
    if label.endswith("m") or label.endswith("h"):
        return "today"
    if label == "1d":
        return "yesterday"
    return label


def separator(label: str, width: int) -> FeedRow:
    text = Text(no_wrap=True)
    text.append("── ", style=LINE)
    text.append(label, style=FAINT)
    text.append(" ", style=LINE)
    text.append("─" * max(width - len(label) - 4, 0), style=LINE)
    return FeedRow(text)
