# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

import webbrowser
from pathlib import Path

from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text
from textual import events, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Input, Static

from ...api.github_client import AuthError, GitHubClient, GitHubError
from ...config.settings import (
    PAT_URL,
    TOKEN_FILE,
    clear_token,
    resolve_token,
    save_token,
)
from ...utils.formatters import keyhint
from ..theme import CORAL, CREAM, FAINT, GREEN, LINE, MARK, MUTED, RED, YELLOW
from ..widgets.common import brand_line

PERMISSIONS: tuple[tuple[str, str, bool], ...] = (
    ("issues, pull requests, code stats", "nothing — works out of the box", True),
    ("private repositories", "repo", True),
    ("organisation repositories", "read:org", True),
    ("notifications feed", "notifications", False),
    ("stargazers feed", "nothing (public repos)", False),
)


def _short_path(path) -> str:
    try:
        return f"~/{Path(path).relative_to(Path.home())}"
    except ValueError:
        return str(path)


class LoginScreen(Screen):

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.checking = False

    def compose(self) -> ComposeResult:
        self.add_class("-centered")
        with Vertical(id="shell"):
            with Vertical(id="topbar"):
                yield Static(id="brand")
            with Vertical(id="login-card"):
                yield Static(id="login-intro")
                yield Static(id="login-perms")
                yield Input(
                    placeholder="paste your token here, then press enter",
                    password=True,
                    id="token-input",
                )
                yield Static(id="login-status")
            yield Static(id="hint")

    def on_mount(self) -> None:
        left, _ = brand_line()
        self.query_one("#brand", Static).update(left)

        card = self.query_one("#login-card")
        card.border_title = f"[{CORAL}]{MARK}[/] sign in to GitHub"
        card.border_subtitle = "read-only · nothing is ever written"

        self.query_one("#login-intro", Static).update(self._intro())
        self.query_one("#login-perms", Static).update(self._permissions())
        self._set_hint()
        self.refresh_status()
        self.query_one(Input).focus()

    def _set_hint(self) -> None:
        authenticated = getattr(self.app, "authenticated", False)
        keys = [("enter", "sign in"), ("ctrl+o", "create a token"), ("ctrl+r", "reveal")]
        if authenticated:
            keys.append(("ctrl+d", "sign out"))
        keys.append(("esc", "back" if authenticated else "skip"))
        self.query_one("#hint", Static).update(keyhint(keys))


    def _intro(self) -> RenderableType:
        line = Text(no_wrap=True, overflow="ellipsis")
        line.append("Press ", style=MUTED)
        line.append("ctrl+o", style=CORAL)
        line.append(
            " to open GitHub's token page with the right boxes ticked, "
            "then paste it below.",
            style=MUTED,
        )
        return line

    def _permissions(self) -> RenderableType:
        grid = Table.grid(padding=(0, 2))
        grid.add_column(width=1, no_wrap=True)
        grid.add_column(width=33, no_wrap=True, overflow="ellipsis")
        grid.add_column(no_wrap=True, overflow="ellipsis")

        grid.add_row(
            Text(""),
            Text("what you get", style=CREAM),
            Text("what to tick", style=CREAM),
        )

        for feature, requirement, fine_grained_ok in PERMISSIONS:
            mark = Text("✓", style=GREEN) if fine_grained_ok else Text("!", style=YELLOW)
            need = Text(no_wrap=True)
            need.append(requirement, style=CREAM)
            if not fine_grained_ok:
                need.append("  ·  classic token only", style=YELLOW)
            grid.add_row(mark, Text(feature, style=MUTED), need)

        footnote = Text(no_wrap=True, overflow="ellipsis")
        footnote.append("!", style=YELLOW)
        footnote.append(
            "  fine-grained tokens do everything else — GitHub refuses only those two.",
            style=FAINT,
        )

        return Group(Text(""), grid, Text(""), footnote)

    def refresh_status(self) -> None:
        status = Text(no_wrap=True, overflow="ellipsis")
        source = resolve_token()

        if source is None:
            status.append("● ", style=RED)
            status.append("not signed in", style=CREAM)
            status.append("   waiting for a token", style=FAINT)
        else:
            status.append("● ", style=GREEN)
            status.append(source.masked, style=CREAM)
            status.append("  ·  ", style=LINE)
            status.append(f"from {source.origin}", style=MUTED)
            if not source.editable:
                status.append("  (the environment wins)", style=FAINT)

        self.query_one("#login-status", Static).update(status)
        self._set_hint()

    def _set_card(self, modifier: str | None) -> None:
        card = self.query_one("#login-card")
        for name in ("-ok", "-bad", "-busy"):
            card.remove_class(name)
        if modifier:
            card.add_class(modifier)


    @work(exclusive=True, group="auth")
    async def validate(self, token: str) -> None:
        status = self.query_one("#login-status", Static)

        busy = Text()
        busy.append("◐ ", style=CORAL)
        busy.append("checking with GitHub…", style=CREAM)
        status.update(busy)
        self._set_card("-busy")
        self.checking = True

        try:
            user, scopes = await GitHubClient.validate(token)
        except (AuthError, GitHubError) as error:
            self._fail(str(error))
            return
        finally:
            self.checking = False

        save_token(token)
        self.app.adopt_token(token)

        result = Text(no_wrap=True, overflow="ellipsis")
        result.append("● ", style=GREEN)
        result.append(f"signed in as @{user.login}", style=CREAM)
        if user.name:
            result.append(f" ({user.name})", style=MUTED)
        result.append(f"  ·  saved to {_short_path(TOKEN_FILE)}", style=FAINT)
        status.update(result)
        self._set_card("-ok")

        self.query_one(Input).value = ""
        self.app.notify(
            self._unlocked(scopes), title=f"Welcome, @{user.login}", timeout=6
        )
        self.app.start_sync(force=True)

        self.set_timer(0.9, self._continue)

    def _continue(self) -> None:
        if getattr(self.app, "authenticated", False):
            self.dismiss()
            self.app.open_dashboard()

    def _unlocked(self, scopes: list[str]) -> str:
        if not scopes:
            return (
                "Fine-grained token accepted. Stars and notifications stay empty — "
                "GitHub does not offer them to this token type."
            )
        missing = []
        if not any(s == "repo" or s.startswith("repo:") for s in scopes):
            missing.append("private repositories")
        if "read:org" not in scopes and "admin:org" not in scopes:
            missing.append("organisation repositories")
        if "notifications" not in scopes and "repo" not in scopes:
            missing.append("notifications")
        if not missing:
            return "Everything unlocked — syncing now."
        return "Syncing now. Not available with this token: " + ", ".join(missing) + "."

    def _fail(self, message: str) -> None:
        text = Text(no_wrap=True, overflow="ellipsis")
        text.append("● ", style=RED)
        text.append(message, style=CREAM)
        self.query_one("#login-status", Static).update(text)
        self._set_card("-bad")


    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        token = event.value.strip()
        if not token:
            self._fail("Paste a token first, or press ctrl+o to create one.")
            return
        self.validate(token)

    def on_key(self, event: events.Key) -> None:
        key = event.key

        if key == "escape":
            self.dismiss()
        elif key == "ctrl+o":
            self._open_token_page()
        elif key == "ctrl+r":
            field = self.query_one(Input)
            field.password = not field.password
        elif key == "ctrl+d":
            clear_token()
            self.app.adopt_token(None)
            self.refresh_status()
            self._set_card(None)
            self.app.notify("Signed out — the stored token was deleted.", severity="warning")
        else:
            return

        event.stop()
        event.prevent_default()

    def _open_token_page(self) -> None:
        try:
            webbrowser.open(PAT_URL)
            self.app.notify("Opened the GitHub token page in your browser.")
        except Exception:
            self.app.notify(f"Open this yourself: {PAT_URL}", severity="warning", timeout=12)
