# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

import webbrowser

from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.rule import Rule
from rich.text import Text
from textual import events, work
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from ...models.data_types import Comment, Issue, PullRequest
from ...utils.formatters import (
    check_badge,
    keyhint,
    label_chips,
    merge_badge,
    stamp,
    time_ago,
    truncate,
)
from ..theme import CORAL, CREAM, FAINT, GREEN, LINE, MARK, MUTED, PURPLE, RED


class IssueDetailScreen(ModalScreen):

    def __init__(self, record: Issue | PullRequest, **kwargs) -> None:
        super().__init__(**kwargs)
        self.record = record
        self.comments: list[Comment] = []
        self.detail: Issue | None = None
        self.fetching = True

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-card"):
            with VerticalScroll(id="modal-body"):
                yield Static(id="detail-body", markup=False)
            yield Static(id="modal-hint")

    def on_mount(self) -> None:
        card = self.query_one("#modal-card")
        kind = "pull request" if isinstance(self.record, PullRequest) else "issue"
        card.border_title = f"[{CORAL}]{MARK}[/] {self.record.slug}"
        card.border_subtitle = kind

        self.query_one("#modal-hint", Static).update(
            keyhint(
                [
                    ("↑↓", "scroll"),
                    ("o", "open in browser"),
                    ("y", "copy url"),
                    ("esc", "close"),
                ]
            )
        )
        self.render_body()
        self.query_one("#modal-body", VerticalScroll).focus()
        self.load_detail()


    @work(exclusive=True, group="detail")
    async def load_detail(self) -> None:
        client = getattr(self.app, "client", None)
        if client is None:
            self.fetching = False
            self.render_body()
            return

        try:
            detail, comments = await client.fetch_issue_detail(
                self.record.repo, self.record.number
            )
        except Exception as error:
            self.fetching = False
            self.render_body(error=str(error))
            return

        self.detail = detail
        self.comments = comments
        self.fetching = False
        self.render_body()


    def render_body(self, error: str = "") -> None:
        blocks: list[RenderableType] = [self._headline(), Text(""), self._meta(), Text("")]

        body = (self.detail.body if self.detail else "") or getattr(self.record, "body", "")
        if body.strip():
            blocks.append(Markdown(body, code_theme="ansi_dark", hyperlinks=False))
        elif self.fetching:
            blocks.append(Text("  loading conversation…", style=FAINT))
        else:
            blocks.append(Text("  no description was given", style=FAINT))

        if error:
            blocks += [Text(""), Text(f"  could not load details — {error}", style=RED)]

        if self.comments:
            blocks += [Text(""), Rule(style=LINE)]
            for comment in self.comments:
                blocks += [self._comment_header(comment), Text("")]
                blocks.append(
                    Markdown(comment.body or "_(empty)_", code_theme="ansi_dark", hyperlinks=False)
                )
                blocks.append(Text(""))
        elif not self.fetching:
            blocks += [Text(""), Text("  no comments yet", style=FAINT)]

        blocks += [Text(""), self._footer()]
        self.query_one("#detail-body", Static).update(Group(*blocks))

    def _headline(self) -> Text:
        text = Text()
        record = self.record
        if isinstance(record, PullRequest) and record.draft:
            text.append("◌ draft  ", style=FAINT)
        else:
            text.append("● open  ", style=GREEN)
        text.append(record.title or "(no title)", style=f"bold {CREAM}")
        return text

    def _meta(self) -> Group:
        record = self.record
        lines: list[RenderableType] = []

        line = Text()
        line.append(record.repo, style=CORAL)
        line.append(f"  #{record.number}", style=FAINT)
        line.append("   opened by ", style=MUTED)
        line.append(record.author, style=CREAM)
        line.append(f"  {time_ago(record.created_at)} ago", style=MUTED)
        line.append(f"  ({stamp(record.created_at)})", style=FAINT)
        lines.append(line)

        if isinstance(record, PullRequest):
            pr_line = Text()
            pr_line.append("branch ", style=FAINT)
            pr_line.append(f"{record.head_ref or '?'} → {record.base_ref or '?'}", style=MUTED)
            if record.changed_files:
                pr_line.append("   ", style=LINE)
                pr_line.append(f"+{record.additions}", style=GREEN)
                pr_line.append(f" −{record.deletions}", style=RED)
                pr_line.append(f"  {record.changed_files} files", style=FAINT)
            pr_line.append("   ", style=LINE)
            pr_line.append_text(merge_badge(record.merge_verdict))
            pr_line.append("   ", style=LINE)
            pr_line.append_text(check_badge(record.checks))
            lines.append(pr_line)

            if record.reviewers:
                reviewers = Text()
                reviewers.append("reviewers ", style=FAINT)
                reviewers.append(", ".join(record.reviewers), style=PURPLE)
                lines.append(reviewers)

        source = self.detail or record
        if getattr(source, "labels", None):
            lines.append(label_chips(source.labels))

        assignees = getattr(source, "assignees", None)
        if assignees:
            row = Text()
            row.append("assigned ", style=FAINT)
            row.append(", ".join(assignees), style=MUTED)
            lines.append(row)

        return Group(*lines)

    def _comment_header(self, comment: Comment) -> Text:
        text = Text()
        text.append("▌ ", style=CORAL)
        text.append(comment.author, style=f"bold {CREAM}")
        if comment.association and comment.association not in ("none", "user"):
            text.append(f"  {comment.association}", style=PURPLE)
        text.append(f"   {time_ago(comment.created_at)} ago", style=MUTED)
        return text

    def _footer(self) -> Text:
        text = Text()
        text.append(truncate(self.record.html_url, 100), style=FAINT)
        return text


    def on_key(self, event: events.Key) -> None:
        key = event.key
        letter = (event.character or "").lower()

        if key in ("escape", "backspace") or letter == "q":
            self.dismiss()
        elif letter == "o":
            if self.record.html_url:
                try:
                    webbrowser.open(self.record.html_url)
                    self.app.notify("Opened in your browser.")
                except Exception as error:
                    self.app.notify(f"Could not open a browser: {error}", severity="error")
        elif letter == "y":
            self.app.copy_to_clipboard(self.record.html_url)
            self.app.notify("URL copied to the clipboard.")
        elif letter == "r":
            self.fetching = True
            self.render_body()
            self.load_detail()
        else:
            return

        event.stop()
        event.prevent_default()
