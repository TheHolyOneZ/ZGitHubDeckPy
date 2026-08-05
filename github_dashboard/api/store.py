# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Sequence

from ..models.data_types import (
    ActivityEvent,
    CodeStats,
    Issue,
    Notification,
    PullRequest,
    RateLimit,
    Repo,
    RepoCode,
    StarEvent,
    User,
    decode,
    decode_all,
    encode,
    parse_time,
)
from .cache_manager import CacheManager
from .github_client import GitHubClient, GitHubError, RateLimitError

SNAPSHOT_KEY = "zdeck:snapshot:v1"

STAGES: tuple[tuple[str, str], ...] = (
    ("viewer", "account"),
    ("repos", "repositories"),
    ("issue", "issues"),
    ("pr", "pull requests"),
    ("stars", "stargazers"),
    ("activity", "activity"),
    ("code", "code volume"),
)

ProgressHook = Callable[["SyncState"], None]


@dataclass
class SyncState:

    running: bool = False
    stage: str = ""
    detail: str = ""
    step: int = 0
    total: int = len(STAGES) - 1
    started_at: float | None = None
    finished_at: float | None = None
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    truncated: bool = False

    @property
    def fraction(self) -> float:
        if not self.total:
            return 0.0
        return max(0.0, min(1.0, self.step / self.total))

    @property
    def elapsed(self) -> float:
        if self.started_at is None:
            return 0.0
        return (self.finished_at or time.monotonic()) - self.started_at

    def label(self) -> str:
        for key, name in STAGES:
            if key == self.stage:
                return name
        return self.stage or "idle"


