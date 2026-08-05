# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Iterable, Sequence

import httpx

from ..config.settings import (
    ACCEPT_JSON,
    ACCEPT_STAR,
    API_ROOT,
    API_VERSION,
    BACKOFF_BASE,
    ENDPOINTS,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    SEARCH_RATE_LIMIT,
    Settings,
    USER_AGENT,
)
from ..models.data_types import (
    ActivityEvent,
    CheckSummary,
    CodeStats,
    Comment,
    Issue,
    Notification,
    PullRequest,
    RateLimit,
    Repo,
    RepoCode,
    StarEvent,
    User,
    dedupe,
    login_of,
)
from .cache_manager import CacheManager

Json = dict[str, Any]
ProgressHook = Callable[[str, str], None]

_EPOCH = datetime.fromtimestamp(0, timezone.utc)


class GitHubError(Exception):
    pass


class AuthError(GitHubError):
    pass


class RateLimitError(GitHubError):
    def __init__(self, message: str, reset_at: float | None = None) -> None:
        super().__init__(message)
        self.reset_at = reset_at


class ForbiddenError(GitHubError):

    def __init__(self, message: str, needed: str = "") -> None:
        super().__init__(message)
        self.needed = needed


class SearchQuotaError(GitHubError):
    pass


@dataclass(slots=True)
class Fetched:

    data: Any
    status: int = 200
    from_cache: bool = False
    stale: bool = False
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.data is not None


class _SearchThrottle:

    def __init__(self, budget: int = SEARCH_RATE_LIMIT, window: float = 60.0) -> None:
        self.budget = max(budget - 2, 1)
        self.window = window
        self._stamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self, max_wait: float = 20.0) -> None:
        async with self._lock:
            now = time.monotonic()
            while self._stamps and now - self._stamps[0] > self.window:
                self._stamps.popleft()

            if len(self._stamps) >= self.budget:
                wait = self.window - (now - self._stamps[0]) + 0.2
                if wait > max_wait:
                    raise SearchQuotaError(
                        f"search quota exhausted, {wait:.0f}s until it refills"
                    )
                await asyncio.sleep(wait)
                now = time.monotonic()
                while self._stamps and now - self._stamps[0] > self.window:
                    self._stamps.popleft()

            self._stamps.append(time.monotonic())


def cache_key(method: str, url: str, params: dict | None) -> str:
    if not params:
        return f"{method}:{url}"
    encoded = "&".join(f"{k}={v}" for k, v in sorted(params.items()) if v is not None)
    return f"{method}:{url}?{encoded}"


