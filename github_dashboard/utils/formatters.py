# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

from datetime import datetime, timezone

from rich.text import Text

from ..models.data_types import CheckSummary, Label
from ..ui.theme import (
    BLUE,
    CREAM,
    FAINT,
    GREEN,
    LINE,
    MUTED,
    PURPLE,
    RED,
    CORAL,
    YELLOW,
)


_UNITS = (
    (60, "s"),
    (3600, "m"),
    (86400, "h"),
    (86400 * 7, "d"),
    (86400 * 30, "w"),
    (86400 * 365, "mo"),
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def time_ago(moment: datetime | None, style: str = "relative") -> str:
    if moment is None:
        return "—"
    if style == "absolute":
        return moment.astimezone().strftime("%Y-%m-%d")

    seconds = (now() - moment).total_seconds()
    if seconds < 0:
        return "soon"
    if seconds < 45:
        return "now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h"
    if seconds < 86400 * 30:
        return f"{int(seconds // 86400)}d"
    if seconds < 86400 * 365:
        return f"{int(seconds // (86400 * 30))}mo"
    return f"{seconds / (86400 * 365):.1f}y"


def age_style(moment: datetime | None) -> str:
    if moment is None:
        return FAINT
    days = (now() - moment).total_seconds() / 86400
    if days < 2:
        return GREEN
    if days < 14:
        return MUTED
    if days < 90:
        return YELLOW
    return RED


def aged(moment: datetime | None, style: str = "relative", justify: str = "right") -> Text:
    return Text(
        time_ago(moment, style),
        style=age_style(moment),
        no_wrap=True,
        justify=justify,
    )


def stamp(moment: datetime | None) -> str:
    if moment is None:
        return "unknown"
    return moment.astimezone().strftime("%d %b %Y at %H:%M")


def countdown(moment: datetime | None) -> str:
    if moment is None:
        return "—"
    seconds = (moment - now()).total_seconds()
    if seconds <= 0:
        return "now"
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    return f"{seconds / 3600:.1f}h"


def truncate(value: str, width: int, ellipsis: str = "…") -> str:
    flat = " ".join(str(value).split())
    if width <= 0 or len(flat) <= width:
        return flat
    return flat[: max(width - len(ellipsis), 0)].rstrip() + ellipsis


def shorten_repo(full_name: str, width: int = 28) -> str:
    if len(full_name) <= width:
        return full_name
    _, _, name = full_name.partition("/")
    return truncate(name or full_name, width)


def compact_number(value: int) -> str:
    if value < 1000:
        return str(value)
    if value < 1_000_000:
        text = f"{value / 1000:.1f}k"
        return text.replace(".0k", "k")
    return f"{value / 1_000_000:.1f}M".replace(".0M", "M")


def plural(count: int, singular: str, suffix: str = "s") -> str:
    return f"{count} {singular}{'' if count == 1 else suffix}"


def first_paragraph(body: str, limit: int = 220) -> str:
    for block in (body or "").split("\n\n"):
        text = " ".join(block.split())
        if text:
            return truncate(text, limit)
    return ""


def _luminance(hex_colour: str) -> float:
    value = (hex_colour or "").lstrip("#")
    if len(value) == 3:
        value = "".join(char * 2 for char in value)
    if len(value) != 6:
        return 0.5
    try:
        red, green, blue = (int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return 0.5
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def readable_on(hex_colour: str) -> str:
    return "#111111" if _luminance(hex_colour) > 0.55 else "#f4f1ec"


def render_labels(labels: list[Label], width: int = 30, max_labels: int = 4) -> Text:
    text = Text(no_wrap=True, overflow="ellipsis")
    if not labels:
        return Text("—", style=FAINT)

    used = 0
    shown = 0
    for label in labels[:max_labels]:
        chip = truncate(label.name, 18)
        cost = len(chip) + 2 + (1 if shown else 0)
        if shown and used + cost > width:
            break
        if shown:
            text.append(" ")
        colour = f"#{label.color}"
        text.append(f" {chip} ", style=f"{readable_on(label.color)} on {colour}")
        used += cost
        shown += 1

    remaining = len(labels) - shown
    if remaining > 0:
        text.append(f" +{remaining}", style=FAINT)
    return text


def label_chips(labels: list[Label]) -> Text:
    text = Text()
    for index, label in enumerate(labels):
        if index:
            text.append(" ")
        text.append(f" {label.name} ", style=f"{readable_on(label.color)} on #{label.color}")
    return text


_CHECK_STYLES = {
    "success": (GREEN, "●"),
    "failure": (RED, "●"),
    "pending": (YELLOW, "◐"),
    "neutral": (MUTED, "○"),
    "unknown": (FAINT, "·"),
}


def check_badge(checks: CheckSummary) -> Text:
    colour, glyph = _CHECK_STYLES.get(checks.state, _CHECK_STYLES["unknown"])
    text = Text(no_wrap=True)
    text.append(f"{glyph} ", style=colour)
    text.append(checks.describe(), style=MUTED if checks.known else FAINT)
    return text


_MERGE_STYLES = {
    "ready": (GREEN, "✓"),
    "conflicts": (RED, "✗"),
    "blocked": (RED, "⊘"),
    "behind": (YELLOW, "↓"),
    "unstable": (YELLOW, "!"),
    "draft": (FAINT, "◌"),
    "—": (FAINT, "·"),
}


def merge_badge(verdict: str) -> Text:
    colour, glyph = _MERGE_STYLES.get(verdict, (MUTED, "·"))
    text = Text(no_wrap=True)
    text.append(f"{glyph} ", style=colour)
    text.append(verdict, style=colour if verdict != "—" else FAINT)
    return text


def review_badge(state: str) -> Text:
    if state == "draft":
        return Text("draft", style=FAINT, no_wrap=True)
    if state == "none":
        return Text("—", style=FAINT, no_wrap=True)
    return Text(state, style=CORAL, no_wrap=True)


_EVENT_STYLES = {
    "push": GREEN,
    "star": YELLOW,
    "fork": BLUE,
    "pr": PURPLE,
    "issue": CORAL,
    "review": PURPLE,
    "comment": MUTED,
    "release": YELLOW,
    "create": GREEN,
    "delete": RED,
}


def event_badge(kind: str) -> Text:
    return Text(kind, style=_EVENT_STYLES.get(kind, MUTED), no_wrap=True)


LANGUAGE_COLOURS = {
    "Python": "#3572A5", "TypeScript": "#3178c6", "JavaScript": "#f1e05a",
    "Rust": "#dea584", "Go": "#00ADD8", "Java": "#b07219", "C": "#555555",
    "C++": "#f34b7d", "C#": "#178600", "Ruby": "#701516", "PHP": "#4F5D95",
    "Swift": "#F05138", "Kotlin": "#A97BFF", "Dart": "#00B4AB", "Lua": "#000080",
    "Shell": "#89e051", "PowerShell": "#012456", "HTML": "#e34c26",
    "CSS": "#563d7c", "SCSS": "#c6538c", "Vue": "#41b883", "Svelte": "#ff3e00",
    "GDScript": "#355570", "Batchfile": "#C1F12E", "Makefile": "#427819",
    "Dockerfile": "#384d54", "SQL": "#e38c00", "Markdown": "#083fa1",
    "Assembly": "#6E4C13", "Perl": "#0298c3", "R": "#198CE7", "Scala": "#c22d40",
}
_FALLBACK_COLOURS = ["#8fbf7a", "#b48ead", "#7fa8c9", "#d9a441", "#e06c75", "#d97757"]


def language_style(language: str) -> str:
    if not language:
        return MUTED
    if language in LANGUAGE_COLOURS:
        return LANGUAGE_COLOURS[language]
    return _FALLBACK_COLOURS[sum(map(ord, language)) % len(_FALLBACK_COLOURS)]


def author_text(login: str, highlight: str = "") -> Text:
    if login and login == highlight:
        return Text(login, style=f"bold {CORAL}", no_wrap=True)
    return Text(login or "ghost", style=MUTED, no_wrap=True)


def meter(fraction: float, width: int = 12, colour: str = CORAL) -> Text:
    fraction = max(0.0, min(1.0, fraction))
    filled = round(width * fraction)
    bar = Text(no_wrap=True)
    bar.append("━" * filled, style=colour)
    bar.append("━" * (width - filled), style=LINE)
    return bar


def rate_colour(fraction: float) -> str:
    if fraction > 0.5:
        return GREEN
    if fraction > 0.2:
        return YELLOW
    return RED


def keyhint(pairs: list[tuple[str, str]], separator: str = "  ·  ") -> Text:
    text = Text(no_wrap=True)
    for key, caption in pairs:
        if text.plain:
            text.append(separator, style=LINE)
        text.append(key, style=CORAL)
        text.append(f" {caption}", style=FAINT)
    return text


def field_row(label: str, value: str, label_width: int = 12) -> Text:
    text = Text(no_wrap=True)
    text.append(f"{label:>{label_width}}  ", style=FAINT)
    text.append(value, style=CREAM)
    return text