@dataclass
class DataStore:

    viewer: User | None = None
    repos: list[Repo] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    pulls: list[PullRequest] = field(default_factory=list)
    stars: list[StarEvent] = field(default_factory=list)
    events: list[ActivityEvent] = field(default_factory=list)
    notifications: list[Notification] = field(default_factory=list)
    code: CodeStats = field(default_factory=CodeStats)

    rate: RateLimit | None = None
    synced_at: datetime | None = None
    loaded_from_snapshot: bool = False
    sync_state: SyncState = field(default_factory=SyncState)


    @property
    def repo_count(self) -> int:
        return len(self.repos)

    @property
    def total_stars(self) -> int:
        return sum(repo.stars for repo in self.repos)

    @property
    def total_forks(self) -> int:
        return sum(repo.forks for repo in self.repos)

    @property
    def unread_count(self) -> int:
        return sum(1 for item in self.notifications if item.unread)

    @property
    def review_requests(self) -> int:
        return sum(1 for pull in self.pulls if pull.reviewers and not pull.draft)

    @property
    def failing_pulls(self) -> int:
        return sum(1 for pull in self.pulls if pull.checks.state == "failure")

    @property
    def has_data(self) -> bool:
        return bool(self.repos or self.issues or self.pulls)

    def repo_names(self) -> list[str]:
        return sorted({repo.full_name for repo in self.repos})

    def repo_by_name(self, full_name: str) -> Repo | None:
        for repo in self.repos:
            if repo.full_name == full_name:
                return repo
        return None

    def busiest_repos(self, limit: int = 5) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            counts[issue.repo] = counts.get(issue.repo, 0) + 1
        ranked = sorted(counts.items(), key=lambda item: -item[1])
        return ranked[:limit]


    def load_snapshot(self, cache: CacheManager) -> bool:
        entry = cache.get(SNAPSHOT_KEY)
        if entry is None or not isinstance(entry.value, dict):
            return False

        blob = entry.value
        try:
            self.viewer = decode(User, blob["viewer"]) if blob.get("viewer") else None
            self.repos = decode_all(Repo, blob.get("repos"))
            self.issues = decode_all(Issue, blob.get("issues"))
            self.pulls = decode_all(PullRequest, blob.get("pulls"))
            self.stars = decode_all(StarEvent, blob.get("stars"))
            self.events = decode_all(ActivityEvent, blob.get("events"))
            self.notifications = decode_all(Notification, blob.get("notifications"))
            code = blob.get("code") or {}
            self.code = CodeStats(
                repos=decode_all(RepoCode, code.get("repos")),
                scanned_at=parse_time(code.get("scanned_at")),
                incomplete=list(code.get("incomplete") or []),
            )
            self.rate = decode(RateLimit, blob["rate"]) if blob.get("rate") else None
        except Exception:
            return False

        stamp = blob.get("synced_at")
        if isinstance(stamp, (int, float)):
            self.synced_at = datetime.fromtimestamp(stamp, timezone.utc)
        self.loaded_from_snapshot = True
        return self.has_data

    def save_snapshot(self, cache: CacheManager) -> None:
        cache.put(
            SNAPSHOT_KEY,
            {
                "viewer": encode(self.viewer) if self.viewer else None,
                "repos": encode(self.repos),
                "issues": encode(self.issues),
                "pulls": encode(self.pulls),
                "stars": encode(self.stars),
                "events": encode(self.events),
                "notifications": encode(self.notifications),
                "code": encode(self.code),
                "rate": encode(self.rate) if self.rate else None,
                "synced_at": time.time(),
            },
        )

    async def scan_code(
        self,
        client: GitHubClient,
        progress: ProgressHook | None = None,
    ) -> CodeStats:
        state = SyncState(running=True, started_at=time.monotonic(), total=1)
        self.sync_state = state

        def publish(stage: str, detail: str) -> None:
            state.stage, state.detail = stage, detail
            if progress:
                progress(state)

        login = self.viewer.login if self.viewer else ""
        try:
            publish("code", f"scanning {len(self.repos)} repositories")
            self.code = await client.fetch_code_stats(self.repos, login, publish)
        except GitHubError as error:
            state.errors.append(f"code: {error}")
        finally:
            state.running = False
            state.finished_at = time.monotonic()
            state.step = state.total
            for note in client.notes:
                if note not in state.notes:
                    state.notes.append(note)
            if progress:
                progress(state)
        return self.code


    async def sync(
        self,
        client: GitHubClient,
        progress: ProgressHook | None = None,
        *,
        stages: Sequence[str] | None = None,
    ) -> SyncState:
        wanted = set(stages) if stages else {key for key, _ in STAGES}
        state = SyncState(running=True, started_at=time.monotonic(), total=len(wanted))
        self.sync_state = state

        def publish(stage: str, detail: str) -> None:
            state.stage = stage
            state.detail = detail
            if progress:
                progress(state)

        def advance(stage: str, detail: str) -> None:
            state.step = min(state.step + 1, state.total)
            publish(stage, detail)

        def fail(stage: str, error: Exception) -> None:
            message = f"{stage}: {error}"
            if message not in state.errors:
                state.errors.append(message)
            advance(stage, "failed")

        try:
            if "viewer" in wanted:
                publish("viewer", "identifying account")
                try:
                    self.viewer = await client.fetch_viewer()
                    advance("viewer", f"@{self.viewer.login}")
                except GitHubError as error:
                    fail("viewer", error)

            if "repos" in wanted:
                publish("repos", "listing repositories")
                try:
                    self.repos = await client.fetch_repos(publish)
                    advance("repos", f"{len(self.repos)} repositories")
                except GitHubError as error:
                    fail("repos", error)

            if "issue" in wanted and self.repos:
                try:
                    self.issues, truncated = await client.fetch_issues(self.repos, publish)
                    state.truncated = state.truncated or truncated
                    advance("issue", f"{len(self.issues)} open issues")
                except GitHubError as error:
                    fail("issue", error)

            if "pr" in wanted and self.repos:
                try:
                    self.pulls, truncated = await client.fetch_pulls(self.repos, publish)
                    state.truncated = state.truncated or truncated
                    if progress:
                        progress(state)
                    await client.enrich_pulls(self.pulls, publish)
                    advance("pr", f"{len(self.pulls)} open pull requests")
                except GitHubError as error:
                    fail("pr", error)

            if "stars" in wanted and self.repos:
                try:
                    self.stars = await client.fetch_stars(self.repos, publish)
                    advance("stars", f"{len(self.stars)} recent stars")
                except GitHubError as error:
                    fail("stars", error)

            if "activity" in wanted:
                login = self.viewer.login if self.viewer else ""
                try:
                    if login:
                        self.events = await client.fetch_events(login, publish)
                    self.notifications = await client.fetch_notifications(publish)
                    advance("activity", f"{len(self.events)} events")
                except GitHubError as error:
                    fail("activity", error)

            await client.fetch_rate_limit()
            self.rate = client.rate
            for note in client.notes:
                if note not in state.notes:
                    state.notes.append(note)

        except RateLimitError as error:
            state.errors.append(f"rate limit: {error}")
        except GitHubError as error:
            state.errors.append(str(error))
        finally:
            state.running = False
            state.finished_at = time.monotonic()
            state.step = state.total
            self.synced_at = datetime.now(timezone.utc)
            self.loaded_from_snapshot = False
            if progress:
                progress(state)

        return state
