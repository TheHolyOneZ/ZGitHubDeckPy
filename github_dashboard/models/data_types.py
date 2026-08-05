# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import fields as dc_fields
from dataclasses import is_dataclass
from datetime import datetime, timezone
from types import UnionType
from typing import Any, Iterable, Union, get_args, get_origin, get_type_hints

Json = dict[str, Any]


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def login_of(payload: Any) -> str:
    if isinstance(payload, dict):
        return str(payload.get("login") or "ghost")
    return "ghost"


_login = login_of


@dataclass(slots=True)
class User:
    login: str
    name: str = ""
    html_url: str = ""
    avatar_url: str = ""
    public_repos: int = 0
    followers: int = 0

    @classmethod
    def from_api(cls, payload: Json) -> User:
        return cls(
            login=str(payload.get("login") or "unknown"),
            name=str(payload.get("name") or ""),
            html_url=str(payload.get("html_url") or ""),
            avatar_url=str(payload.get("avatar_url") or ""),
            public_repos=int(payload.get("public_repos") or 0),
            followers=int(payload.get("followers") or 0),
        )

    @property
    def display(self) -> str:
        return self.name or self.login


@dataclass(slots=True, frozen=True)
class Label:
    name: str
    color: str = "666666"
    description: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> Label:
        if isinstance(payload, str):
            return cls(name=payload)
        return cls(
            name=str(payload.get("name") or "?"),
            color=str(payload.get("color") or "666666").lstrip("#") or "666666",
            description=str(payload.get("description") or ""),
        )


@dataclass(slots=True)
class Repo:
    full_name: str
    name: str
    owner: str
    owner_type: str = "User"
    private: bool = False
    fork: bool = False
    archived: bool = False
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    watchers: int = 0
    language: str = ""
    description: str = ""
    html_url: str = ""
    default_branch: str = "main"
    pushed_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_api(cls, payload: Json) -> Repo:
        owner = _login(payload.get("owner"))
        name = str(payload.get("name") or "?")
        return cls(
            full_name=str(payload.get("full_name") or f"{owner}/{name}"),
            name=name,
            owner=owner,
            owner_type=str((payload.get("owner") or {}).get("type") or "User"),
            private=bool(payload.get("private")),
            fork=bool(payload.get("fork")),
            archived=bool(payload.get("archived")),
            stars=int(payload.get("stargazers_count") or 0),
            forks=int(payload.get("forks_count") or 0),
            open_issues=int(payload.get("open_issues_count") or 0),
            watchers=int(payload.get("subscribers_count") or 0),
            language=str(payload.get("language") or ""),
            description=str(payload.get("description") or ""),
            html_url=str(payload.get("html_url") or ""),
            default_branch=str(payload.get("default_branch") or "main"),
            pushed_at=parse_time(payload.get("pushed_at")),
            updated_at=parse_time(payload.get("updated_at")),
        )


@dataclass(slots=True)
class Issue:

    id: int
    number: int
    repo: str
    title: str
    author: str
    state: str = "open"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    comments: int = 0
    labels: list[Label] = field(default_factory=list)
    assignees: list[str] = field(default_factory=list)
    body: str = ""
    html_url: str = ""
    locked: bool = False

    @classmethod
    def from_api(cls, payload: Json, repo: str | None = None) -> Issue:
        return cls(
            id=int(payload.get("id") or 0),
            number=int(payload.get("number") or 0),
            repo=repo or repo_from_url(payload),
            title=str(payload.get("title") or "").strip(),
            author=_login(payload.get("user")),
            state=str(payload.get("state") or "open"),
            created_at=parse_time(payload.get("created_at")),
            updated_at=parse_time(payload.get("updated_at")),
            comments=int(payload.get("comments") or 0),
            labels=[Label.from_api(item) for item in payload.get("labels") or []],
            assignees=[_login(item) for item in payload.get("assignees") or []],
            body=str(payload.get("body") or ""),
            html_url=str(payload.get("html_url") or ""),
            locked=bool(payload.get("locked")),
        )

    @property
    def slug(self) -> str:
        return f"{self.repo}#{self.number}"

    @property
    def label_names(self) -> list[str]:
        return [label.name for label in self.labels]


