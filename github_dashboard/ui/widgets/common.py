# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

from rich.console import RenderableType
from rich.text import Text
from textual import events
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget

from ...config.settings import APP_NAME, BRAND, Preference
from ..theme import (
    CORAL,
    CREAM,
    FAINT,
    LINE,
    LOGO,
    LOGO_SHADES,
    LOGO_SHADOW,
    LOGO_WIDTH,
    MARK,
    MUTED,
)


class Logo(Widget):

    def render(self) -> RenderableType:
        if self.size.width < LOGO_WIDTH + 2:
            small = Text(justify="center")
            small.append(f"{MARK} ", style=f"bold {CORAL}")
            small.append(APP_NAME, style=f"bold {CREAM}")
            return small

        art = Text(no_wrap=True, overflow="crop")
        for index, line in enumerate(LOGO):
            shade = LOGO_SHADES[index % len(LOGO_SHADES)]
            for char in line.ljust(LOGO_WIDTH):
                art.append(char, style=shade if char == "█" else LOGO_SHADOW)
            if index < len(LOGO) - 1:
                art.append("\n")
        return art


class MenuHover(Message):
    def __init__(self, key: str) -> None:
        super().__init__()
        self.key = key


class MenuChosen(Message):
    def __init__(self, key: str) -> None:
        super().__init__()
        self.key = key


class MenuOption(Widget):

    selected: reactive[bool] = reactive(False)
    enabled: reactive[bool] = reactive(True)

    def __init__(self, key: str, label: str, blurb: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.key = key
        self.label = label
        self.blurb = blurb

    def watch_selected(self, selected: bool) -> None:
        self.set_class(selected, "-selected")

    def watch_enabled(self, enabled: bool) -> None:
        self.set_class(not enabled, "-disabled")

    def render(self) -> RenderableType:
        row = Text(no_wrap=True, overflow="crop")
        row.append("  ▸ " if self.selected else "    ", style=CORAL)

        if not self.enabled:
            label_style = FAINT
        elif self.selected:
            label_style = f"bold {CREAM}"
        else:
            label_style = CREAM
        row.append(self.label, style=label_style)

        pad = self.size.width - len(self.label) - len(self.blurb) - 8
        row.append(" " * max(pad, 2))
        row.append(self.blurb, style=FAINT if not self.enabled or not self.selected else MUTED)
        row.append("  ")
        return row

    def on_enter(self, event: events.Enter) -> None:
        self.post_message(MenuHover(self.key))

    def on_click(self, event: events.Click) -> None:
        if self.enabled:
            self.post_message(MenuChosen(self.key))


class RowHover(Message):
    def __init__(self, key: str) -> None:
        super().__init__()
        self.key = key


class RowCycle(Message):
    def __init__(self, key: str, step: int) -> None:
        super().__init__()
        self.key = key
        self.step = step


class ChoiceRow(Widget):

    selected: reactive[bool] = reactive(False)

    def __init__(self, preference: Preference, **kwargs) -> None:
        super().__init__(**kwargs)
        self.preference = preference
        self.value_label = ""

    def watch_selected(self, selected: bool) -> None:
        self.set_class(selected, "-selected")

    def render(self) -> RenderableType:
        row = Text(no_wrap=True, overflow="crop")
        row.append("  ▸ " if self.selected else "    ", style=CORAL)
        row.append(
            self.preference.label,
            style=f"bold {CREAM}" if self.selected else CREAM,
        )

        value = f"‹ {self.value_label} ›" if self.selected else f"  {self.value_label}  "
        pad = self.size.width - len(self.preference.label) - len(value) - 6
        row.append(" " * max(pad, 2))
        row.append(value, style=f"bold {CORAL}" if self.selected else MUTED)
        row.append("  ")
        return row

    def on_enter(self, event: events.Enter) -> None:
        self.post_message(RowHover(self.preference.key))

    def on_click(self, event: events.Click) -> None:
        self.post_message(RowCycle(self.preference.key, 1))


def brand_line(right_text: str = "") -> tuple[Text, Text]:
    left = Text(no_wrap=True)
    left.append(f"{MARK} ", style=f"bold {CORAL}")
    left.append(APP_NAME.lower(), style=f"bold {CREAM}")
    left.append("  ·  ", style=LINE)
    left.append(f"by {BRAND}", style=MUTED)

    right = Text(right_text, style=FAINT, justify="right", no_wrap=True)
    return left, right
