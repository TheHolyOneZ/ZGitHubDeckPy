# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import html as html_renderer
from . import markdown as md_renderer
from .report import Report

EXPORT_DIR = Path.home() / "zdeck-exports"


@dataclass(frozen=True)
class Format:
    key: str
    label: str
    suffix: str
    blurb: str


FORMATS: tuple[Format, ...] = (
    Format("markdown", "Markdown", ".md", "tables and links — drops into a README or issue"),
    Format("html", "HTML page", ".html", "self-contained, searchable, sortable, GitHub Pages ready"),
    Format("csv", "CSV", ".csv", "one file per section, for spreadsheets"),
    Format("json", "JSON", ".json", "the raw rows, for scripting"),
)


def format_for(key: str) -> Format:
    for fmt in FORMATS:
        if fmt.key == key:
            return fmt
    return FORMATS[0]


def render_csv(report: Report) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    for index, section in enumerate(report.sections):
        if index:
            writer.writerow([])
        writer.writerow([f"# {section.title}"])
        writer.writerow([column.label for column in section.columns])
        for row in section.rows:
            writer.writerow([cell.plain for cell in row])
    return buffer.getvalue()


def render_json(report: Report) -> str:
    payload = {
        "title": report.title,
        "subtitle": report.subtitle,
        "owner": report.owner,
        "generated_at": report.generated_at.isoformat(),
        "filter": report.filter_text,
        "summary": {label: value for label, value in report.stats},
        "sections": [
            {
                "title": section.title,
                "columns": [column.label for column in section.columns],
                "rows": [
                    {
                        column.key: (cell.href or cell.plain)
                        if column.key in ("number",) and cell.href
                        else cell.plain
                        for column, cell in zip(section.columns, row)
                    }
                    for row in section.rows
                ],
            }
            for section in report.sections
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


RENDERERS = {
    "markdown": md_renderer.render,
    "html": html_renderer.render,
    "csv": render_csv,
    "json": render_json,
}


def suggested_path(report: Report, format_key: str, directory: Path | None = None) -> Path:
    fmt = format_for(format_key)
    stamp = datetime.now().strftime("%Y-%m-%d")
    base = (directory or EXPORT_DIR) / f"zdeck-{report.slug}-{stamp}{fmt.suffix}"
    return base


def unique(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 100):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    return path


def write(report: Report, format_key: str, path: Path | None = None) -> Path:
    renderer = RENDERERS.get(format_key, md_renderer.render)
    target = unique(path or suggested_path(report, format_key))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(renderer(report), encoding="utf-8")
    return target