@dataclass(slots=True)
class CheckSummary:

    state: str = "unknown"
    total: int = 0
    passed: int = 0
    failed: int = 0

    @property
    def known(self) -> bool:
        return self.state != "unknown"

    def describe(self) -> str:
        if self.state == "unknown":
            return "—"
        if self.total == 0:
            return "no checks"
        if self.state == "failure":
            return f"{self.failed} failing"
        if self.state == "pending":
            return f"{self.total - self.passed - self.failed} running"
        if self.state == "success":
            return f"{self.passed} passed"
        return self.state


@dataclass(slots=True)
class PullRequest:
    id: int
    number: int
    repo: str
    title: str
    author: str
    state: str = "open"
    draft: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    comments: int = 0
    labels: list[Label] = field(default_factory=list)
    reviewers: list[str] = field(default_factory=list)
    assignees: list[str] = field(default_factory=list)
    html_url: str = ""
    body: str = ""
    head_sha: str = ""
    head_ref: str = ""
    base_ref: str = ""
    mergeable_state: str = ""
    mergeable: bool | None = None
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    checks: CheckSummary = field(default_factory=CheckSummary)
    enriched: bool = False

    @classmethod
    def from_api(cls, payload: Json, repo: str | None = None) -> PullRequest:
        pull = payload.get("pull_request") or {}
        head = payload.get("head") or {}
        base = payload.get("base") or {}
        return cls(
            id=int(payload.get("id") or 0),
            number=int(payload.get("number") or 0),
            repo=repo or repo_from_url(payload),
            title=str(payload.get("title") or "").strip(),
            author=_login(payload.get("user")),
            state=str(payload.get("state") or "open"),
            draft=bool(payload.get("draft") or pull.get("draft")),
            created_at=parse_time(payload.get("created_at")),
            updated_at=parse_time(payload.get("updated_at")),
            comments=int(payload.get("comments") or 0),
            labels=[Label.from_api(item) for item in payload.get("labels") or []],
            reviewers=[_login(item) for item in payload.get("requested_reviewers") or []],
            assignees=[_login(item) for item in payload.get("assignees") or []],
            html_url=str(payload.get("html_url") or ""),
            body=str(payload.get("body") or ""),
            head_sha=str(head.get("sha") or ""),
            head_ref=str(head.get("ref") or ""),
            base_ref=str(base.get("ref") or ""),
        )

    def merge_detail(self, payload: Json) -> None:
        head = payload.get("head") or {}
        base = payload.get("base") or {}
        self.head_sha = str(head.get("sha") or self.head_sha)
        self.head_ref = str(head.get("ref") or self.head_ref)
        self.base_ref = str(base.get("ref") or self.base_ref)
        self.mergeable_state = str(payload.get("mergeable_state") or "")
        mergeable = payload.get("mergeable")
        self.mergeable = mergeable if isinstance(mergeable, bool) else None
        self.additions = int(payload.get("additions") or 0)
        self.deletions = int(payload.get("deletions") or 0)
        self.changed_files = int(payload.get("changed_files") or 0)
        self.draft = bool(payload.get("draft", self.draft))
        reviewers = [_login(item) for item in payload.get("requested_reviewers") or []]
        teams = [
            str(item.get("name") or "team")
            for item in payload.get("requested_teams") or []
            if isinstance(item, dict)
        ]
        if reviewers or teams:
            self.reviewers = reviewers + [f"@{team}" for team in teams]
        self.enriched = True

    @property
    def slug(self) -> str:
        return f"{self.repo}#{self.number}"

    @property
    def review_state(self) -> str:
        if self.draft:
            return "draft"
        if self.reviewers:
            return f"{len(self.reviewers)} pending"
        return "none"

    @property
    def merge_verdict(self) -> str:
        if self.draft:
            return "draft"
        state = self.mergeable_state
        if state == "clean":
            return "ready"
        if state == "dirty":
            return "conflicts"
        if state == "behind":
            return "behind"
        if state == "blocked":
            return "blocked"
        if state == "unstable":
            return "unstable"
        if state == "has_hooks":
            return "ready"
        if self.mergeable is False:
            return "conflicts"
        return "—"


