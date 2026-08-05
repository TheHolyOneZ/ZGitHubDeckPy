# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from ...config.settings import TAGLINE
from ...utils.formatters import compact_number, keyhint, time_ago
from ..theme import CORAL, CREAM, FAINT, GREEN, LINE, MARK, MUTED, RED
from ..widgets.common import Logo, MenuChosen, MenuHover, MenuOption


class MenuScreen(Screen):

    ITEMS: tuple[tuple[str, str, str], ...] = (
        ("dashboard", "open dashboard", "issues, pull requests, stars and activity"),
        ("sync", "sync now", "refresh every repository from GitHub"),
        ("account", "account", "swap tokens, check what they unlock"),
        ("settings", "settings", "what gets fetched, how often, and how it looks"),
        ("quit", "quit", "see you next time"),
    )

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.index = 0

    def compose(self) -> ComposeResult:
        self.add_class("-centered")
        with Vertical(id="shell"):
            yield Logo(id="logo")
            yield Static(id="tagline")
            with Vertical(id="menu"):
                for key, label, blurb in self.ITEMS:
                    yield MenuOption(key, label, blurb)
            yield Static(id="account-line")
            yield Static(id="cache-line")
            yield Static(id="hint")

    def on_mount(self) -> None:
        tagline = Text(justify="center")
        tagline.append(TAGLINE, style=MUTED)
        self.query_one("#tagline", Static).update(tagline)

        self.query_one("#hint", Static).update(
            keyhint(
                [
                    ("↑↓", "move"),
                    ("enter", "select"),
                    ("a", "account"),
                    ("s", "settings"),
                    ("q", "quit"),
                ]
            )
        )
        if not getattr(self.app, "authenticated", False):
            self.index = [item[0] for item in self.ITEMS].index("account")

        self.refresh_rows()
        self.refresh_status()


    @property
    def _composed(self) -> bool:
        return bool(self.is_mounted and self.query("#account-line"))

    def refresh_rows(self) -> None:
        authenticated = getattr(self.app, "authenticated", False)
        for position, option in enumerate(self.query(MenuOption)):
            option.selected = position == self.index
            option.enabled = authenticated or option.key in ("account", "quit")
            if option.key == "account":
                option.label = "account" if authenticated else "sign in to GitHub"
                option.blurb = (
                    "swap tokens, check what they unlock"
                    if authenticated
                    else "needed before anything else works"
                )
                option.refresh()

    def refresh_status(self) -> None:
        if not self._composed:
            return

        app = self.app
        store = app.store

        account = Text(justify="center", no_wrap=True, overflow="ellipsis")
        if not getattr(app, "authenticated", False):
            account.append("● ", style=RED)
            account.append("no token — press ", style=MUTED)
            account.append("a", style=CORAL)
            account.append(" to sign in", style=MUTED)
        else:
            account.append("● ", style=GREEN)
            login = store.viewer.login if store.viewer else "authenticating…"
            account.append(f"@{login}", style=CREAM)
            if store.repo_count:
                account.append("  ·  ", style=LINE)
                account.append(f"{store.repo_count} repos", style=MUTED)
                account.append("  ·  ", style=LINE)
                account.append(f"{compact_number(store.total_stars)} stars", style=MUTED)
            source = getattr(app, "token_source", None)
            if source is not None:
                account.append("  ·  ", style=LINE)
                account.append(f"token from {source.origin}", style=FAINT)
        self.query_one("#account-line", Static).update(account)

        cache = Text(justify="center", no_wrap=True, overflow="ellipsis")
        state = store.sync_state
        if state.running:
            cache.append(f"{MARK} ", style=CORAL)
            cache.append(f"syncing {state.label()}", style=CREAM)
            if state.detail:
                cache.append(f" · {state.detail}", style=MUTED)
        else:
            cache.append("cache ", style=FAINT)
            cache.append(app.cache.describe(), style=MUTED)
            if store.synced_at:
                cache.append("  ·  ", style=LINE)
                cache.append(f"synced {time_ago(store.synced_at)}", style=FAINT)
        self.query_one("#cache-line", Static).update(cache)

    def on_screen_resume(self, event: events.ScreenResume) -> None:
        self.refresh_rows()
        self.refresh_status()


    def move(self, step: int) -> None:
        self.index = (self.index + step) % len(self.ITEMS)
        self.refresh_rows()

    def activate(self, key: str) -> None:
        app = self.app
        if key in ("dashboard", "sync", "settings") and not getattr(app, "authenticated", False):
            app.notify("Sign in first — a Personal Access Token is required.", severity="warning")
            self.activate("account")
            return

        if key == "dashboard":
            app.open_dashboard()
        elif key == "sync":
            app.start_sync(force=True)
            app.open_dashboard()
        elif key == "account":
            app.open_login()
        elif key == "settings":
            app.open_settings()
        elif key == "quit":
            app.exit()

    def on_menu_hover(self, message: MenuHover) -> None:
        keys = [item[0] for item in self.ITEMS]
        if message.key in keys:
            self.index = keys.index(message.key)
            self.refresh_rows()

    def on_menu_chosen(self, message: MenuChosen) -> None:
        self.activate(message.key)

    def on_key(self, event: events.Key) -> None:
        key = event.key
        letter = (event.character or "").lower()

        if key in ("up", "k", "shift+tab"):
            self.move(-1)
        elif key in ("down", "j", "tab"):
            self.move(1)
        elif key in ("enter", "space"):
            self.activate(self.ITEMS[self.index][0])
        elif letter == "a":
            self.activate("account")
        elif letter == "s":
            self.activate("settings")
        elif letter == "d":
            self.activate("dashboard")
        elif letter == "r":
            self.activate("sync")
        elif letter == "q" or key == "escape":
            self.app.exit()
        else:
            return

        event.stop()
        event.prevent_default()
