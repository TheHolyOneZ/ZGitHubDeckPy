# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

import webbrowser
from dataclasses import dataclass
from typing import Any

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static, TabbedContent, TabPane

from ...api.store import SyncState
from ...models.data_types import ActivityEvent, Issue, Notification, PullRequest, StarEvent
from ...utils.formatters import compact_number, keyhint, stamp, truncate
from ..theme import CORAL, CREAM, FAINT, GREEN, LINE, MUTED, RED, YELLOW
from ..widgets.about_panel import AboutPanel
from ..widgets.activity_feed import ActivityFeed
from ..widgets.code_summary import CodeSummary
from ..widgets.code_table import CodeTable
from ..widgets.filter_bar import FilterBar
from ..widgets.header_bar import HeaderBar
from ..widgets.issue_table import IssueTable
from ..widgets.pr_table import PRTable
from ..widgets.record_table import RecordTable
from ..widgets.stars_feed import StarsFeed
from ..widgets.stream_feed import StreamFeed

TABS = ("issues", "pulls", "stars", "activity", "code", "about")

FILTER_HINTS = {
    "issues": "filter — repo:api  author:octocat  label:bug  is:stale  -label:wip",
    "pulls": "filter — repo:api  is:failing  is:conflicts  review-requested  is:draft",
    "stars": "filter — repo:name  user:login",
    "activity": "filter — repo:name  actor:login  type:push  is:fork",
    "code": "filter — repo:name  lang:rust  is:mine  is:archived  -is:empty",
}


@dataclass
class Panel:

    name: str
    bar: FilterBar
    view: Any


