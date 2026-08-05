# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text
from textual.widget import Widget

from ...models.data_types import CodeStats
from ...utils.formatters import compact_number, language_style, time_ago
from ..theme import CORAL, CREAM, FAINT, GREEN, LINE, MUTED, RED


class CodeSummary(Widget):

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.stats = CodeStats()
        self.scanning = False

    def update_stats(self, stats: CodeStats) -> None:
        self.stats = stats
        self.refresh()

    def set_scanning(self, scanning: bool) -> None:
        self.scanning = scanning
        self.refresh()


    def render(self) -> RenderableType:
        stats = self.stats
        if not stats.repos:
            hint = Text(no_wrap=True)
            if self.scanning:
                hint.append("  measuring every repository…", style=CORAL)
            else:
                hint.append("  press ", style=FAINT)
                hint.append("c", style=CORAL)
                hint.append(
                    "  to measure every line of code you have ever written",
                    style=FAINT,
                )
            return Group(Text(""), hint)

        return Group(self._headline(), Text(""), self._languages())

    def _headline(self) -> Table:
        stats = self.stats
        grid = Table.grid(expand=True, padding=(0, 2))
        for _ in range(6):
            grid.add_column(justify="left", ratio=1)

        def cell(value: str, label: str, style: str = CORAL) -> Text:
            text = Text(no_wrap=True)
            text.append(value, style=f"bold {style}")
            text.append(f"\n{label}", style=MUTED)
            return text

        grid.add_row(
            cell(f"{stats.additions:,}", "lines ever written"),
            cell(f"{stats.net:,}", "net lines", GREEN),
            cell(f"{stats.deletions:,}", "lines removed", RED),
            cell(f"{stats.commits:,}", "commits", CREAM),
            cell(f"{stats.repos_touched}", "repos contributed to", CREAM),
            cell(
                f"{compact_number(stats.standing_lines)}",
                "lines standing today",
                CREAM,
            ),
        )
        return grid

    def _languages(self) -> Group:
        stats = self.stats
        languages = stats.languages()
        if not languages:
            return Group(Text(""))

        total = sum(size for _, size in languages) or 1
        width = max(self.size.width - 4, 20)

        bar = Text(no_wrap=True, overflow="crop")
        used = 0
        for language, size in languages[:8]:
            share = size / total
            cells = int(round(share * width))
            if cells <= 0:
                continue
            bar.append("█" * cells, style=language_style(language))
            used += cells
        if used < width:
            bar.append("█" * (width - used), style=LINE)

        legend = Text(no_wrap=True, overflow="ellipsis")
        for index, (language, size) in enumerate(languages[:6]):
            if index:
                legend.append("   ", style=LINE)
            legend.append("● ", style=language_style(language))
            legend.append(language, style=CREAM)
            legend.append(f" {size / total * 100:.0f}%", style=FAINT)

        footer = Text(no_wrap=True, overflow="ellipsis")
        if stats.scanned_at:
            footer.append(f"scanned {time_ago(stats.scanned_at)} ago", style=FAINT)
        if stats.incomplete:
            footer.append("   ", style=LINE)
            footer.append(
                f"{len(stats.incomplete)} repos still being computed by GitHub — "
                "press c again shortly",
                style=MUTED,
            )
        footer.append("   ", style=LINE)
        footer.append(
            "'lines now' is estimated from language byte counts; "
            "'you added' is exact",
            style=FAINT,
        )

        return Group(bar, legend, footer)
