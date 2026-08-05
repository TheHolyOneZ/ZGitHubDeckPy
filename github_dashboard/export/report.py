# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence

from ..models.data_types import (
    ActivityEvent,
    CodeStats,
    Issue,
    Notification,
    PullRequest,
    RepoCode,
    StarEvent,
)
from ..utils.formatters import compact_number, stamp, time_ago


@dataclass(slots=True)
class Cell:

    text: str = ""
    href: str = ""
    kind: str = "text"
    chips: list[tuple[str, str]] = field(default_factory=list)

    @property
    def plain(self) -> str:
        if self.chips:
            return ", ".join(name for name, _ in self.chips)
        return self.text


@dataclass(slots=True)
class Column:
    key: str
    label: str
    align: str = "left"


@dataclass(slots=True)
class Section:
    title: str
    columns: list[Column] = field(default_factory=list)
    rows: list[list[Cell]] = field(default_factory=list)
    subtitle: str = ""
    note: str = ""

    @property
    def empty(self) -> bool:
        return not self.rows


@dataclass(slots=True)
class Report:
    title: str
    subtitle: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    owner: str = ""
    filter_text: str = ""
    stats: list[tuple[str, str]] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)

    @property
    def slug(self) -> str:
        keep = [c.lower() if c.isalnum() else "-" for c in self.title]
        slug = "".join(keep).strip("-")
        while "--" in slug:
            slug = slug.replace("--", "-")
        return slug or "export"

    @property
    def row_count(self) -> int:
        return sum(len(section.rows) for section in self.sections)


def _repo_cell(repo: str) -> Cell:
    return Cell(repo, href=f"https://github.com/{repo}", kind="mono")


def _number(value: int) -> Cell:
    return Cell(f"{value:,}" if value else "—", kind="number")


def _top_repos(names: Sequence[str], limit: int = 5) -> str:
    counts: dict[str, int] = {}
    for name in names:
        counts[name] = counts.get(name, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])[:limit]
    return " · ".join(f"{name} ({count})" for name, count in ranked) or "—"


def issues_report(issues: Sequence[Issue], owner: str, filter_text: str = "") -> Report:
    repos = [issue.repo for issue in issues]
    oldest = min(
        (i for i in issues if i.created_at), key=lambda i: i.created_at, default=None
    )
    unlabelled = sum(1 for i in issues if not i.labels)
    unanswered = sum(1 for i in issues if i.comments == 0)

    report = Report(
        title="Open issues",
        subtitle=f"across {len(set(repos))} repositories",
        owner=owner,
        filter_text=filter_text,
        stats=[
            ("Open issues", f"{len(issues):,}"),
            ("Repositories", f"{len(set(repos)):,}"),
            ("Nobody has replied", f"{unanswered:,}"),
            ("No labels", f"{unlabelled:,}"),
            ("Oldest", f"{time_ago(oldest.created_at)} — {oldest.slug}" if oldest else "—"),
            ("Busiest", _top_repos(repos, 3)),
        ],
    )

    section = Section(
        title="Issues",
        columns=[
            Column("repo", "Repository"),
            Column("number", "#", "right"),
            Column("title", "Title"),
            Column("author", "Author"),
            Column("age", "Opened", "right"),
            Column("comments", "Comments", "right"),
            Column("labels", "Labels"),
        ],
    )
    for issue in issues:
        section.rows.append([
            _repo_cell(issue.repo),
            Cell(f"#{issue.number}", href=issue.html_url, kind="number"),
            Cell(issue.title or "(no title)", href=issue.html_url),
            Cell(issue.author, href=f"https://github.com/{issue.author}", kind="mono"),
            Cell(time_ago(issue.created_at), kind="muted"),
            _number(issue.comments),
            Cell(chips=[(l.name, l.color) for l in issue.labels]),
        ])
    report.sections.append(section)
    return report


def pulls_report(pulls: Sequence[PullRequest], owner: str, filter_text: str = "") -> Report:
    repos = [pull.repo for pull in pulls]
    drafts = sum(1 for p in pulls if p.draft)
    failing = sum(1 for p in pulls if p.checks.state == "failure")
    conflicts = sum(1 for p in pulls if p.merge_verdict == "conflicts")
    awaiting = sum(1 for p in pulls if p.reviewers and not p.draft)

    report = Report(
        title="Open pull requests",
        subtitle=f"across {len(set(repos))} repositories",
        owner=owner,
        filter_text=filter_text,
        stats=[
            ("Open pull requests", f"{len(pulls):,}"),
            ("Repositories", f"{len(set(repos)):,}"),
            ("Waiting on review", f"{awaiting:,}"),
            ("Failing CI", f"{failing:,}"),
            ("Cannot merge", f"{conflicts:,}"),
            ("Drafts", f"{drafts:,}"),
        ],
    )

    section = Section(
        title="Pull requests",
        columns=[
            Column("repo", "Repository"),
            Column("number", "#", "right"),
            Column("title", "Title"),
            Column("author", "Author"),
            Column("review", "Review"),
            Column("checks", "Checks"),
            Column("merge", "Mergeable"),
            Column("age", "Opened", "right"),
        ],
    )
    for pull in pulls:
        section.rows.append([
            _repo_cell(pull.repo),
            Cell(f"#{pull.number}", href=pull.html_url, kind="number"),
            Cell(("[draft] " if pull.draft else "") + (pull.title or "(no title)"),
                 href=pull.html_url),
            Cell(pull.author, href=f"https://github.com/{pull.author}", kind="mono"),
            Cell(pull.review_state, kind="muted"),
            Cell(pull.checks.describe(), kind="muted"),
            Cell(pull.merge_verdict, kind="muted"),
            Cell(time_ago(pull.created_at), kind="muted"),
        ])
    report.sections.append(section)
    return report