@dataclass(slots=True)
class StarEvent:
    repo: str
    user: str
    starred_at: datetime | None
    avatar_url: str = ""
    repo_stars: int = 0

    @classmethod
    def from_api(cls, payload: Json, repo: str, repo_stars: int = 0) -> StarEvent:
        user = payload.get("user") if isinstance(payload.get("user"), dict) else payload
        return cls(
            repo=repo,
            user=_login(user),
            starred_at=parse_time(payload.get("starred_at")),
            avatar_url=str((user or {}).get("avatar_url") or ""),
            repo_stars=repo_stars,
        )


@dataclass(slots=True)
class ActivityEvent:
    id: str
    type: str
    actor: str
    repo: str
    created_at: datetime | None
    summary: str = ""
    url: str = ""

    @classmethod
    def from_api(cls, payload: Json) -> ActivityEvent:
        repo = payload.get("repo") or {}
        return cls(
            id=str(payload.get("id") or ""),
            type=str(payload.get("type") or "Event"),
            actor=_login(payload.get("actor")),
            repo=str(repo.get("name") or "?"),
            created_at=parse_time(payload.get("created_at")),
            summary=summarize_event(payload),
            url=event_url(payload),
        )

    @property
    def kind(self) -> str:
        return EVENT_KINDS.get(self.type, self.type.replace("Event", "").lower())


@dataclass(slots=True)
class Notification:
    id: str
    repo: str
    title: str
    reason: str
    subject_type: str
    updated_at: datetime | None
    unread: bool = True
    url: str = ""

    @classmethod
    def from_api(cls, payload: Json) -> Notification:
        subject = payload.get("subject") or {}
        repo = payload.get("repository") or {}
        return cls(
            id=str(payload.get("id") or ""),
            repo=str(repo.get("full_name") or "?"),
            title=str(subject.get("title") or "").strip(),
            reason=str(payload.get("reason") or "").replace("_", " "),
            subject_type=str(subject.get("type") or ""),
            updated_at=parse_time(payload.get("updated_at")),
            unread=bool(payload.get("unread", True)),
            url=api_url_to_web(str(subject.get("url") or "")),
        )


@dataclass(slots=True)
class Comment:
    author: str
    body: str
    created_at: datetime | None
    association: str = ""

    @classmethod
    def from_api(cls, payload: Json) -> Comment:
        return cls(
            author=_login(payload.get("user")),
            body=str(payload.get("body") or ""),
            created_at=parse_time(payload.get("created_at")),
            association=str(payload.get("author_association") or "").replace("_", " ").lower(),
        )


BYTES_PER_LINE: dict[str, float] = {
    "Python": 33, "JavaScript": 36, "TypeScript": 38, "Java": 38, "C": 30,
    "C++": 32, "C#": 38, "Go": 30, "Rust": 34, "Ruby": 30, "PHP": 34,
    "Swift": 34, "Kotlin": 36, "Scala": 36, "Dart": 34, "Lua": 28,
    "Shell": 28, "PowerShell": 34, "Batchfile": 26, "Perl": 30, "R": 30,
    "HTML": 45, "CSS": 28, "SCSS": 28, "Vue": 36, "Svelte": 36,
    "JSON": 40, "YAML": 32, "TOML": 28, "XML": 45, "Markdown": 55,
    "Dockerfile": 30, "Makefile": 26, "SQL": 30, "Assembly": 24,
}
DEFAULT_BYTES_PER_LINE = 35.0


def estimate_lines(languages: dict[str, int]) -> int:
    total = 0.0
    for language, size in (languages or {}).items():
        total += size / BYTES_PER_LINE.get(language, DEFAULT_BYTES_PER_LINE)
    return int(round(total))


@dataclass(slots=True)
class RepoCode:

    repo: str
    languages: dict[str, int] = field(default_factory=dict)
    additions: int = 0
    deletions: int = 0
    commits: int = 0
    stats_ready: bool = True
    archived: bool = False
    private: bool = False

    @property
    def total_bytes(self) -> int:
        return sum(self.languages.values())

    @property
    def estimated_lines(self) -> int:
        return estimate_lines(self.languages)

    @property
    def net(self) -> int:
        return self.additions - self.deletions

    @property
    def primary_language(self) -> str:
        if not self.languages:
            return ""
        return max(self.languages.items(), key=lambda kv: kv[1])[0]

    @property
    def touched(self) -> bool:
        return bool(self.additions or self.deletions or self.commits)


