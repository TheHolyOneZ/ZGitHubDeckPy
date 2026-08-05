# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

import sys

from textual import work
from textual.app import App
from textual.binding import Binding

from .api.cache_manager import CacheManager
from .api.github_client import AuthError, GitHubClient, GitHubError
from .api.store import DataStore, SyncState
from .config.settings import (
    APP_NAME,
    BRAND,
    CACHE_DB,
    Settings,
    TokenSource,
    ensure_dirs,
    resolve_token,
)
from .ui.screens.login_screen import LoginScreen
from .ui.screens.main_screen import MainScreen
from .ui.screens.menu_screen import MenuScreen
from .ui.screens.settings_screen import SettingsScreen
from .ui.theme import APP_CSS


class ZDeckApp(App):

    TITLE = f"{APP_NAME} · {BRAND}"
    SUB_TITLE = "github command deck"
    CSS = APP_CSS
    ENABLE_COMMAND_PALETTE = False

    BINDINGS = [
        Binding("ctrl+q", "quit", "quit", show=False, priority=True),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        ensure_dirs()
        self.settings = Settings.load()
        self.cache = CacheManager(CACHE_DB)
        self.store = DataStore()
        self.token_source: TokenSource | None = resolve_token()
        self.client: GitHubClient | None = None
        self._auto_timer = None
        self._last_stage = ""


    @property
    def authenticated(self) -> bool:
        return self.token_source is not None

    def on_mount(self) -> None:
        self.store.load_snapshot(self.cache)
        self._build_client()

        self.push_screen(MenuScreen())

        if self.authenticated:
            self.start_sync()
        else:
            self.call_after_refresh(self.open_login)

        self._schedule_auto_refresh()

    async def on_unmount(self) -> None:
        if self.client is not None:
            await self.client.close()
        self.cache.close()

    def _build_client(self) -> None:
        if self.token_source is None:
            self.client = None
            return
        self.client = GitHubClient(
            token=self.token_source.token,
            cache=self.cache,
            settings=self.settings,
            on_rate_limit=self._on_rate_limit,
        )

    def adopt_token(self, token: str | None) -> None:
        self.token_source = resolve_token() if token else None
        self._build_client()
        self._refresh_menu()


    def open_dashboard(self) -> None:
        if not any(isinstance(screen, MainScreen) for screen in self.screen_stack):
            self.push_screen(MainScreen())

    def open_login(self) -> None:
        if not any(isinstance(screen, LoginScreen) for screen in self.screen_stack):
            self.push_screen(LoginScreen())

    def open_settings(self) -> None:
        if not any(isinstance(screen, SettingsScreen) for screen in self.screen_stack):
            self.push_screen(SettingsScreen())

    @property
    def dashboard(self) -> MainScreen | None:
        for screen in self.screen_stack:
            if isinstance(screen, MainScreen):
                return screen
        return None

    def _refresh_menu(self) -> None:
        for screen in self.screen_stack:
            if isinstance(screen, MenuScreen):
                screen.refresh_rows()
                screen.refresh_status()


    def settings_changed(self, key: str) -> None:
        if self.client is not None:
            self.client.settings = self.settings

        if key == "auto_refresh_minutes":
            self._schedule_auto_refresh()

        dashboard = self.dashboard
        if dashboard is not None and key in ("date_style", "default_tab"):
            dashboard.refresh_data()

    def _schedule_auto_refresh(self) -> None:
        if self._auto_timer is not None:
            self._auto_timer.stop()
            self._auto_timer = None

        minutes = self.settings.auto_refresh_minutes
        if minutes > 0:
            self._auto_timer = self.set_interval(minutes * 60, self._auto_refresh)

    def _auto_refresh(self) -> None:
        if self.authenticated and not self.store.sync_state.running:
            self.start_sync()


    @work(exclusive=True, group="sync")
    async def start_sync(self, force: bool = False) -> None:
        if self.client is None:
            self.notify("No token — sign in first.", severity="warning")
            return

        if force:
            self.client.settings = self.settings

        self._last_stage = ""
        try:
            state = await self.store.sync(self.client, progress=self._on_progress)
        except AuthError as error:
            self.notify(str(error), title="Authentication", severity="error")
            self.token_source = None
            self.client = None
            self._refresh_menu()
            self.open_login()
            return
        except GitHubError as error:
            self.notify(str(error), title="GitHub", severity="error")
            return

        self.store.save_snapshot(self.cache)
        self._publish(state)

        if state.errors:
            self.notify(
                f"Synced with {len(state.errors)} problem(s): {state.errors[0]}",
                title="Partial sync",
                severity="warning",
            )
        elif force:
            counts = (
                f"{self.store.repo_count} repos · "
                f"{len(self.store.issues)} issues · "
                f"{len(self.store.pulls)} pull requests"
            )
            self.notify(counts, title=f"Synced in {state.elapsed:.1f}s")

    @work(exclusive=True, group="code")
    async def start_code_scan(self) -> None:
        if self.client is None:
            self.notify("No token - sign in first.", severity="warning")
            return
        if not self.store.repos:
            self.notify("Sync first so there are repositories to measure.", severity="warning")
            return

        try:
            stats = await self.store.scan_code(self.client, progress=self._on_progress)
        except GitHubError as error:
            self.notify(str(error), title="Code scan", severity="error")
            return

        self.store.save_snapshot(self.cache)
        self._publish(self.store.sync_state)

        pending = len(stats.incomplete)
        detail = f"{stats.additions:,} lines across {stats.repos_touched} repositories"
        if pending:
            detail += f" - {pending} still being computed by GitHub"
        self.notify(detail, title="Lines you have ever written")

    def _on_progress(self, state: SyncState) -> None:
        dashboard = self.dashboard
        if dashboard is not None:
            if state.stage != self._last_stage:
                self._last_stage = state.stage
                dashboard.refresh_data()
            dashboard.set_sync_state(state)

        self._refresh_menu()

    def _publish(self, state: SyncState) -> None:
        dashboard = self.dashboard
        if dashboard is not None:
            dashboard.refresh_data()
            dashboard.set_sync_state(state)
        self._refresh_menu()

    def _on_rate_limit(self, rate) -> None:
        self.store.rate = rate


def main() -> int:
    try:
        ZDeckApp().run()
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
