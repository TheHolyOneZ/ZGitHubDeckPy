# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable, Iterable, Sequence

from ..models.data_types import (
    ActivityEvent,
    Issue,
    Notification,
    PullRequest,
    RepoCode,
    StarEvent,
)
from .formatters import now

Accessor = Callable[[Any], Any]
FieldMap = dict[str, Accessor]


@dataclass(frozen=True)
class Term:
    key: str
    value: str
    negated: bool = False


@dataclass
class Query:

    terms: list[Term] = field(default_factory=list)
    words: list[str] = field(default_factory=list)
    raw: str = ""

    @property
    def empty(self) -> bool:
        return not self.terms and not self.words


    @classmethod
    def parse(cls, text: str) -> Query:
        text = (text or "").strip()
        if not text:
            return cls(raw="")

        try:
            tokens = shlex.split(text)
        except ValueError:
            tokens = text.split()

        terms: list[Term] = []
        words: list[str] = []

        for token in tokens:
            negated = token.startswith("-") and len(token) > 1
            if negated:
                token = token[1:]
            key, separator, value = token.partition(":")
            if separator and value:
                terms.append(Term(key.lower(), value.lower(), negated))
            elif token:
                words.append(token.lower())

        return cls(terms=terms, words=words, raw=text)


    def matches(self, item: Any, fields: FieldMap, searchable: Sequence[str]) -> bool:
        for term in self.terms:
            accessor = fields.get(term.key)
            if accessor is None:
                hit = _contains(_gather(item, fields, searchable), f"{term.key}:{term.value}")
            else:
                hit = _match_value(accessor(item), term.value)
            if hit == term.negated:
                return False

        if self.words:
            haystack = _gather(item, fields, searchable)
            for word in self.words:
                if word not in haystack:
                    return False

        return True

    def apply(self, items: Iterable[Any], fields: FieldMap, searchable: Sequence[str]) -> list[Any]:
        if self.empty:
            return list(items)
        return [item for item in items if self.matches(item, fields, searchable)]

    def describe(self) -> str:
        if self.empty:
            return ""
        bits = [f"{'-' if t.negated else ''}{t.key}:{t.value}" for t in self.terms]
        bits.extend(self.words)
        return " ".join(bits)


def _match_value(value: Any, needle: str) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set)):
        return any(needle in str(item).lower() for item in value)
    if isinstance(value, bool):
        return needle in ("true", "yes", "1") if value else needle in ("false", "no", "0")
    return needle in str(value).lower()


def _contains(haystack: str, needle: str) -> bool:
    return needle.lower() in haystack


def _gather(item: Any, fields: FieldMap, searchable: Sequence[str]) -> str:
    parts: list[str] = []
    for name in searchable:
        accessor = fields.get(name)
        if accessor is None:
            continue
        value = accessor(item)
        if isinstance(value, (list, tuple, set)):
            parts.extend(str(entry) for entry in value)
        elif value is not None:
            parts.append(str(value))
    return " ".join(parts).lower()


STALE_AFTER = timedelta(days=30)


def _issue_flags(issue: Issue) -> list[str]:
    flags = [issue.state]
    if issue.assignees:
        flags.append("assigned")
    else:
        flags.append("unassigned")
    if not issue.labels:
        flags.append("unlabeled")
    if issue.comments == 0:
        flags.append("unanswered")
    if issue.updated_at and now() - issue.updated_at > STALE_AFTER:
        flags.append("stale")
    return flags


ISSUE_FIELDS: FieldMap = {
    "repo": lambda i: i.repo,
    "owner": lambda i: i.repo.split("/")[0],
    "author": lambda i: i.author,
    "title": lambda i: i.title,
    "label": lambda i: i.label_names,
    "assignee": lambda i: i.assignees,
    "state": lambda i: i.state,
    "number": lambda i: str(i.number),
    "comments": lambda i: str(i.comments),
    "is": _issue_flags,
}
ISSUE_SEARCHABLE = ("title", "repo", "author", "label")


