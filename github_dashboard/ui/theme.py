# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

CORAL = "#d97757"
CREAM = "#e6e0d6"
MUTED = "#7a736a"
FAINT = "#4a4540"
LINE = "#2e2b28"

PAPER = "#161513"
PANEL = "#1b1a18"
SELECT = "#26241f"
SUNKEN = "#141311"

GREEN = "#8fbf7a"
RED = "#e06c75"
YELLOW = "#d9a441"
PURPLE = "#b48ead"
BLUE = "#7fa8c9"

CORAL_DIM = "#8a4c37"
CORAL_BRIGHT = "#f0a07a"

LOGO_SHADES = ["#f0a07a", "#e8895f", "#e07f57", "#d97757", "#c66a4c", "#b25c42"]
LOGO_SHADOW = "#5c3427"

MARK = "✻"

LOGO = r"""
███████╗ ██████╗  ███████╗  ██████╗ ██╗  ██╗
╚══███╔╝ ██╔══██╗ ██╔════╝ ██╔════╝ ██║ ██╔╝
  ███╔╝  ██║  ██║ █████╗   ██║      █████╔╝
 ███╔╝   ██║  ██║ ██╔══╝   ██║      ██╔═██╗
███████╗ ██████╔╝ ███████╗ ╚██████╗ ██║  ██╗
╚══════╝ ╚═════╝  ╚══════╝  ╚═════╝ ╚═╝  ╚═╝
""".strip("\n").split("\n")

LOGO_WIDTH = max(len(line) for line in LOGO)
LOGO_HEIGHT = len(LOGO)

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

