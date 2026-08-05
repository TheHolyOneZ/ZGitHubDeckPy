# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from rich.text import Text

from ...models.data_types import Issue
from ...utils.filters import ISSUE_FIELDS, ISSUE_SEARCHABLE, Query
from ...utils.formatters import (
    aged,
    author_text,
    render_labels,
    shorten_repo,
    truncate,
)
from ..theme import CORAL, CREAM, FAINT, MUTED
from .record_table import Column, RecordTable, Sort

_EPOCH = datetime.fromtimestamp(0, timezone.utc)


class IssueTable(RecordTable):
    COLUMNS = (
        Column("repo", "repository", width=24),
        Column("number", "#", width=6, justify="right"),
        Column("title", "title", flex=True, min_width=24),
        Column("author", "author", width=15),
        Column("labels", "labels", width=24),
        Column("age", "age", width=5, justify="right"),
        Column("comments", "···", width=4, justify="right"),
    )

    SORTS = (
        Sort("age", "age", lambda i: i.created_at or _EPOCH, reverse=True),
        Sort("updated", "recently updated", lambda i: i.updated_at or _EPOCH, reverse=True),
        Sort("repo", "repository", lambda i: (i.repo.lower(), i.number), reverse=False),
        Sort("author", "author", lambda i: (i.author.lower(), i.repo.lower()), reverse=False),
        Sort("comments", "comments", lambda i: i.comments, reverse=True),
        Sort("labels", "label count", lambda i: len(i.labels), reverse=True),
    )

    EMPTY_MESSAGE = "no open issues — press r to sync"
    NO_MATCH_MESSAGE = "no issues match this filter"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.viewer_login = ""
        self.date_style = "relative"

    def build_row(self, record: Issue, flex: int) -> Sequence[Text]:
        title = Text(truncate(record.title or "(no title)", flex), style=CREAM, no_wrap=True)

        number = Text(f"#{record.number}", style=FAINT, no_wrap=True, justify="right")

        comments = (
            Text(str(record.comments), style=MUTED, no_wrap=True, justify="right")
            if record.comments
            else Text("·", style=FAINT, no_wrap=True, justify="right")
        )

        repo = Text(shorten_repo(record.repo, 24), style=CORAL, no_wrap=True)

        return (
            repo,
            number,
            title,
            author_text(record.author, self.viewer_login),
            render_labels(record.labels, width=24),
            aged(record.created_at, self.date_style),
            comments,
        )

    def filter_records(self, records: Sequence[Issue], text: str) -> list[Issue]:
        return Query.parse(text).apply(records, ISSUE_FIELDS, ISSUE_SEARCHABLE)
