# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

APP_NAME = "ZDECK"
APP_SLUG = "zdeck"
BRAND = "TheHolyOneZ"
TAGLINE = "github command deck"
VERSION = "1.0.0"
USER_AGENT = f"{APP_SLUG}/{VERSION}"


CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_SLUG
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / APP_SLUG

SETTINGS_FILE = CONFIG_DIR / "settings.json"
TOKEN_FILE = CONFIG_DIR / "token"
CACHE_DB = CACHE_DIR / "cache.sqlite3"


def ensure_dirs() -> None:
    for directory in (CONFIG_DIR, CACHE_DIR):
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass


API_ROOT = "https://api.github.com"
WEB_ROOT = "https://github.com"

ENDPOINTS = {
    "viewer": "/user",
    "repos": "/user/repos",
    "search_issues": "/search/issues",
    "notifications": "/notifications",
    "rate_limit": "/rate_limit",
    "user_events": "/users/{login}/events",
    "received_events": "/users/{login}/received_events",
    "stargazers": "/repos/{repo}/stargazers",
    "pull": "/repos/{repo}/pulls/{number}",
    "combined_status": "/repos/{repo}/commits/{sha}/status",
    "check_runs": "/repos/{repo}/commits/{sha}/check-runs",
    "issue": "/repos/{repo}/issues/{number}",
    "issue_comments": "/repos/{repo}/issues/{number}/comments",
    "languages": "/repos/{repo}/languages",
    "contributor_stats": "/repos/{repo}/stats/contributors",
}

ACCEPT_JSON = "application/vnd.github+json"
ACCEPT_STAR = "application/vnd.github.star+json"
API_VERSION = "2022-11-28"

REQUIRED_SCOPES = ("repo", "read:org", "notifications")
PAT_URL = f"{WEB_ROOT}/settings/tokens/new?scopes=repo,read:org,notifications"

REQUEST_TIMEOUT = 25.0
MAX_RETRIES = 3
BACKOFF_BASE = 1.6

CORE_RATE_LIMIT = 5000
SEARCH_RATE_LIMIT = 30
SEARCH_RESULT_CAP = 1000
RATE_LIMIT_FLOOR = 60


@dataclass(frozen=True)
class TokenSource:

    token: str
    origin: str
    editable: bool

    @property
    def masked(self) -> str:
        if len(self.token) <= 8:
            return "•" * len(self.token)
        return f"{self.token[:4]}{'•' * 8}{self.token[-4:]}"


def _read_token_file() -> str | None:
    try:
        value = TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def _read_gh_cli() -> str | None:
    if not shutil.which("gh"):
        return None
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def resolve_token() -> TokenSource | None:
    for variable in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(variable, "").strip()
        if value:
            return TokenSource(value, f"${variable}", editable=False)

    value = _read_token_file()
    if value:
        return TokenSource(value, str(TOKEN_FILE), editable=True)

    value = _read_gh_cli()
    if value:
        return TokenSource(value, "gh auth token", editable=False)

    return None


def save_token(token: str) -> None:
    ensure_dirs()
    TOKEN_FILE.write_text(token.strip() + "\n", encoding="utf-8")
    try:
        TOKEN_FILE.chmod(0o600)
    except OSError:
        pass


def clear_token() -> None:
    try:
        TOKEN_FILE.unlink()
    except OSError:
        pass


@dataclass
class Settings:

    affiliation: str = "owner,organization_member"
    include_archived: bool = False
    include_forks: bool = False

    max_search_pages: int = 10
    pr_enrich_limit: int = 40
    star_repo_limit: int = 60
    concurrency: int = 8

    cache_ttl_minutes: int = 15
    auto_refresh_minutes: int = 0
    code_scan_ttl_hours: int = 24

    date_style: str = "relative"
    notifications_all: bool = False
    default_tab: str = "issues"


    @classmethod
    def load(cls) -> Settings:
        try:
            raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        if not isinstance(raw, dict):
            return cls()
        known = {f.name: raw[f.name] for f in fields(cls) if f.name in raw}
        try:
            return cls(**known)
        except TypeError:
            return cls()

    def save(self) -> None:
        try:
            ensure_dirs()
            SETTINGS_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except OSError:
            pass


    @property
    def cache_ttl(self) -> float:
        return max(self.cache_ttl_minutes, 0) * 60.0

    def summary(self) -> str:
        scope = "owned + orgs" if "organization_member" in self.affiliation else "owned only"
        bits = [scope, f"{self.cache_ttl_minutes}m cache"]
        if self.include_forks:
            bits.append("forks")
        if self.include_archived:
            bits.append("archived")
        if self.auto_refresh_minutes:
            bits.append(f"auto {self.auto_refresh_minutes}m")
        return " · ".join(bits)


@dataclass(frozen=True)
class Preference:

    key: str
    label: str
    values: list = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    help: str = ""

    def index_of(self, value: object) -> int:
        try:
            return self.values.index(value)
        except ValueError:
            return 0

    def label_for(self, value: object) -> str:
        return self.labels[self.index_of(value)]


PREFERENCES: tuple[Preference, ...] = (
    Preference(
        "affiliation",
        "repositories",
        ["owner", "owner,organization_member", "owner,collaborator,organization_member"],
        ["owned only", "owned + orgs", "owned + orgs + collab"],
        "which repositories get pulled into the aggregate views",
    ),
    Preference(
        "include_forks",
        "forks",
        [False, True],
        ["hidden", "shown"],
        "include repositories you forked from someone else",
    ),
    Preference(
        "include_archived",
        "archived",
        [False, True],
        ["hidden", "shown"],
        "include repositories you have archived",
    ),
    Preference(
        "cache_ttl_minutes",
        "cache lifetime",
        [5, 15, 30, 60, 240],
        ["5 minutes", "15 minutes", "30 minutes", "1 hour", "4 hours"],
        "how long cached responses count as fresh before refetching",
    ),
    Preference(
        "auto_refresh_minutes",
        "auto refresh",
        [0, 5, 15, 30],
        ["off", "every 5 min", "every 15 min", "every 30 min"],
        "background resync while the dashboard stays open",
    ),
    Preference(
        "max_search_pages",
        "issue depth",
        [2, 5, 10],
        ["200 results", "500 results", "1000 results (max)"],
        "how deep to page the search API for issues and pull requests",
    ),
    Preference(
        "pr_enrich_limit",
        "pr detail",
        [0, 20, 40, 80],
        ["off (fast)", "top 20", "top 40", "top 80"],
        "resolve mergeability and CI status for the newest pull requests",
    ),
    Preference(
        "star_repo_limit",
        "star scan",
        [0, 25, 60, 150],
        ["off", "top 25 repos", "top 60 repos", "top 150 repos"],
        "how many starred repositories to scan for recent stargazers",
    ),
    Preference(
        "concurrency",
        "parallelism",
        [4, 8, 16],
        ["4 requests", "8 requests", "16 requests"],
        "simultaneous in-flight requests during a sync",
    ),
    Preference(
        "notifications_all",
        "notifications",
        [False, True],
        ["unread only", "all recent"],
        "whether the activity tab shows read notifications too",
    ),
    Preference(
        "date_style",
        "timestamps",
        ["relative", "absolute"],
        ["relative (3d)", "absolute (date)"],
        "how ages are rendered across every table",
    ),
    Preference(
        "default_tab",
        "opening tab",
        ["issues", "pulls", "stars", "activity"],
        ["issues", "pull requests", "stars", "activity"],
        "which tab the dashboard lands on",
    ),
)