APP_CSS = f"""

Screen {{
    background: {PAPER};
    color: {CREAM};
}}

Screen.-centered {{
    align: center middle;
}}

#shell {{
    width: 100%;
    max-width: 96;
    height: auto;
    padding: 0 2;
}}

#topbar {{
    height: 1;
    margin-bottom: 1;
}}
#brand {{ width: 1fr; }}
#brand-right {{ width: auto; }}

#hint {{
    height: 1;
    margin-top: 1;
    text-align: center;
}}

Tooltip {{
    background: {PANEL};
    color: {CREAM};
    border: round {LINE};
    padding: 0 1;
}}

Toast {{
    background: {PANEL};
    border: round {CORAL};
    color: {CREAM};
}}
Toast.-error {{ border: round {RED}; }}
Toast.-warning {{ border: round {YELLOW}; }}
ToastRack {{ align: right bottom; }}

LoadingIndicator {{
    background: {PAPER};
    color: {CORAL};
}}

#logo {{
    height: {LOGO_HEIGHT};
    margin-bottom: 1;
    text-align: center;
}}

#tagline {{
    height: 1;
    margin-bottom: 1;
    text-align: center;
}}

#menu {{
    height: auto;
    margin: 0 0 1 0;
}}

MenuOption {{
    height: 1;
    width: 100%;
}}

MenuOption.-selected {{
    background: {SELECT};
}}

MenuOption.-disabled {{
    color: {FAINT};
}}

#account-line, #cache-line {{
    height: 1;
    text-align: center;
}}

#options {{
    height: auto;
    background: {PANEL};
    border: round {LINE};
    border-title-color: {CREAM};
    border-title-align: left;
    padding: 1 1;
}}

ChoiceRow {{
    height: 1;
    width: 100%;
}}

ChoiceRow.-selected {{
    background: {SELECT};
}}

#help-line {{
    height: 1;
    margin-top: 1;
    text-align: center;
}}

#login-card {{
    height: auto;
    background: {PANEL};
    border: round {LINE};
    border-title-color: {CREAM};
    border-title-align: left;
    border-subtitle-color: {MUTED};
    border-subtitle-align: right;
    padding: 1 2;
}}

#login-card.-ok {{ border: round {GREEN}; }}
#login-card.-bad {{ border: round {RED}; }}
#login-card.-busy {{ border: round {CORAL}; }}

#login-intro {{
    height: 1;
}}

#token-input {{
    background: {SUNKEN};
    border: round {LINE};
    color: {CREAM};
    padding: 0 1;
    height: 3;
}}

#token-input:focus {{
    border: round {CORAL};
}}

#token-input > .input--placeholder {{ color: {FAINT}; }}
#token-input > .input--cursor {{ background: {CORAL}; color: {PAPER}; }}
#token-input > .input--selection {{ background: {SELECT}; }}

#login-status {{
    height: 1;
    margin-top: 1;
}}

#login-perms {{
    height: auto;
}}

#dash {{
    width: 100%;
    height: 100%;
    padding: 0 1;
}}

HeaderBar {{
    height: 4;
    width: 100%;
    padding: 0 1;
    background: {PANEL};
    border-bottom: hkey {LINE};
}}

#tabs {{
    height: 1fr;
}}

TabbedContent > ContentSwitcher {{
    height: 1fr;
    background: {PAPER};
}}

TabPane {{
    padding: 0;
    height: 1fr;
}}

Tabs {{
    height: 2;
    background: {PAPER};
}}

Tabs:focus .-active {{
    text-style: bold;
}}

Tab {{
    color: {MUTED};
    padding: 0 2;
}}

Tab.-active {{
    color: {CORAL};
    text-style: bold;
}}

Tab:hover {{
    color: {CREAM};
}}

Underline > .underline--bar {{
    color: {CORAL};
    background: {LINE};
}}

FilterBar {{
    height: 3;
    width: 100%;
}}

FilterBar .filter-input {{
    width: 1fr;
    background: {SUNKEN};
    border: round {LINE};
    color: {CREAM};
    height: 3;
    padding: 0 1;
}}

FilterBar .filter-input:focus {{
    border: round {CORAL};
}}

FilterBar .filter-input > .input--placeholder {{ color: {FAINT}; }}
FilterBar .filter-input > .input--cursor {{ background: {CORAL}; color: {PAPER}; }}
FilterBar .filter-input > .input--selection {{ background: {SELECT}; }}

FilterBar .filter-summary {{
    width: 20;
    height: 3;
    padding: 1 1 0 1;
    text-align: right;
}}

DataTable {{
    height: 1fr;
    width: 100%;
    background: {SUNKEN};
    border: round {LINE};
    scrollbar-size-vertical: 1;
    scrollbar-background: {SUNKEN};
    scrollbar-color: {LINE};
    scrollbar-color-hover: {CORAL_DIM};
    scrollbar-color-active: {CORAL};
}}

DataTable:focus {{
    border: round {CORAL_DIM};
}}

DataTable > .datatable--header {{
    background: {PANEL};
    color: {MUTED};
    text-style: none;
}}

DataTable > .datatable--header-hover {{
    background: {SELECT};
    color: {CREAM};
}}

DataTable > .datatable--cursor {{
    background: {SELECT};
    color: {CREAM};
    text-style: none;
}}

DataTable > .datatable--hover {{
    background: {PANEL};
}}

DataTable > .datatable--odd-row {{
    background: {SUNKEN};
}}

DataTable > .datatable--even-row {{
    background: {SUNKEN};
}}

StreamFeed {{
    height: 1fr;
    width: 100%;
    background: {SUNKEN};
    border: round {LINE};
    padding: 0 1;
    scrollbar-size-vertical: 1;
    scrollbar-background: {SUNKEN};
    scrollbar-color: {LINE};
    scrollbar-color-hover: {CORAL_DIM};
    scrollbar-color-active: {CORAL};
}}

StreamFeed:focus {{
    border: round {CORAL_DIM};
}}

StreamFeed > #feed-body {{
    width: 100%;
    height: auto;
}}

.tab-body {{
    height: 1fr;
    width: 100%;
}}

CodeSummary {{
    height: 6;
    width: 100%;
    padding: 0 1;
    background: {PANEL};
    border-bottom: hkey {LINE};
}}

AboutPanel {{
    height: 1fr;
    width: 100%;
    padding: 1 1;
    background: {SUNKEN};
    border: round {LINE};
}}

AboutPanel:focus {{
    border: round {CORAL_DIM};
}}

#statusline {{
    height: 1;
    width: 100%;
    padding: 0 1;
}}

#dash-hint {{
    height: 1;
    width: 100%;
    padding: 0 1;
    text-align: center;
}}

ModalScreen {{
    align: center middle;
    background: {PAPER} 70%;
}}

#modal-card {{
    width: 100%;
    max-width: 108;
    height: 100%;
    max-height: 90%;
    background: {PANEL};
    border: round {CORAL};
    border-title-color: {CREAM};
    border-title-align: left;
    border-subtitle-color: {MUTED};
    border-subtitle-align: right;
    padding: 1 2;
}}

#modal-body {{
    height: 1fr;
    scrollbar-size-vertical: 1;
    scrollbar-background: {PANEL};
    scrollbar-color: {LINE};
    scrollbar-color-hover: {CORAL_DIM};
    scrollbar-color-active: {CORAL};
}}

#modal-hint {{
    height: 1;
    margin-top: 1;
    text-align: center;
}}

#export-card {{
    width: 84;
    max-width: 94%;
    height: auto;
    background: {PANEL};
    border: round {CORAL};
    border-title-color: {CREAM};
    border-title-align: left;
    border-subtitle-color: {MUTED};
    border-subtitle-align: right;
    padding: 1 2;
}}

#export-body {{
    width: 1fr;
    height: auto;
}}

#help-card {{
    width: 124;
    max-width: 96%;
    height: auto;
    max-height: 92%;
    background: {PANEL};
    border: round {CORAL};
    border-title-color: {CREAM};
    border-title-align: left;
    border-subtitle-color: {MUTED};
    border-subtitle-align: right;
    padding: 1 2;
}}

#help-body {{
    width: 1fr;
    height: auto;
}}
"""