@dataclass(slots=True)
class CodeStats:

    repos: list[RepoCode] = field(default_factory=list)
    scanned_at: datetime | None = None
    incomplete: list[str] = field(default_factory=list)

    @property
    def additions(self) -> int:
        return sum(item.additions for item in self.repos)

    @property
    def deletions(self) -> int:
        return sum(item.deletions for item in self.repos)

    @property
    def net(self) -> int:
        return self.additions - self.deletions

    @property
    def commits(self) -> int:
        return sum(item.commits for item in self.repos)

    @property
    def standing_lines(self) -> int:
        return sum(item.estimated_lines for item in self.repos)

    @property
    def total_bytes(self) -> int:
        return sum(item.total_bytes for item in self.repos)

    @property
    def repos_touched(self) -> int:
        return sum(1 for item in self.repos if item.touched)

    def languages(self) -> list[tuple[str, int]]:
        totals: dict[str, int] = {}
        for item in self.repos:
            for language, size in item.languages.items():
                totals[language] = totals.get(language, 0) + size
        return sorted(totals.items(), key=lambda kv: -kv[1])

    def biggest(self, limit: int = 5) -> list[RepoCode]:
        return sorted(self.repos, key=lambda item: -item.additions)[:limit]


@dataclass(slots=True)
class RateLimit:

    limit: int = 0
    remaining: int = 0
    used: int = 0
    reset_at: datetime | None = None
    resource: str = "core"

    @classmethod
    def from_headers(cls, headers: Any, resource: str = "core") -> RateLimit | None:
        try:
            limit = int(headers.get("x-ratelimit-limit", ""))
            remaining = int(headers.get("x-ratelimit-remaining", ""))
        except (TypeError, ValueError):
            return None
        try:
            reset = datetime.fromtimestamp(int(headers.get("x-ratelimit-reset", 0)), timezone.utc)
        except (TypeError, ValueError, OSError):
            reset = None
        return cls(
            limit=limit,
            remaining=remaining,
            used=max(limit - remaining, 0),
            reset_at=reset,
            resource=str(headers.get("x-ratelimit-resource") or resource),
        )

    @property
    def fraction(self) -> float:
        if self.limit <= 0:
            return 1.0
        return max(0.0, min(1.0, self.remaining / self.limit))

    @property
    def healthy(self) -> bool:
        return self.fraction > 0.25


EVENT_KINDS = {
    "PushEvent": "push",
    "ForkEvent": "fork",
    "WatchEvent": "star",
    "IssuesEvent": "issue",
    "IssueCommentEvent": "comment",
    "PullRequestEvent": "pr",
    "PullRequestReviewEvent": "review",
    "PullRequestReviewCommentEvent": "review",
    "CreateEvent": "create",
    "DeleteEvent": "delete",
    "ReleaseEvent": "release",
    "PublicEvent": "public",
    "MemberEvent": "member",
    "GollumEvent": "wiki",
    "CommitCommentEvent": "comment",
}


def repo_from_url(payload: Json) -> str:
    for key in ("repository_url", "html_url", "url"):
        url = payload.get(key)
        if not isinstance(url, str) or not url:
            continue
        if key == "repository_url":
            parts = url.rstrip("/").split("/")
            if len(parts) >= 2:
                return f"{parts[-2]}/{parts[-1]}"
        else:
            parts = url.split("/")
            if "repos" in parts:
                index = parts.index("repos")
                if len(parts) > index + 2:
                    return f"{parts[index + 1]}/{parts[index + 2]}"
            elif "github.com" in url and len(parts) >= 5:
                return f"{parts[3]}/{parts[4]}"
    repository = payload.get("repository")
    if isinstance(repository, dict) and repository.get("full_name"):
        return str(repository["full_name"])
    return "?/?"


def api_url_to_web(url: str) -> str:
    if not url:
        return ""
    return (
        url.replace("https://api.github.com/repos/", "https://github.com/")
        .replace("/pulls/", "/pull/")
    )


