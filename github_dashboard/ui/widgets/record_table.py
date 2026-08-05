# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from rich.text import Text
from textual.message import Message
from textual.widgets import DataTable

from ..theme import CORAL, FAINT, MUTED

SortFn = Callable[[Any], Any]


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    width: int | None = None
    flex: bool = False
    justify: str = "left"
    min_width: int = 8


@dataclass(frozen=True)
class Sort:
    key: str
    label: str
    fn: SortFn
    reverse: bool = True


class RecordTable(DataTable):

    COLUMNS: tuple[Column, ...] = ()
    SORTS: tuple[Sort, ...] = ()
    EMPTY_MESSAGE = "nothing here yet"
    NO_MATCH_MESSAGE = "no rows match this filter"

    class RecordSelected(Message):
        def __init__(self, table: "RecordTable", record: Any) -> None:
            super().__init__()
            self.table = table
            self.record = record

        @property
        def control(self) -> "RecordTable":
            return self.table

    class RecordHighlighted(Message):
        def __init__(self, table: "RecordTable", record: Any | None) -> None:
            super().__init__()
            self.table = table
            self.record = record

        @property
        def control(self) -> "RecordTable":
            return self.table

    class CountsChanged(Message):
        def __init__(self, table: "RecordTable", shown: int, total: int) -> None:
            super().__init__()
            self.table = table
            self.shown = shown
            self.total = total

        @property
        def control(self) -> "RecordTable":
            return self.table

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = False
        self.records: list[Any] = []
        self.visible_records: list[Any] = []
        self.filter_text: str = ""
        self.sort_index: int = 0
        self.sort_reverse: bool = True
        self._flex_width: int = 40
        self._built_for_width: int = -1


    def build_row(self, record: Any, flex: int) -> Sequence[Any]:
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
        self.rebuild()

    @property
    def current_sort(self) -> Sort | None:
        if not self.SORTS:
            return None
        return self.SORTS[self.sort_index % len(self.SORTS)]

    def cycle_sort(self, step: int = 1) -> str:
        if not self.SORTS:
            return ""
        self.sort_index = (self.sort_index + step) % len(self.SORTS)
        self.sort_reverse = self.SORTS[self.sort_index].reverse
        self.rebuild()
        return self.SORTS[self.sort_index].label

    def toggle_direction(self) -> None:
        self.sort_reverse = not self.sort_reverse
        self.rebuild()

    def sort_by(self, key: str) -> None:
        for index, sort in enumerate(self.SORTS):
            if sort.key == key:
                if index == self.sort_index:
                    self.toggle_direction()
                else:
                    self.sort_index = index
                    self.sort_reverse = sort.reverse
                    self.rebuild()
                return

    @property
    def highlighted_record(self) -> Any | None:
        row = self.cursor_row
        if 0 <= row < len(self.visible_records):
            return self.visible_records[row]
        return None


    def _measure(self) -> int:
        fixed = sum(
            (column.width or column.min_width) + 2
            for column in self.COLUMNS
            if not column.flex
        )
        flexible = [column for column in self.COLUMNS if column.flex]
        if not flexible:
            return 0
        available = self.size.width - fixed - 4
        return max(available // len(flexible), flexible[0].min_width)

    def on_resize(self) -> None:
        width = self._measure()
        if abs(width - self._flex_width) >= 2:
            self._flex_width = width
            self.rebuild()


    def rebuild(self) -> None:
        remembered = self.cursor_row
        self.clear(columns=True)

        self._flex_width = self._measure() or self._flex_width
        for column in self.COLUMNS:
            width = self._flex_width if column.flex else column.width
            label = Text(column.label, style=MUTED, justify=column.justify)
            if self.current_sort and self.current_sort.key == column.key:
                label = Text(no_wrap=True)
                label.append("▼ " if self.sort_reverse else "▲ ", style=CORAL)
                label.append(column.label, style=CORAL)
            self.add_column(label, width=width, key=column.key)

        records = self.filter_records(self.records, self.filter_text)
        sort = self.current_sort
        if sort is not None:
            try:
                records = sorted(records, key=sort.fn, reverse=self.sort_reverse)
            except TypeError:
                pass

        self.visible_records = records

        if not records:
            message = self.EMPTY_MESSAGE if not self.records else self.NO_MATCH_MESSAGE
            slot = next(
                (index for index, column in enumerate(self.COLUMNS) if column.flex), 0
            )
            cells = [Text("") for _ in self.COLUMNS]
            cells[slot] = Text(message, style=FAINT, no_wrap=True)
            self.add_row(*cells)
            self.post_message(self.CountsChanged(self, 0, len(self.records)))
            return

        for index, record in enumerate(records):
            self.add_row(*self.build_row(record, self._flex_width), key=str(index))

        if records and remembered:
            self.move_cursor(row=min(remembered, len(records) - 1), animate=False)

        self.post_message(self.CountsChanged(self, len(records), len(self.records)))


    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        event.stop()
        record = self.highlighted_record
        if record is not None:
            self.post_message(self.RecordSelected(self, record))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        event.stop()
        self.post_message(self.RecordHighlighted(self, self.highlighted_record))

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        event.stop()
        if event.column_key.value:
            self.sort_by(str(event.column_key.value))