def stars_report(stars: Sequence[StarEvent], owner: str, filter_text: str = "") -> Report:
    repos = [star.repo for star in stars]
    report = Report(
        title="Recent stargazers",
        subtitle=f"{len(stars):,} stars across {len(set(repos))} repositories",
        owner=owner,
        filter_text=filter_text,
        stats=[
            ("Stargazers listed", f"{len(stars):,}"),
            ("Repositories", f"{len(set(repos)):,}"),
            ("Most starred", _top_repos(repos, 3)),
            ("Newest", time_ago(stars[0].starred_at) if stars else "—"),
        ],
    )
    section = Section(
        title="Stargazers",
        columns=[
            Column("when", "When", "right"),
            Column("user", "Who"),
            Column("repo", "Repository"),
            Column("total", "Repo stars", "right"),
        ],
    )
    for star in stars:
        section.rows.append([
            Cell(stamp(star.starred_at), kind="muted"),
            Cell(star.user, href=f"https://github.com/{star.user}", kind="mono"),
            _repo_cell(star.repo),
            _number(star.repo_stars),
        ])
    report.sections.append(section)
    return report


def activity_report(
    events: Sequence[ActivityEvent],
    notifications: Sequence[Notification],
    owner: str,
    filter_text: str = "",
) -> Report:
    kinds: dict[str, int] = {}
    for event in events:
        kinds[event.kind] = kinds.get(event.kind, 0) + 1
    busiest = " · ".join(
        f"{k} ({v})" for k, v in sorted(kinds.items(), key=lambda kv: -kv[1])[:4]
    )
    unread = sum(1 for n in notifications if n.unread)

    report = Report(
        title="Activity",
        subtitle=f"{len(events):,} events, {len(notifications):,} notifications",
        owner=owner,
        filter_text=filter_text,
        stats=[
            ("Events", f"{len(events):,}"),
            ("Notifications", f"{len(notifications):,}"),
            ("Unread", f"{unread:,}"),
            ("Repositories", f"{len({e.repo for e in events}):,}"),
            ("Most common", busiest or "—"),
        ],
    )

    if notifications:
        section = Section(
            title="Notifications",
            columns=[
                Column("when", "When", "right"),
                Column("state", "State"),
                Column("reason", "Reason"),
                Column("repo", "Repository"),
                Column("subject", "Subject"),
            ],
        )
        for item in notifications:
            section.rows.append([
                Cell(stamp(item.updated_at), kind="muted"),
                Cell("unread" if item.unread else "read", kind="muted"),
                Cell(item.reason, kind="muted"),
                _repo_cell(item.repo),
                Cell(item.title, href=item.url),
            ])
        report.sections.append(section)

    section = Section(
        title="Events",
        columns=[
            Column("when", "When", "right"),
            Column("type", "Type"),
            Column("actor", "Who"),
            Column("repo", "Repository"),
            Column("what", "What happened"),
        ],
    )
    for event in events:
        section.rows.append([
            Cell(stamp(event.created_at), kind="muted"),
            Cell(event.kind, kind="muted"),
            Cell(event.actor, href=f"https://github.com/{event.actor}", kind="mono"),
            _repo_cell(event.repo),
            Cell(event.summary, href=event.url),
        ])
    report.sections.append(section)
    return report


def code_report(
    entries: Sequence[RepoCode], stats: CodeStats, owner: str, filter_text: str = ""
) -> Report:
    languages = stats.languages()
    total_bytes = sum(size for _, size in languages) or 1
    spread = " · ".join(
        f"{name} {size / total_bytes * 100:.0f}%" for name, size in languages[:5]
    )

    report = Report(
        title="Code written",
        subtitle=f"{stats.additions:,} lines across {len(entries)} repositories",
        owner=owner,
        filter_text=filter_text,
        stats=[
            ("Lines ever written", f"{stats.additions:,}"),
            ("Lines removed", f"{stats.deletions:,}"),
            ("Net lines", f"{stats.net:,}"),
            ("Commits", f"{stats.commits:,}"),
            ("Repositories contributed to", f"{stats.repos_touched:,}"),
            ("Standing today (estimated)", f"{compact_number(stats.standing_lines)} lines"),
            ("Languages", spread or "—"),
        ],
    )

    if languages:
        section = Section(
            title="Languages",
            subtitle="By volume of code currently in your repositories.",
            columns=[
                Column("language", "Language"),
                Column("share", "Share", "right"),
                Column("size", "Size", "right"),
            ],
        )
        for name, size in languages:
            section.rows.append([
                Cell(name),
                Cell(f"{size / total_bytes * 100:.1f}%", kind="number"),
                Cell(f"{size / 1_048_576:.2f} MB", kind="number"),
            ])
        report.sections.append(section)

    section = Section(
        title="Repositories",
        note=(
            "`Lines now` is estimated from GitHub's language byte counts. "
            "`You added` and `You removed` are exact, from GitHub's contributor statistics."
        ),
        columns=[
            Column("repo", "Repository"),
            Column("language", "Language"),
            Column("lines", "Lines now", "right"),
            Column("additions", "You added", "right"),
            Column("deletions", "You removed", "right"),
            Column("net", "Net", "right"),
            Column("commits", "Commits", "right"),
        ],
    )
    for entry in entries:
        section.rows.append([
            _repo_cell(entry.repo),
            Cell(entry.primary_language or "—", kind="muted"),
            _number(entry.estimated_lines),
            _number(entry.additions),
            _number(entry.deletions),
            Cell(f"{entry.net:+,}" if entry.net else "—", kind="number"),
            _number(entry.commits),
        ])
    report.sections.append(section)
    return report
