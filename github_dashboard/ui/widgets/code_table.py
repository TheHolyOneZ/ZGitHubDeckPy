# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Sequence

from rich.text import Text

from ...models.data_types import RepoCode
from ...utils.filters import CODE_FIELDS, CODE_SEARCHABLE, Query
from ...utils.formatters import compact_number, language_style, shorten_repo
from ..theme import CORAL, CREAM, FAINT, GREEN, LINE, MUTED, RED
from .record_table import Column, RecordTable, Sort


class CodeTable(RecordTable):
    COLUMNS = (
        Column("repo", "repository", width=42),
        Column("language", "language", width=13),
        Column("lines", "lines now", width=10, justify="right"),
        Column("additions", "you added", width=11, justify="right"),
        Column("deletions", "you removed", width=12, justify="right"),
        Column("net", "net", width=11, justify="right"),
        Column("commits", "commits", width=8, justify="right"),
        Column("share", "share of your output", flex=True, min_width=12),
    )

    SORTS = (
        Sort("additions", "lines you added", lambda r: r.additions, reverse=True),
        Sort("lines", "repository size", lambda r: r.estimated_lines, reverse=True),
        Sort("net", "net lines", lambda r: r.net, reverse=True),
        Sort("commits", "commits", lambda r: r.commits, reverse=True),
        Sort("repo", "repository", lambda r: r.repo.lower(), reverse=False),
        Sort("language", "language", lambda r: (r.primary_language.lower(), -r.additions), reverse=False),
    )

    EMPTY_MESSAGE = "no code scanned yet — press c to measure every repository"
    NO_MATCH_MESSAGE = "no repositories match this filter"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._peak = 1
        self._total = 1

    def build_row(self, record: RepoCode, flex: int) -> Sequence[Text]:
        name = Text(no_wrap=True)
        name.append(shorten_repo(record.repo, 40), style=CORAL)
        if record.archived:
            name.append("  archived", style=FAINT)
        elif record.private:
            name.append("  private", style=FAINT)

        language = record.primary_language
        lang_cell = (
            Text(language, style=language_style(language), no_wrap=True)
            if language
            else Text("—", style=FAINT, no_wrap=True)
        )

        def number(value: int, style: str, sign: str = "") -> Text:
            if not value:
                return Text("·", style=FAINT, no_wrap=True, justify="right")
            return Text(
                f"{sign}{value:,}", style=style, no_wrap=True, justify="right"
            )

        net = record.net
        net_cell = Text(
            f"{net:+,}" if net else "·",
            style=(GREEN if net > 0 else RED if net < 0 else FAINT),
            no_wrap=True,
            justify="right",
        )

        lines = Text(
            f"{record.estimated_lines:,}" if record.estimated_lines else "·",
            style=CREAM if record.estimated_lines else FAINT,
            no_wrap=True,
            justify="right",
        )
        if not record.stats_ready:
            lines = Text("computing…", style=FAINT, no_wrap=True, justify="right")

        return (
            name,
            lang_cell,
            lines,
            number(record.additions, GREEN, "+"),
            number(record.deletions, RED, "−"),
            net_cell,
            number(record.commits, MUTED),
            self._share(record, flex),
        )

    def _share(self, record: RepoCode, flex: int) -> Text:
        width = max(flex - 8, 6)
        fraction = record.additions / self._peak if self._peak else 0.0
        filled = int(round(min(fraction, 1.0) * width))

        bar = Text(no_wrap=True, overflow="crop")
        bar.append("━" * filled, style=language_style(record.primary_language))
        bar.append("━" * (width - filled), style=LINE)
        if record.additions and self._total:
            bar.append(f" {record.additions / self._total * 100:4.1f}%", style=FAINT)
        return bar

    def filter_records(self, records: Sequence[RepoCode], text: str) -> list[RepoCode]:
        visible = Query.parse(text).apply(records, CODE_FIELDS, CODE_SEARCHABLE)
        self._peak = max((item.additions for item in visible), default=1) or 1
        self._total = sum(item.additions for item in visible) or 1
        return visible


def compact(value: int) -> str:
    return compact_number(value)
