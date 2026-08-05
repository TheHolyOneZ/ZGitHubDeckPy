# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from rich.text import Text

from ...models.data_types import PullRequest
from ...utils.filters import PR_FIELDS, PR_SEARCHABLE, Query
from ...utils.formatters import (
    aged,
    author_text,
    check_badge,
    merge_badge,
    review_badge,
    shorten_repo,
    truncate,
)
from ..theme import CORAL, CREAM, FAINT, MUTED
from .record_table import Column, RecordTable, Sort

_EPOCH = datetime.fromtimestamp(0, timezone.utc)

_URGENCY = {
    "conflicts": 5,
    "blocked": 4,
    "unstable": 3,
    "behind": 2,
    "ready": 1,
    "draft": 0,
    "—": 0,
}
_CHECK_URGENCY = {"failure": 3, "pending": 2, "neutral": 1, "success": 0, "unknown": 0}


class PRTable(RecordTable):
    COLUMNS = (
        Column("repo", "repository", width=24),
        Column("number", "#", width=6, justify="right"),
        Column("title", "title", flex=True, min_width=20),
        Column("author", "author", width=14),
        Column("review", "review", width=11),
        Column("checks", "checks", width=13),
        Column("merge", "merge", width=11),
        Column("age", "age", width=5, justify="right"),
    )

    SORTS = (
        Sort(
            "merge",
            "needs attention",
            lambda p: (
                _URGENCY.get(p.merge_verdict, 0) + _CHECK_URGENCY.get(p.checks.state, 0),
                p.updated_at or _EPOCH,
            ),
            reverse=True,
        ),
        Sort("age", "age", lambda p: p.created_at or _EPOCH, reverse=True),
        Sort("updated", "recently updated", lambda p: p.updated_at or _EPOCH, reverse=True),
        Sort("review", "pending reviews", lambda p: len(p.reviewers), reverse=True),
        Sort("repo", "repository", lambda p: (p.repo.lower(), p.number), reverse=False),
        Sort("author", "author", lambda p: (p.author.lower(), p.repo.lower()), reverse=False),
    )

    EMPTY_MESSAGE = "no open pull requests — press r to sync"
    NO_MATCH_MESSAGE = "no pull requests match this filter"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.viewer_login = ""
        self.date_style = "relative"

    def build_row(self, record: PullRequest, flex: int) -> Sequence[Text]:
        title = Text(no_wrap=True)
        if record.draft:
            title.append("◌ ", style=FAINT)
        title.append(
            truncate(record.title or "(no title)", flex - (2 if record.draft else 0)),
            style=MUTED if record.draft else CREAM,
        )

        return (
            Text(shorten_repo(record.repo, 24), style=CORAL, no_wrap=True),
            Text(f"#{record.number}", style=FAINT, no_wrap=True, justify="right"),
            title,
            author_text(record.author, self.viewer_login),
            review_badge(record.review_state),
            check_badge(record.checks),
            merge_badge(record.merge_verdict),
            aged(record.created_at, self.date_style),
        )

    def filter_records(self, records: Sequence[PullRequest], text: str) -> list[PullRequest]:
        return Query.parse(text).apply(records, PR_FIELDS, PR_SEARCHABLE)