def summarize_event(payload: Json) -> str:
    kind = str(payload.get("type") or "")
    detail = payload.get("payload") or {}

    if kind == "PushEvent":
        commits = detail.get("commits") or []
        ref = str(detail.get("ref") or "").rsplit("/", 1)[-1]
        count = int(detail.get("size") or len(commits))
        head = ""
        if commits:
            message = str(commits[-1].get("message") or "").splitlines()
            head = message[0] if message else ""
        if count == 0:
            return f"pushed to {ref}" if ref else "pushed"
        noun = "commit" if count == 1 else "commits"
        return f"pushed {count} {noun} to {ref}" + (f" — {head}" if head else "")

    if kind == "ForkEvent":
        forkee = detail.get("forkee") or {}
        return f"forked to {forkee.get('full_name', '?')}"

    if kind == "WatchEvent":
        return "starred the repository"

    if kind in ("IssuesEvent", "PullRequestEvent"):
        action = str(detail.get("action") or "updated")
        item = detail.get("issue") or detail.get("pull_request") or {}
        number = item.get("number", "?")
        title = str(item.get("title") or "")
        return f"{action} #{number} — {title}"

    if kind in ("IssueCommentEvent", "PullRequestReviewCommentEvent", "CommitCommentEvent"):
        item = detail.get("issue") or detail.get("pull_request") or {}
        number = item.get("number")
        target = f" on #{number}" if number else ""
        body = str((detail.get("comment") or {}).get("body") or "").splitlines()
        return f"commented{target}" + (f" — {body[0]}" if body else "")

    if kind == "PullRequestReviewEvent":
        review = detail.get("review") or {}
        item = detail.get("pull_request") or {}
        state = str(review.get("state") or "reviewed").lower().replace("_", " ")
        return f"{state} #{item.get('number', '?')}"

    if kind in ("CreateEvent", "DeleteEvent"):
        verb = "created" if kind == "CreateEvent" else "deleted"
        ref_type = str(detail.get("ref_type") or "ref")
        ref = str(detail.get("ref") or "")
        return f"{verb} {ref_type} {ref}".strip()

    if kind == "ReleaseEvent":
        release = detail.get("release") or {}
        return f"released {release.get('tag_name', '?')}"

    if kind == "PublicEvent":
        return "made the repository public"

    if kind == "MemberEvent":
        member = detail.get("member") or {}
        return f"{detail.get('action', 'changed')} collaborator {member.get('login', '?')}"

    return kind.replace("Event", "").lower() or "activity"


def event_url(payload: Json) -> str:
    detail = payload.get("payload") or {}
    for item in (detail.get("issue"), detail.get("pull_request"), detail.get("comment")):
        if isinstance(item, dict) and item.get("html_url"):
            return str(item["html_url"])
    release = detail.get("release")
    if isinstance(release, dict) and release.get("html_url"):
        return str(release["html_url"])
    repo = payload.get("repo") or {}
    name = repo.get("name")
    return f"https://github.com/{name}" if name else ""


def encode(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: encode(getattr(value, f.name)) for f in dc_fields(value)}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]
    if isinstance(value, dict):
        return {str(k): encode(v) for k, v in value.items()}
    return value


def _decode_value(annotation: Any, raw: Any) -> Any:
    origin = get_origin(annotation)

    if origin in (Union, UnionType):
        options = [arg for arg in get_args(annotation) if arg is not type(None)]
        if raw is None or not options:
            return None
        return _decode_value(options[0], raw)

    if origin in (list, tuple):
        args = get_args(annotation)
        inner = args[0] if args else Any
        return [_decode_value(inner, item) for item in raw or []]

    if annotation is datetime:
        return parse_time(raw)

    if is_dataclass(annotation) and isinstance(annotation, type):
        return decode(annotation, raw or {})

    return raw


def decode(model: type, data: Json) -> Any:
    try:
        hints = get_type_hints(model)
    except (NameError, TypeError):
        hints = {}

    kwargs: Json = {}
    for f in dc_fields(model):
        if f.name not in data:
            continue
        kwargs[f.name] = _decode_value(hints.get(f.name, Any), data[f.name])

    try:
        return model(**kwargs)
    except TypeError:
        return None


def decode_all(model: type, rows: Any) -> list[Any]:
    if not isinstance(rows, list):
        return []
    built = (decode(model, row) for row in rows if isinstance(row, dict))
    return [item for item in built if item is not None]


def dedupe(items: Iterable[Any], key: Any) -> list[Any]:
    seen: set = set()
    out: list[Any] = []
    for item in items:
        marker = key(item)
        if marker in seen:
            continue
        seen.add(marker)
        out.append(item)
    return out