def _pr_flags(pull: PullRequest) -> list[str]:
    flags = [pull.state, pull.merge_verdict]
    flags.append("draft" if pull.draft else "ready")
    if pull.reviewers:
        flags.append("review-requested")
    if pull.checks.state == "failure":
        flags.append("failing")
    elif pull.checks.state == "success":
        flags.append("passing")
    elif pull.checks.state == "pending":
        flags.append("running")
    if pull.updated_at and now() - pull.updated_at > STALE_AFTER:
        flags.append("stale")
    return flags


PR_FIELDS: FieldMap = {
    "repo": lambda p: p.repo,
    "owner": lambda p: p.repo.split("/")[0],
    "author": lambda p: p.author,
    "title": lambda p: p.title,
    "label": lambda p: p.label_names,
    "reviewer": lambda p: p.reviewers,
    "assignee": lambda p: p.assignees,
    "branch": lambda p: p.head_ref,
    "base": lambda p: p.base_ref,
    "state": lambda p: p.state,
    "number": lambda p: str(p.number),
    "checks": lambda p: p.checks.state,
    "merge": lambda p: p.merge_verdict,
    "is": _pr_flags,
}
PR_SEARCHABLE = ("title", "repo", "author", "label")


STAR_FIELDS: FieldMap = {
    "repo": lambda s: s.repo,
    "owner": lambda s: s.repo.split("/")[0],
    "user": lambda s: s.user,
    "author": lambda s: s.user,
}
STAR_SEARCHABLE = ("repo", "user")


EVENT_FIELDS: FieldMap = {
    "repo": lambda e: e.repo,
    "owner": lambda e: e.repo.split("/")[0],
    "actor": lambda e: e.actor,
    "author": lambda e: e.actor,
    "type": lambda e: e.kind,
    "is": lambda e: [e.kind],
}
EVENT_SEARCHABLE = ("repo", "actor", "type", "summary")
EVENT_FIELDS["summary"] = lambda e: e.summary


def _code_flags(item) -> list[str]:
    flags = []
    flags.append("archived" if item.archived else "active")
    flags.append("private" if item.private else "public")
    if item.touched:
        flags.append("mine")
    if not item.stats_ready:
        flags.append("pending")
    if not item.languages:
        flags.append("empty")
    return flags


CODE_FIELDS: FieldMap = {
    "repo": lambda c: c.repo,
    "owner": lambda c: c.repo.split("/")[0],
    "language": lambda c: list(c.languages.keys()),
    "lang": lambda c: list(c.languages.keys()),
    "is": _code_flags,
}
CODE_SEARCHABLE = ("repo", "language")


NOTIFICATION_FIELDS: FieldMap = {
    "repo": lambda n: n.repo,
    "owner": lambda n: n.repo.split("/")[0],
    "reason": lambda n: n.reason,
    "title": lambda n: n.title,
    "type": lambda n: n.subject_type,
    "is": lambda n: ["unread" if n.unread else "read", n.subject_type.lower()],
}
NOTIFICATION_SEARCHABLE = ("title", "repo", "reason")


def filter_issues(items: Sequence[Issue], text: str) -> list[Issue]:
    return Query.parse(text).apply(items, ISSUE_FIELDS, ISSUE_SEARCHABLE)


def filter_pulls(items: Sequence[PullRequest], text: str) -> list[PullRequest]:
    return Query.parse(text).apply(items, PR_FIELDS, PR_SEARCHABLE)


def filter_stars(items: Sequence[StarEvent], text: str) -> list[StarEvent]:
    return Query.parse(text).apply(items, STAR_FIELDS, STAR_SEARCHABLE)


def filter_events(items: Sequence[ActivityEvent], text: str) -> list[ActivityEvent]:
    return Query.parse(text).apply(items, EVENT_FIELDS, EVENT_SEARCHABLE)


def filter_notifications(items: Sequence[Notification], text: str) -> list[Notification]:
    return Query.parse(text).apply(items, NOTIFICATION_FIELDS, NOTIFICATION_SEARCHABLE)


def filter_code(items: Sequence[RepoCode], text: str) -> list[RepoCode]:
    return Query.parse(text).apply(items, CODE_FIELDS, CODE_SEARCHABLE)
