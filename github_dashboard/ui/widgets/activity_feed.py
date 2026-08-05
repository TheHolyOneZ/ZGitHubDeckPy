# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from rich.text import Text

from ...models.data_types import ActivityEvent, Notification
from ...utils.filters import (
    EVENT_FIELDS,
    EVENT_SEARCHABLE,
    NOTIFICATION_FIELDS,
    NOTIFICATION_SEARCHABLE,
    Query,
)
from ...utils.formatters import event_badge, time_ago, truncate
from ..theme import CORAL, CREAM, FAINT, GREEN, MUTED
from .stream_feed import FeedRow, StreamFeed, day_bucket, separator

_EPOCH = datetime.fromtimestamp(0, timezone.utc)


class ActivityFeed(StreamFeed):
    EMPTY_MESSAGE = "no recent activity — press r to sync"
    NO_MATCH_MESSAGE = "nothing here matches this filter"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.notifications: list[Notification] = []
        self.viewer_login = ""

    def set_notifications(self, notifications: Sequence[Notification]) -> None:
        self.notifications = list(notifications)
        self.rebuild()


    def build_rows(self, records: Sequence[ActivityEvent], width: int) -> list[FeedRow]:
        rows: list[FeedRow] = []
        repo_width = max(min(width - 58, 34), 16)

        notifications = Query.parse(self.filter_text).apply(
            self.notifications, NOTIFICATION_FIELDS, NOTIFICATION_SEARCHABLE
        )
        if notifications:
            unread = sum(1 for item in notifications if item.unread)
            rows.append(separator(f"notifications · {unread} unread", width))
            notifications.sort(
                key=lambda item: (item.unread, item.updated_at or _EPOCH), reverse=True
            )
            for item in notifications[:40]:
                rows.append(self._notification_row(item, repo_width))
            rows.append(FeedRow(Text("")))

        current_bucket: str | None = None
        for event in records:
            bucket = day_bucket(event.created_at, self.date_style)
            if bucket != current_bucket:
                if current_bucket is not None:
                    rows.append(FeedRow(Text("")))
                rows.append(separator(bucket, width))
                current_bucket = bucket
            rows.append(self._event_row(event, repo_width, width))

        return rows

    def _notification_row(self, item: Notification, repo_width: int) -> FeedRow:
        line = Text(no_wrap=True, overflow="crop")
        line.append(f"{time_ago(item.updated_at, self.date_style):>5}  ", style=FAINT)
        line.append("● " if item.unread else "○ ", style=GREEN if item.unread else FAINT)
        line.append(f"{truncate(item.reason, 12):<12}  ", style=MUTED)
        line.append(f"{truncate(item.repo, repo_width):<{repo_width}}  ", style=CORAL)
        line.append(truncate(item.title, 60), style=CREAM if item.unread else MUTED)
        return FeedRow(line, payload=item)

    def _event_row(self, event: ActivityEvent, repo_width: int, width: int) -> FeedRow:
        line = Text(no_wrap=True, overflow="crop")
        line.append(f"{time_ago(event.created_at, self.date_style):>5}  ", style=FAINT)

        badge = event_badge(event.kind)
        badge.pad_right(max(9 - badge.cell_len, 0))
        line.append_text(badge)

        actor_style = f"bold {CORAL}" if event.actor == self.viewer_login else MUTED
        line.append(f"{truncate(event.actor, 16):<16}  ", style=actor_style)
        line.append(f"{truncate(event.repo, repo_width):<{repo_width}}  ", style=CORAL)

        remaining = max(width - 32 - repo_width, 20)
        line.append(truncate(event.summary, remaining), style=CREAM)
        return FeedRow(line, payload=event)

    def filter_records(
        self, records: Sequence[ActivityEvent], text: str
    ) -> list[ActivityEvent]:
        return Query.parse(text).apply(records, EVENT_FIELDS, EVENT_SEARCHABLE)