class MainScreen(Screen):
    BINDINGS = [
        ("r", "sync", "sync"),
        ("R", "hard_sync", "full sync"),
        ("slash", "focus_filter", "filter"),
        ("o", "open_browser", "open"),
        ("y", "copy_url", "copy url"),
        ("s", "cycle_sort", "sort"),
        ("S", "reverse_sort", "reverse"),
        ("e", "export", "export"),
        ("question_mark", "help", "help"),
        ("m", "menu", "menu"),
        ("1", "goto_tab('issues')", "issues"),
        ("2", "goto_tab('pulls')", "pull requests"),
        ("3", "goto_tab('stars')", "stars"),
        ("4", "goto_tab('activity')", "activity"),
        ("5", "goto_tab('code')", "code"),
        ("6", "goto_tab('about')", "about"),
        ("c", "scan_code", "scan code"),
        ("bracketright", "next_tab", "next tab"),
        ("bracketleft", "prev_tab", "previous tab"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.panels: dict[str, Panel] = {}
        self._highlight: Any | None = None


    def compose(self) -> ComposeResult:
        store = self.app.store
        with Vertical(id="dash"):
            yield HeaderBar(store, id="header")

            with TabbedContent(id="tabs", initial=f"tab-{self.app.settings.default_tab}"):
                with TabPane("issues", id="tab-issues"):
                    with Vertical(classes="tab-body"):
                        yield FilterBar(FILTER_HINTS["issues"], id="filter-issues")
                        yield IssueTable(id="table-issues")

                with TabPane("pull requests", id="tab-pulls"):
                    with Vertical(classes="tab-body"):
                        yield FilterBar(FILTER_HINTS["pulls"], id="filter-pulls")
                        yield PRTable(id="table-pulls")

                with TabPane("stars", id="tab-stars"):
                    with Vertical(classes="tab-body"):
                        yield FilterBar(FILTER_HINTS["stars"], id="filter-stars")
                        yield StarsFeed(id="feed-stars")

                with TabPane("activity", id="tab-activity"):
                    with Vertical(classes="tab-body"):
                        yield FilterBar(FILTER_HINTS["activity"], id="filter-activity")
                        yield ActivityFeed(id="feed-activity")

                with TabPane("code", id="tab-code"):
                    with Vertical(classes="tab-body"):
                        yield CodeSummary(id="code-summary")
                        yield FilterBar(FILTER_HINTS["code"], id="filter-code")
                        yield CodeTable(id="table-code")

                with TabPane("about", id="tab-about"):
                    yield AboutPanel(id="about-panel")

            yield Static(id="statusline")
            yield Static(id="dash-hint")

    def on_mount(self) -> None:
        self.panels = {
            "issues": Panel(
                "issues",
                self.query_one("#filter-issues", FilterBar),
                self.query_one("#table-issues", IssueTable),
            ),
            "pulls": Panel(
                "pulls",
                self.query_one("#filter-pulls", FilterBar),
                self.query_one("#table-pulls", PRTable),
            ),
            "stars": Panel(
                "stars",
                self.query_one("#filter-stars", FilterBar),
                self.query_one("#feed-stars", StarsFeed),
            ),
            "activity": Panel(
                "activity",
                self.query_one("#filter-activity", FilterBar),
                self.query_one("#feed-activity", ActivityFeed),
            ),
            "code": Panel(
                "code",
                self.query_one("#filter-code", FilterBar),
                self.query_one("#table-code", CodeTable),
            ),
        }

        self.query_one("#dash-hint", Static).update(
            keyhint(
                [
                    ("1-6", "tabs"),
                    ("/", "filter"),
                    ("enter", "inspect"),
                    ("o", "browser"),
                    ("s", "sort"),
                    ("r", "sync"),
                    ("c", "code"),
                    ("e", "export"),
                    ("?", "keys"),
                    ("m", "menu"),
                ]
            )
        )
        self.refresh_data()
        self.set_status()
        panel = self.active_panel
        if panel is not None:
            panel.view.focus()


    def refresh_data(self) -> None:
        store = self.app.store
        login = store.viewer.login if store.viewer else ""
        date_style = self.app.settings.date_style

        issues = self.panels["issues"].view
        issues.viewer_login = login
        issues.date_style = date_style
        issues.set_records(store.issues)

        pulls = self.panels["pulls"].view
        pulls.viewer_login = login
        pulls.date_style = date_style
        pulls.set_records(store.pulls)

        stars = self.panels["stars"].view
        stars.date_style = date_style
        stars.set_records(store.stars)

        activity = self.panels["activity"].view
        activity.viewer_login = login
        activity.date_style = date_style
        activity.notifications = list(store.notifications)
        activity.set_records(store.events)

        code = self.panels["code"].view
        code.set_records(store.code.repos)
        self.query_one("#code-summary", CodeSummary).update_stats(store.code)

        self._relabel_tabs()
        self.query_one("#header", HeaderBar).refresh()

    def _relabel_tabs(self) -> None:
        store = self.app.store
        tabs = self.query_one("#tabs", TabbedContent)
        counts = {
            "tab-issues": ("issues", len(store.issues), CORAL),
            "tab-pulls": ("pull requests", len(store.pulls), CORAL),
            "tab-stars": ("stars", len(store.stars), YELLOW),
            "tab-activity": ("activity", store.unread_count or len(store.events), GREEN),
            "tab-code": ("code", store.code.additions, GREEN),
            "tab-about": ("about", 0, MUTED),
        }
        for pane_id, (name, count, colour) in counts.items():
            label = Text(no_wrap=True)
            label.append(name)
            if count:
                label.append(f"  {compact_number(count)}", style=colour)
            try:
                tabs.get_tab(pane_id).label = label
            except Exception:
                pass

    def set_sync_state(self, state: SyncState) -> None:
        header = self.query_one("#header", HeaderBar)
        header.set_busy(state.running)
        if not state.running:
            self.refresh_data()
        self.set_status()


    @property
    def active_tab(self) -> str:
        active = self.query_one("#tabs", TabbedContent).active or ""
        return active.removeprefix("tab-") or "issues"

    @property
    def active_panel(self) -> Panel | None:
        return self.panels.get(self.active_tab)

    def set_status(self) -> None:
        if not self.panels:
            return
        widget = self.query_one("#statusline", Static)
        record = self._highlight
        text = Text(no_wrap=True, overflow="ellipsis")

        if record is None:
            panel = self.active_panel
            sort = getattr(panel.view, "current_sort", None) if panel else None
            if sort is not None:
                text.append("sorted by ", style=FAINT)
                text.append(sort.label, style=MUTED)
                text.append("  ·  ", style=LINE)
            errors = self.app.store.sync_state.errors
            if errors:
                text.append(truncate(errors[0], 90), style=RED)
            elif self.app.store.sync_state.truncated:
                text.append(
                    "results were capped — raise 'issue depth' in settings", style=YELLOW
                )
            elif self.active_tab == "about":
                text.append("zdeck is free software under the GNU GPL v3", style=FAINT)
                text.append("  ·  ", style=LINE)
                text.append("↑↓ then enter opens a link", style=MUTED)
            else:
                text.append("select a row to see its details", style=FAINT)
            widget.update(text)
            return

        widget.update(self._describe(record))

    def _describe(self, record: Any) -> Text:
        text = Text(no_wrap=True, overflow="ellipsis")

        if isinstance(record, (Issue, PullRequest)):
            text.append(record.slug, style=CORAL)
            text.append("  ·  ", style=LINE)
            text.append(f"opened {stamp(record.created_at)}", style=MUTED)
            text.append(" by ", style=FAINT)
            text.append(record.author, style=CREAM)

            if isinstance(record, PullRequest):
                if record.head_ref:
                    text.append("  ·  ", style=LINE)
                    text.append(f"{record.head_ref} → {record.base_ref}", style=MUTED)
                if record.changed_files:
                    text.append("  ·  ", style=LINE)
                    text.append(f"+{record.additions}", style=GREEN)
                    text.append(f" −{record.deletions}", style=RED)
                    text.append(f" in {record.changed_files} files", style=FAINT)
                if record.reviewers:
                    text.append("  ·  ", style=LINE)
                    text.append(f"awaiting {', '.join(record.reviewers[:3])}", style=YELLOW)
            else:
                if record.assignees:
                    text.append("  ·  ", style=LINE)
                    text.append(f"assigned {', '.join(record.assignees[:3])}", style=MUTED)
                if record.labels:
                    text.append("  ·  ", style=LINE)
                    text.append(", ".join(record.label_names[:5]), style=MUTED)
            return text

        if isinstance(record, StarEvent):
            text.append(f"@{record.user}", style=CREAM)
            text.append(" starred ", style=MUTED)
            text.append(record.repo, style=CORAL)
            text.append("  ·  ", style=LINE)
            text.append(stamp(record.starred_at), style=MUTED)
            text.append("  ·  ", style=LINE)
            text.append(f"{record.repo_stars} stars total", style=FAINT)
            return text

        if isinstance(record, ActivityEvent):
            text.append(record.repo, style=CORAL)
            text.append("  ·  ", style=LINE)
            text.append(f"@{record.actor} ", style=CREAM)
            text.append(record.summary, style=MUTED)
            text.append("  ·  ", style=LINE)
            text.append(stamp(record.created_at), style=FAINT)
            return text

        if isinstance(record, Notification):
            text.append(record.repo, style=CORAL)
            text.append("  ·  ", style=LINE)
            text.append(record.title, style=CREAM)
            text.append("  ·  ", style=LINE)
            text.append(f"{record.reason} · {stamp(record.updated_at)}", style=MUTED)
            return text

        return text


    def on_filter_bar_changed(self, message: FilterBar.Changed) -> None:
        message.stop()
        for panel in self.panels.values():
            if panel.bar is message.bar:
                panel.view.set_filter(message.value)
                return

    def on_record_table_counts_changed(self, message: RecordTable.CountsChanged) -> None:
        message.stop()
        self._sync_counts(message.control, message.shown, message.total)

    def on_stream_feed_counts_changed(self, message: StreamFeed.CountsChanged) -> None:
        message.stop()
        self._sync_counts(message.control, message.shown, message.total)

    def _sync_counts(self, view: Any, shown: int, total: int) -> None:
        for panel in self.panels.values():
            if panel.view is view:
                panel.bar.set_counts(shown, total)
                return

    def on_record_table_record_highlighted(
        self, message: RecordTable.RecordHighlighted
    ) -> None:
        message.stop()
        self._highlight_from(message.control, message.record)

    def on_stream_feed_record_highlighted(
        self, message: StreamFeed.RecordHighlighted
    ) -> None:
        message.stop()
        self._highlight_from(message.control, message.record)

    def _highlight_from(self, view: Any, record: Any) -> None:
        panel = self.active_panel
        if panel is None or panel.view is not view:
            return
        self._highlight = record
        self.set_status()

    def on_record_table_record_selected(self, message: RecordTable.RecordSelected) -> None:
        message.stop()
        self.inspect(message.record)

    def on_stream_feed_record_selected(self, message: StreamFeed.RecordSelected) -> None:
        message.stop()
        self.inspect(message.record)

    def on_tabbed_content_tab_activated(self, message: TabbedContent.TabActivated) -> None:
        if self.active_tab == "about":
            self._highlight = None
            try:
                self.query_one("#about-panel", AboutPanel).focus()
            except Exception:
                pass
            self.set_status()
            return

        panel = self.active_panel
        if panel is not None and self.panels:
            self._highlight = getattr(panel.view, "highlighted_record", None)
            panel.view.focus()
        self.set_status()


    def inspect(self, record: Any) -> None:
        from .issue_detail import IssueDetailScreen

        if isinstance(record, (Issue, PullRequest)):
            self.app.push_screen(IssueDetailScreen(record))
        else:
            self.action_open_browser()

    def _record_url(self, record: Any) -> str:
        if isinstance(record, (Issue, PullRequest, Notification, ActivityEvent)):
            return getattr(record, "html_url", "") or getattr(record, "url", "")
        if isinstance(record, StarEvent):
            return f"https://github.com/{record.repo}"
        return ""

    def action_open_browser(self) -> None:
        url = self._record_url(self._highlight)
        if not url:
            self.app.notify("Nothing selected to open.", severity="warning")
            return
        try:
            webbrowser.open(url)
            self.app.notify(f"Opened {truncate(url, 60)}")
        except Exception as error:
            self.app.notify(f"Could not open a browser: {error}", severity="error")

    def action_copy_url(self) -> None:
        url = self._record_url(self._highlight)
        if not url:
            self.app.notify("Nothing selected to copy.", severity="warning")
            return
        self.app.copy_to_clipboard(url)
        self.app.notify("URL copied to the clipboard.")

    def action_focus_filter(self) -> None:
        panel = self.active_panel
        if panel is not None:
            panel.bar.focus_input()

    def action_cycle_sort(self) -> None:
        panel = self.active_panel
        if panel is None or not hasattr(panel.view, "cycle_sort"):
            return
        label = panel.view.cycle_sort(1)
        if label:
            self.app.notify(f"Sorted by {label}.", timeout=2)
        self.set_status()

    def action_reverse_sort(self) -> None:
        panel = self.active_panel
        if panel is not None and hasattr(panel.view, "toggle_direction"):
            panel.view.toggle_direction()

    def action_goto_tab(self, name: str) -> None:
        if name in TABS:
            self.query_one("#tabs", TabbedContent).active = f"tab-{name}"

    def action_next_tab(self) -> None:
        index = (TABS.index(self.active_tab) + 1) % len(TABS)
        self.action_goto_tab(TABS[index])

    def action_prev_tab(self) -> None:
        index = (TABS.index(self.active_tab) - 1) % len(TABS)
        self.action_goto_tab(TABS[index])

    def action_sync(self) -> None:
        self.app.start_sync(force=True)

    def action_hard_sync(self) -> None:
        removed = self.app.cache.clear()
        self.app.notify(f"Cache cleared ({removed} entries) — resyncing.", severity="warning")
        self.app.start_sync(force=True)

    def action_scan_code(self) -> None:
        self.action_goto_tab("code")
        self.query_one("#code-summary", CodeSummary).set_scanning(True)
        self.app.start_code_scan()

    def action_export(self) -> None:
        from .export_screen import ExportScreen

        if self.active_panel is None:
            self.app.notify("There is nothing to export on this tab.", severity="warning")
            return
        self.app.push_screen(ExportScreen(self.active_tab))

    def action_help(self) -> None:
        from .help_screen import HelpScreen

        self.app.push_screen(HelpScreen())

    def action_menu(self) -> None:
        self.app.pop_screen()


    def on_key(self, event: events.Key) -> None:
        if event.key != "escape":
            return
        panel = self.active_panel
        if panel is None:
            return

        if panel.bar.value:
            panel.bar.clear()
            panel.view.set_filter("")
            panel.view.focus()
        elif panel.bar.input.has_focus:
            panel.view.focus()
        else:
            self.app.pop_screen()
        event.stop()
        event.prevent_default()
