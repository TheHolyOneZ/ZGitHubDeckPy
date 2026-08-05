# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Any

from rich.console import Group, RenderableType
from rich.text import Text
from textual import events, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from ...export import report as report_builders
from ...export.writer import EXPORT_DIR, FORMATS, suggested_path, write
from ...utils.formatters import keyhint, truncate
from ..theme import CORAL, CREAM, FAINT, GREEN, LINE, MARK, MUTED, RED

TAB_LABELS = {
    "issues": "open issues",
    "pulls": "open pull requests",
    "stars": "recent stargazers",
    "activity": "activity and notifications",
    "code": "code written",
}


class ExportScreen(ModalScreen):

    def __init__(self, tab: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.tab = tab if tab in TAB_LABELS else "issues"
        self.index = 0
        self.format_index = 0
        self.filtered = True
        self.open_after = False
        self.written: Path | None = None
        self.busy = False


    def compose(self) -> ComposeResult:
        with Vertical(id="export-card"):
            yield Static(id="export-body")
            yield Static(id="modal-hint")

    def on_mount(self) -> None:
        card = self.query_one("#export-card")
        card.border_title = f"[{CORAL}]{MARK}[/] export"
        card.border_subtitle = "writes a file, nothing leaves your machine"
        self._set_hint()
        self.redraw()

    def _set_hint(self) -> None:
        keys = [("↑↓", "row"), ("←→", "change"), ("enter", "export")]
        if self.written:
            keys.append(("o", "open"))
        keys.append(("esc", "close"))
        self.query_one("#modal-hint", Static).update(keyhint(keys))


    @property
    def rows(self) -> list[tuple[str, str, str]]:
        shown, total = self._counts()
        scope = (
            f"what the filter shows — {shown:,} rows"
            if self.filtered
            else f"everything in this tab — {total:,} rows"
        )
        fmt = FORMATS[self.format_index]
        return [
            ("source", "what", TAB_LABELS[self.tab]),
            ("scope", "rows", scope),
            ("format", "format", f"{fmt.label} ({fmt.suffix})"),
            ("open", "open when done", "yes" if self.open_after else "no"),
        ]

    def cycle(self, key: str, step: int) -> None:
        if key == "source":
            tabs = list(TAB_LABELS)
            self.tab = tabs[(tabs.index(self.tab) + step) % len(tabs)]
        elif key == "scope":
            self.filtered = not self.filtered
        elif key == "format":
            self.format_index = (self.format_index + step) % len(FORMATS)
        elif key == "open":
            self.open_after = not self.open_after
        self.written = None
        self._set_hint()
        self.redraw()


    def _panel(self):
        dashboard = getattr(self.app, "dashboard", None)
        if dashboard is None:
            return None
        return dashboard.panels.get(self.tab)

    def _counts(self) -> tuple[int, int]:
        panel = self._panel()
        if panel is None:
            return 0, 0
        view = panel.view
        return len(getattr(view, "visible_records", [])), len(getattr(view, "records", []))

    def _records(self) -> tuple[list[Any], str]:
        panel = self._panel()
        if panel is None:
            return [], ""
        view = panel.view
        if self.filtered:
            return list(getattr(view, "visible_records", [])), panel.bar.value.strip()
        return list(getattr(view, "records", [])), ""

    def _build_report(self):
        store = self.app.store
        owner = store.viewer.login if store.viewer else ""
        records, filter_text = self._records()

        if self.tab == "issues":
            return report_builders.issues_report(records, owner, filter_text)
        if self.tab == "pulls":
            return report_builders.pulls_report(records, owner, filter_text)
        if self.tab == "stars":
            return report_builders.stars_report(records, owner, filter_text)
        if self.tab == "code":
            return report_builders.code_report(records, store.code, owner, filter_text)

        notifications = list(store.notifications)
        if self.filtered:
            panel = self._panel()
            feed = panel.view if panel else None
            notifications = list(getattr(feed, "notifications", notifications))
        return report_builders.activity_report(records, notifications, owner, filter_text)


    def redraw(self) -> None:
        blocks: list[RenderableType] = [Text("")]

        for position, (_, label, value) in enumerate(self.rows):
            selected = position == self.index
            line = Text(no_wrap=True, overflow="ellipsis")
            line.append("  ▸ " if selected else "    ", style=CORAL)
            line.append(f"{label:<16}", style=f"bold {CREAM}" if selected else CREAM)
            line.append(
                f"‹ {value} ›" if selected else f"  {value}",
                style=f"bold {CORAL}" if selected else MUTED,
            )
            blocks.append(line)

        blocks.append(Text(""))
        blocks.append(self._destination())
        blocks.append(Text(""))
        blocks.append(self._status())

        self.query_one("#export-body", Static).update(Group(*blocks))

    def _destination(self) -> Text:
        fmt = FORMATS[self.format_index]
        text = Text(no_wrap=True, overflow="ellipsis")
        text.append("    → ", style=FAINT)
        try:
            path = suggested_path(self._build_report(), fmt.key)
            shown = str(path)
            home = str(Path.home())
            if shown.startswith(home):
                shown = "~" + shown[len(home):]
            text.append(shown, style=CREAM)
        except Exception:
            text.append(str(EXPORT_DIR), style=CREAM)
        return text

    def _status(self) -> Text:
        text = Text(no_wrap=True, overflow="ellipsis")

        if self.busy:
            text.append("    ◐ ", style=CORAL)
            text.append("writing…", style=CREAM)
            return text

        if self.written:
            text.append("    ● ", style=GREEN)
            text.append("written  ", style=CREAM)
            size = self.written.stat().st_size if self.written.exists() else 0
            readable = f"{size / 1024:.0f} KB" if size >= 1024 else f"{size} B"
            text.append(f"{readable}", style=MUTED)
            text.append("   ·   ", style=LINE)
            text.append("press o to open it", style=FAINT)
            return text

        shown, _ = self._counts()
        if shown == 0:
            text.append("    · ", style=RED)
            text.append(
                "this view is empty — the export will record that", style=MUTED
            )
            return text

        text.append("    ", style=FAINT)
        text.append(FORMATS[self.format_index].blurb, style=FAINT)
        return text


    @work(exclusive=True, thread=True, group="export")
    def perform_export(self) -> None:
        fmt = FORMATS[self.format_index]
        try:
            report = self._build_report()
            path = write(report, fmt.key)
        except OSError as error:
            self.app.call_from_thread(self._failed, f"could not write the file — {error}")
            return
        except Exception as error:
            self.app.call_from_thread(self._failed, str(error))
            return
        self.app.call_from_thread(self._succeeded, path, report.row_count)

    def _succeeded(self, path: Path, rows: int) -> None:
        self.busy = False
        self.written = path
        self._set_hint()
        self.redraw()
        self.app.notify(
            f"{rows:,} rows → {truncate(str(path), 70)}", title="Exported", timeout=8
        )
        if self.open_after:
            self._open()

    def _failed(self, message: str) -> None:
        self.busy = False
        self.written = None
        self.redraw()
        self.app.notify(message, title="Export failed", severity="error")

    def _open(self) -> None:
        if not self.written:
            return
        try:
            webbrowser.open(self.written.as_uri())
        except Exception:
            self.app.notify(f"Saved at {self.written}", timeout=10)


    def on_key(self, event: events.Key) -> None:
        key = event.key
        letter = (event.character or "").lower()
        rows = self.rows

        if key in ("up", "k", "shift+tab"):
            self.index = (self.index - 1) % len(rows)
            self.redraw()
        elif key in ("down", "j", "tab"):
            self.index = (self.index + 1) % len(rows)
            self.redraw()
        elif key in ("left", "h"):
            self.cycle(rows[self.index][0], -1)
        elif key in ("right", "l"):
            self.cycle(rows[self.index][0], 1)
        elif key == "enter":
            self.busy = True
            self.written = None
            self.redraw()
            self.perform_export()
        elif letter == "o" and self.written:
            self._open()
        elif key in ("escape", "backspace") or letter == "q":
            self.dismiss()
        else:
            return

        event.stop()
        event.prevent_default()
