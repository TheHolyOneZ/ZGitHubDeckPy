# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Sequence

from rich.text import Text

from ...models.data_types import StarEvent
from ...utils.filters import STAR_FIELDS, STAR_SEARCHABLE, Query
from ...utils.formatters import compact_number, time_ago, truncate
from ..theme import CORAL, CREAM, FAINT, MUTED, YELLOW
from .stream_feed import FeedRow, StreamFeed, day_bucket, separator


class StarsFeed(StreamFeed):
    EMPTY_MESSAGE = "no stargazers found — enable 'star scan' in settings, then sync"
    NO_MATCH_MESSAGE = "no stargazers match this filter"

    def build_rows(self, records: Sequence[StarEvent], width: int) -> list[FeedRow]:
        rows: list[FeedRow] = []
        current_bucket: str | None = None

        repo_width = max(min(width - 46, 44), 18)
        user_width = 20

        for event in records:
            bucket = day_bucket(event.starred_at, self.date_style)
            if bucket != current_bucket:
                if rows:
                    rows.append(FeedRow(Text("")))
                rows.append(separator(bucket, width))
                current_bucket = bucket

            line = Text(no_wrap=True, overflow="crop")
            line.append(f"{time_ago(event.starred_at, self.date_style):>5}  ", style=FAINT)
            line.append("★ ", style=YELLOW)
            line.append(f"{truncate(event.user, user_width):<{user_width}}", style=CREAM)
            line.append("  starred  ", style=MUTED)
            line.append(
                f"{truncate(event.repo, repo_width):<{repo_width}}", style=CORAL
            )
            line.append(f"{compact_number(event.repo_stars):>7}", style=MUTED)
            line.append(" total", style=FAINT)
            rows.append(FeedRow(line, payload=event))

        return rows

    def filter_records(self, records: Sequence[StarEvent], text: str) -> list[StarEvent]:
        return Query.parse(text).apply(records, STAR_FIELDS, STAR_SEARCHABLE)