class GitHubClient:
    def __init__(
        self,
        token: str,
        cache: CacheManager,
        settings: Settings,
        on_rate_limit: Callable[[RateLimit], None] | None = None,
    ) -> None:
        self.token = token
        self.cache = cache
        self.settings = settings
        self.on_rate_limit = on_rate_limit

        self.rate: RateLimit | None = None
        self.search_rate: RateLimit | None = None
        self.notes: list[str] = []
        self.requests_made = 0
        self.requests_saved = 0

        self._client: httpx.AsyncClient | None = None
        self._semaphore = asyncio.Semaphore(max(settings.concurrency, 1))
        self._search_throttle = _SearchThrottle()

    def note(self, message: str) -> None:
        if message not in self.notes:
            self.notes.append(message)


    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": ACCEPT_JSON,
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": USER_AGENT,
        }

    async def open(self) -> None:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=API_ROOT,
                headers=self.headers,
                timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=10.0),
                follow_redirects=True,
                limits=httpx.Limits(
                    max_connections=max(self.settings.concurrency * 2, 8),
                    max_keepalive_connections=max(self.settings.concurrency, 4),
                ),
            )

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    async def __aenter__(self) -> GitHubClient:
        await self.open()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()


    def _record_rate(self, headers: httpx.Headers) -> None:
        parsed = RateLimit.from_headers(headers)
        if parsed is None:
            return
        if parsed.resource == "search":
            self.search_rate = parsed
        else:
            self.rate = parsed
            if self.on_rate_limit is not None:
                self.on_rate_limit(parsed)

    async def fetch(
        self,
        path: str,
        *,
        params: dict | None = None,
        accept: str | None = None,
        ttl: float | None = None,
        use_etag: bool = True,
        allow_404: bool = False,
    ) -> Fetched:
        await self.open()
        assert self._client is not None

        key = cache_key("GET", path, params)
        effective_ttl = self.settings.cache_ttl if ttl is None else ttl

        if effective_ttl > 0:
            cached = self.cache.fresh(key, effective_ttl)
            if cached is not None:
                self.requests_saved += 1
                return Fetched(cached, from_cache=True)

        entry = self.cache.get(key)
        request_headers: dict[str, str] = {}
        if accept:
            request_headers["Accept"] = accept
        if use_etag and entry is not None and entry.etag:
            request_headers["If-None-Match"] = entry.etag

        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                async with self._semaphore:
                    response = await self._client.get(
                        path, params=params, headers=request_headers or None
                    )
            except (httpx.TransportError, httpx.HTTPError) as error:
                last_error = error
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BACKOFF_BASE**attempt)
                    continue
                break

            self.requests_made += 1
            self._record_rate(response.headers)
            status = response.status_code

            if status == 304 and entry is not None:
                self.requests_saved += 1
                self.cache.touch(key)
                return Fetched(entry.value, status=304, from_cache=True)

            if 200 <= status < 300:
                try:
                    data = response.json()
                except ValueError:
                    data = None
                if data is not None and status == 200:
                    self.cache.put(key, data, response.headers.get("etag"))
                return Fetched(
                    data, status=status, headers=dict(response.headers)
                )

            if status == 401:
                raise AuthError("GitHub rejected the token (401). Re-authenticate.")

            if status == 404:
                if allow_404:
                    return Fetched(None, status=404)
                raise GitHubError(f"Not found: {path}")

            if status in (403, 429):
                remaining = response.headers.get("x-ratelimit-remaining")
                retry_after = response.headers.get("retry-after")

                if remaining == "0":
                    reset = response.headers.get("x-ratelimit-reset")
                    reset_at = float(reset) if reset and reset.isdigit() else None
                    if entry is not None:
                        return Fetched(entry.value, status=status, from_cache=True, stale=True)
                    raise RateLimitError("GitHub rate limit exhausted", reset_at)

                if status == 403 and retry_after is None and not _is_throttle(response):
                    needed = response.headers.get("x-accepted-github-permissions", "")
                    raise ForbiddenError(_forbidden_message(response, path), needed)

                delay = float(retry_after) if retry_after and retry_after.isdigit() else BACKOFF_BASE ** (attempt + 1)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(min(delay, 30.0))
                    continue
                if entry is not None:
                    return Fetched(entry.value, status=status, from_cache=True, stale=True)
                raise RateLimitError("GitHub secondary rate limit hit; try again shortly")

            if status >= 500:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BACKOFF_BASE**attempt)
                    continue
                last_error = GitHubError(f"GitHub returned {status} for {path}")
                break

            raise GitHubError(f"GitHub returned {status} for {path}")

        if entry is not None:
            return Fetched(entry.value, status=0, from_cache=True, stale=True)
        if isinstance(last_error, GitHubError):
            raise last_error
        raise GitHubError(f"Could not reach GitHub: {last_error}")

    async def paginate(
        self,
        path: str,
        *,
        params: dict | None = None,
        max_pages: int = 5,
        per_page: int = 100,
        accept: str | None = None,
        ttl: float | None = None,
        items_key: str | None = None,
        search: bool = False,
    ) -> tuple[list[Json], bool]:
        collected: list[Json] = []
        base = dict(params or {})
        base["per_page"] = per_page

        for page in range(1, max_pages + 1):
            if search:
                await self._search_throttle.acquire()

            result = await self.fetch(
                path, params={**base, "page": page}, accept=accept, ttl=ttl
            )
            body = result.data
            if body is None:
                break

            if items_key:
                page_items = body.get(items_key) or [] if isinstance(body, dict) else []
                total = int(body.get("total_count") or 0) if isinstance(body, dict) else 0
            else:
                page_items = body if isinstance(body, list) else []
                total = 0

            collected.extend(page_items)

            if len(page_items) < per_page:
                return collected, False
            if items_key and total and len(collected) >= total:
                return collected, False

        return collected, True


    async def fetch_viewer(self) -> User:
        result = await self.fetch(ENDPOINTS["viewer"], ttl=3600)
        if not isinstance(result.data, dict):
            raise AuthError("Could not read the authenticated user.")
        return User.from_api(result.data)

    @staticmethod
    async def validate(token: str) -> tuple[User, list[str]]:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": ACCEPT_JSON,
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": USER_AGENT,
        }
        async with httpx.AsyncClient(
            base_url=API_ROOT, headers=headers, timeout=15.0
        ) as client:
            try:
                response = await client.get(ENDPOINTS["viewer"])
            except httpx.HTTPError as error:
                raise GitHubError(f"Could not reach GitHub: {error}") from error

        if response.status_code == 401:
            raise AuthError("GitHub rejected that token.")
        if response.status_code != 200:
            raise GitHubError(f"GitHub returned {response.status_code}.")

        scopes_header = response.headers.get("x-oauth-scopes", "")
        scopes = [scope.strip() for scope in scopes_header.split(",") if scope.strip()]
        return User.from_api(response.json()), scopes

    async def fetch_rate_limit(self) -> RateLimit | None:
        try:
            result = await self.fetch(ENDPOINTS["rate_limit"], ttl=0, use_etag=False)
        except GitHubError:
            return self.rate

        resources = (result.data or {}).get("resources") or {}
        core = resources.get("core") or {}
        search = resources.get("search") or {}

        if search:
            self.search_rate = _prefer(self.search_rate, _rate_from_block(search, "search"))
        if core:
            self.rate = _prefer(self.rate, _rate_from_block(core, "core"))
            if self.on_rate_limit is not None and self.rate:
                self.on_rate_limit(self.rate)
        return self.rate


    async def fetch_repos(self, progress: ProgressHook | None = None) -> list[Repo]:
        if progress:
            progress("repos", "listing repositories")

        raw, _ = await self.paginate(
            ENDPOINTS["repos"],
            params={
                "affiliation": self.settings.affiliation,
                "sort": "pushed",
                "direction": "desc",
            },
            max_pages=10,
        )

        repos: list[Repo] = []
        for payload in raw:
            repo = Repo.from_api(payload)
            if repo.archived and not self.settings.include_archived:
                continue
            if repo.fork and not self.settings.include_forks:
                continue
            repos.append(repo)

        repos.sort(key=lambda item: item.pushed_at or _EPOCH, reverse=True)
        if progress:
            progress("repos", f"{len(repos)} repositories")
        return repos


    def _accounts(self, repos: Sequence[Repo]) -> list[tuple[str, str]]:
        counts: dict[tuple[str, str], int] = {}
        for repo in repos:
            qualifier = "org" if repo.owner_type == "Organization" else "user"
            counts[(qualifier, repo.owner)] = counts.get((qualifier, repo.owner), 0) + 1
        return [key for key, _ in sorted(counts.items(), key=lambda kv: -kv[1])]

    async def _search(
        self,
        kind: str,
        repos: Sequence[Repo],
        progress: ProgressHook | None = None,
    ) -> tuple[list[Json], bool]:
        accounts = self._accounts(repos)
        if not accounts:
            return [], False

        per_account = max(self.settings.max_search_pages // max(len(accounts), 1), 2)
        items: list[Json] = []
        truncated = False

        for qualifier, login in accounts:
            terms = ["is:open", f"is:{kind}", f"{qualifier}:{login}"]
            if not self.settings.include_archived:
                terms.append("archived:false")
            if self.settings.include_forks:
                terms.append("fork:true")

            if progress:
                progress(kind, f"searching {login}")

            try:
                found, more = await self.paginate(
                    ENDPOINTS["search_issues"],
                    params={"q": " ".join(terms), "sort": "updated", "order": "desc"},
                    max_pages=per_account,
                    items_key="items",
                    search=True,
                )
            except SearchQuotaError:
                truncated = True
                break
            except GitHubError:
                truncated = True
                continue

            items.extend(found)
            truncated = truncated or more

        return items, truncated

    async def fetch_issues(
        self, repos: Sequence[Repo], progress: ProgressHook | None = None
    ) -> tuple[list[Issue], bool]:
        raw, truncated = await self._search("issue", repos, progress)

        issues = [Issue.from_api(payload) for payload in raw]
        issues = dedupe(issues, key=lambda item: item.id)
        issues.sort(key=lambda item: item.updated_at or _EPOCH, reverse=True)

        if progress:
            progress("issue", f"{len(issues)} open issues")
        return issues, truncated

    async def fetch_pulls(
        self, repos: Sequence[Repo], progress: ProgressHook | None = None
    ) -> tuple[list[PullRequest], bool]:
        raw, truncated = await self._search("pr", repos, progress)

        pulls = [PullRequest.from_api(payload) for payload in raw]
        pulls = dedupe(pulls, key=lambda item: item.id)
        pulls.sort(key=lambda item: item.updated_at or _EPOCH, reverse=True)

        if progress:
            progress("pr", f"{len(pulls)} open pull requests")
        return pulls, truncated

    async def enrich_pulls(
        self, pulls: Sequence[PullRequest], progress: ProgressHook | None = None
    ) -> None:
        limit = self.settings.pr_enrich_limit
        if limit <= 0 or not pulls:
            return

        targets = list(pulls)[:limit]
        done = 0
        lock = asyncio.Lock()

        async def resolve(pull: PullRequest) -> None:
            nonlocal done
            try:
                detail = await self.fetch(
                    ENDPOINTS["pull"].format(repo=pull.repo, number=pull.number),
                    ttl=self.settings.cache_ttl,
                    allow_404=True,
                )
                if isinstance(detail.data, dict):
                    pull.merge_detail(detail.data)
                if pull.head_sha:
                    pull.checks = await self._checks_for(pull.repo, pull.head_sha)
            except GitHubError:
                pass
            finally:
                async with lock:
                    done += 1
                    if progress and done % 5 == 0:
                        progress("pr", f"details {done}/{len(targets)}")

        await _gather_bounded(
            [resolve(pull) for pull in targets], self.settings.concurrency
        )
        if progress:
            progress("pr", f"details {len(targets)}/{len(targets)}")

    async def _checks_for(self, repo: str, sha: str) -> CheckSummary:
        passed = failed = pending = 0

        status = await self.fetch(
            ENDPOINTS["combined_status"].format(repo=repo, sha=sha),
            ttl=self.settings.cache_ttl,
            allow_404=True,
        )
        if isinstance(status.data, dict):
            for entry in status.data.get("statuses") or []:
                state = str(entry.get("state") or "")
                if state == "success":
                    passed += 1
                elif state in ("failure", "error"):
                    failed += 1
                elif state == "pending":
                    pending += 1

        runs = await self.fetch(
            ENDPOINTS["check_runs"].format(repo=repo, sha=sha),
            ttl=self.settings.cache_ttl,
            allow_404=True,
        )
        if isinstance(runs.data, dict):
            for entry in runs.data.get("check_runs") or []:
                if str(entry.get("status")) != "completed":
                    pending += 1
                    continue
                conclusion = str(entry.get("conclusion") or "")
                if conclusion in ("success", "skipped", "neutral"):
                    passed += 1
                elif conclusion in ("failure", "timed_out", "cancelled", "action_required"):
                    failed += 1
                else:
                    pending += 1

        total = passed + failed + pending
        if total == 0:
            return CheckSummary(state="neutral", total=0)
        if failed:
            state = "failure"
        elif pending:
            state = "pending"
        else:
            state = "success"
        return CheckSummary(state=state, total=total, passed=passed, failed=failed)


    async def fetch_stars(
        self, repos: Sequence[Repo], progress: ProgressHook | None = None
    ) -> list[StarEvent]:
        limit = self.settings.star_repo_limit
        if limit <= 0:
            return []

        candidates = [repo for repo in repos if repo.stars > 0]
        candidates.sort(key=lambda repo: repo.stars, reverse=True)
        candidates = candidates[:limit]
        if not candidates:
            return []

        events: list[StarEvent] = []
        lock = asyncio.Lock()
        done = 0

        async def scan(repo: Repo) -> None:
            nonlocal done
            page = max(math.ceil(repo.stars / 100), 1)
            try:
                result = await self.fetch(
                    ENDPOINTS["stargazers"].format(repo=repo.full_name),
                    params={"per_page": 100, "page": page},
                    accept=ACCEPT_STAR,
                    ttl=self.settings.cache_ttl,
                    allow_404=True,
                )
            except ForbiddenError:
                self.note(
                    "stargazers need a classic token (fine-grained ones are refused "
                    "unless granted Contents: write)"
                )
                return
            except GitHubError:
                return

            rows = result.data if isinstance(result.data, list) else []
            found = [
                StarEvent.from_api(row, repo.full_name, repo.stars)
                for row in rows[-12:]
                if isinstance(row, dict)
            ]
            async with lock:
                events.extend(found)
                done += 1
                if progress and done % 10 == 0:
                    progress("stars", f"scanned {done}/{len(candidates)} repos")

        await _gather_bounded(
            [scan(repo) for repo in candidates], self.settings.concurrency
        )

        events = [event for event in events if event.starred_at is not None]
        events.sort(key=lambda item: item.starred_at or _EPOCH, reverse=True)
        events = dedupe(events, key=lambda item: (item.repo, item.user))

        if progress:
            progress("stars", f"{len(events)} recent stargazers")
        return events[:400]


    async def fetch_events(
        self, login: str, progress: ProgressHook | None = None
    ) -> list[ActivityEvent]:
        if progress:
            progress("activity", "reading event feeds")

        collected: list[Json] = []
        for endpoint in ("user_events", "received_events"):
            try:
                page, _ = await self.paginate(
                    ENDPOINTS[endpoint].format(login=login),
                    max_pages=2,
                    ttl=min(self.settings.cache_ttl, 300),
                )
                collected.extend(page)
            except GitHubError:
                continue

        events = [ActivityEvent.from_api(payload) for payload in collected]
        events = dedupe(events, key=lambda item: item.id)
        events.sort(key=lambda item: item.created_at or _EPOCH, reverse=True)
        return events[:300]

    async def fetch_notifications(
        self, progress: ProgressHook | None = None
    ) -> list[Notification]:
        if progress:
            progress("activity", "reading notifications")
        try:
            raw, _ = await self.paginate(
                ENDPOINTS["notifications"],
                params={"all": str(self.settings.notifications_all).lower()},
                max_pages=2,
                per_page=50,
                ttl=min(self.settings.cache_ttl, 300),
            )
        except ForbiddenError:
            self.note(
                "notifications need a classic token with the 'notifications' scope"
            )
            return []
        except GitHubError:
            return []

        notifications = [Notification.from_api(payload) for payload in raw]
        notifications.sort(key=lambda item: item.updated_at or _EPOCH, reverse=True)
        return notifications


    async def fetch_languages(self, repo: str) -> dict[str, int]:
        result = await self.fetch(
            ENDPOINTS["languages"].format(repo=repo),
            ttl=self.settings.code_scan_ttl_hours * 3600,
            allow_404=True,
        )
        data = result.data
        if not isinstance(data, dict):
            return {}
        return {str(k): int(v) for k, v in data.items() if isinstance(v, int)}

    async def fetch_contributor_stats(
        self, repo: str, login: str, attempts: int = 3
    ) -> tuple[int, int, int, bool]:
        path = ENDPOINTS["contributor_stats"].format(repo=repo)

        for attempt in range(attempts):
            try:
                result = await self.fetch(
                    path,
                    ttl=self.settings.code_scan_ttl_hours * 3600,
                    allow_404=True,
                )
            except ForbiddenError:
                self.note("contributor statistics are not readable with this token")
                return 0, 0, 0, False
            except GitHubError:
                return 0, 0, 0, False

            if result.status == 202 or not isinstance(result.data, list):
                if attempt < attempts - 1:
                    await asyncio.sleep(2.0 * (attempt + 1))
                    continue
                return 0, 0, 0, False

            rows = result.data
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if login_of(row.get("author")) != login:
                    continue
                additions = deletions = commits = 0
                for week in row.get("weeks") or []:
                    additions += int(week.get("a") or 0)
                    deletions += int(week.get("d") or 0)
                    commits += int(week.get("c") or 0)
                return additions, deletions, commits, True

            return 0, 0, 0, True

        return 0, 0, 0, False

    async def fetch_code_stats(
        self,
        repos: Sequence[Repo],
        login: str,
        progress: ProgressHook | None = None,
    ) -> CodeStats:
        stats = CodeStats(scanned_at=datetime.now(timezone.utc))
        if not repos:
            return stats

        done = 0
        lock = asyncio.Lock()
        results: list[RepoCode] = []

        async def scan(repo: Repo) -> None:
            nonlocal done
            languages = await self.fetch_languages(repo.full_name)
            additions, deletions, commits, ready = await self.fetch_contributor_stats(
                repo.full_name, login
            )
            entry = RepoCode(
                repo=repo.full_name,
                languages=languages,
                additions=additions,
                deletions=deletions,
                commits=commits,
                stats_ready=ready,
                archived=repo.archived,
                private=repo.private,
            )
            async with lock:
                results.append(entry)
                if not ready:
                    stats.incomplete.append(repo.full_name)
                done += 1
                if progress and done % 5 == 0:
                    progress("code", f"scanned {done}/{len(repos)} repositories")

        await _gather_bounded(
            [scan(repo) for repo in repos], self.settings.concurrency
        )

        results.sort(key=lambda item: -item.additions)
        stats.repos = results
        if progress:
            progress("code", f"{len(results)} repositories scanned")
        return stats


    async def fetch_issue_detail(
        self, repo: str, number: int
    ) -> tuple[Issue | None, list[Comment]]:
        issue_result = await self.fetch(
            ENDPOINTS["issue"].format(repo=repo, number=number),
            ttl=min(self.settings.cache_ttl, 300),
            allow_404=True,
        )
        issue = (
            Issue.from_api(issue_result.data, repo)
            if isinstance(issue_result.data, dict)
            else None
        )

        comments: list[Comment] = []
        if issue is not None and issue.comments:
            try:
                raw, _ = await self.paginate(
                    ENDPOINTS["issue_comments"].format(repo=repo, number=number),
                    max_pages=2,
                    per_page=50,
                    ttl=min(self.settings.cache_ttl, 300),
                )
                comments = [Comment.from_api(payload) for payload in raw]
            except GitHubError:
                comments = []

        return issue, comments


def _body_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""
    return str(payload.get("message") or "") if isinstance(payload, dict) else ""


def _is_throttle(response: httpx.Response) -> bool:
    message = _body_message(response).lower()
    return "secondary rate limit" in message or "abuse" in message or "too many requests" in message


def _forbidden_message(response: httpx.Response, path: str) -> str:
    message = _body_message(response) or "Forbidden"
    needed = response.headers.get("x-accepted-github-permissions", "")
    if "not accessible by personal access token" in message.lower():
        hint = f" (needs: {needed})" if needed else ""
        return f"{path} is not available to this token{hint}"
    return f"{path}: {message}"


def _prefer(known: RateLimit | None, reported: RateLimit) -> RateLimit:
    if known is None:
        return reported
    if reported.reset_at and known.reset_at and reported.reset_at > known.reset_at:
        return reported
    return reported if reported.remaining < known.remaining else known


def _rate_from_block(block: Json, resource: str) -> RateLimit:
    reset = block.get("reset")
    return RateLimit(
        limit=int(block.get("limit") or 0),
        remaining=int(block.get("remaining") or 0),
        used=int(block.get("used") or 0),
        reset_at=datetime.fromtimestamp(int(reset), timezone.utc) if reset else None,
        resource=resource,
    )


async def _gather_bounded(tasks: Iterable[Awaitable[Any]], limit: int) -> list[Any]:
    semaphore = asyncio.Semaphore(max(limit, 1))

    async def guarded(task: Awaitable[Any]) -> Any:
        async with semaphore:
            return await task

    return await asyncio.gather(*(guarded(task) for task in tasks), return_exceptions=True)
