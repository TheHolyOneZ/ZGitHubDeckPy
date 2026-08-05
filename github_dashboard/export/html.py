# ZDECK
# Copyright (C) 2026 TheHolyOneZ
# Licensed under the GNU General Public License v3.0 or later.
# See LICENSE, or <https://www.gnu.org/licenses/>.

from __future__ import annotations

from html import escape as _escape

from ..utils.formatters import readable_on
from .report import Cell, Report, Section

MARK = "✻"

CSS = """
:root {
  --paper:#ffffff; --panel:#f6f4f1; --line:#e4e0da; --ink:#1c1a18;
  --muted:#6b6559; --faint:#98918a; --accent:#c2603c; --accent-soft:#fbeee8;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper:#161513; --panel:#1b1a18; --line:#2e2b28; --ink:#e6e0d6;
    --muted:#7a736a; --faint:#4a4540; --accent:#d97757; --accent-soft:#26241f;
  }
}
* { box-sizing: border-box; }
body {
  margin:0; padding:2.5rem 1.25rem 4rem; background:var(--paper); color:var(--ink);
  font:15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, sans-serif;
}
.wrap { max-width: 1180px; margin: 0 auto; }
header { border-bottom:1px solid var(--line); padding-bottom:1.25rem; margin-bottom:1.75rem; }
.brand { font-family:var(--mono); font-size:.8rem; color:var(--muted); letter-spacing:.04em; }
.brand b { color:var(--accent); }
h1 { font-size:1.9rem; margin:.5rem 0 .35rem; font-weight:650; letter-spacing:-.01em; }
.sub { color:var(--muted); margin:0; }
.meta { color:var(--faint); font-size:.82rem; margin-top:.6rem; font-family:var(--mono); }
.filter-note {
  display:inline-block; margin-top:.6rem; padding:.2rem .55rem; border-radius:5px;
  background:var(--accent-soft); color:var(--accent); font-family:var(--mono); font-size:.8rem;
}
.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:.75rem; margin:0 0 2.25rem; }
.stat { background:var(--panel); border:1px solid var(--line); border-radius:9px; padding:.8rem .95rem; }
.stat dt { color:var(--muted); font-size:.72rem; text-transform:uppercase; letter-spacing:.07em; margin:0 0 .3rem; }
.stat dd { margin:0; font-size:1.3rem; font-weight:650; font-variant-numeric:tabular-nums; }
.stat dd.long { font-size:.92rem; font-weight:550; line-height:1.5; letter-spacing:0; }
h2 { font-size:1.15rem; margin:2.25rem 0 .4rem; font-weight:620; }
h2:first-of-type { margin-top:0; }
.note, .section-sub { color:var(--muted); font-size:.87rem; margin:.2rem 0 .9rem; }
.controls { display:flex; gap:.6rem; align-items:center; margin:.6rem 0 .8rem; flex-wrap:wrap; }
.controls input {
  flex:1 1 240px; min-width:0; padding:.5rem .7rem; border-radius:7px;
  border:1px solid var(--line); background:var(--panel); color:var(--ink); font-size:.9rem;
}
.controls input:focus { outline:none; border-color:var(--accent); }
.count { color:var(--faint); font-size:.82rem; font-family:var(--mono); }
.scroll { overflow-x:auto; border:1px solid var(--line); border-radius:9px; background:var(--panel); }
table { border-collapse:collapse; width:100%; font-size:.88rem; }
th, td { padding:.55rem .8rem; text-align:left; border-bottom:1px solid var(--line); white-space:nowrap; }
th {
  position:sticky; top:0; background:var(--panel); color:var(--muted); font-weight:550;
  font-size:.74rem; text-transform:uppercase; letter-spacing:.06em; cursor:pointer; user-select:none;
}
th:hover { color:var(--ink); }
th[data-dir]::after { content:" ▲"; color:var(--accent); }
th[data-dir="desc"]::after { content:" ▼"; }
td.right, th.right { text-align:right; font-variant-numeric:tabular-nums; }
td.title { white-space:normal; min-width:22rem; }
tbody tr:last-child td { border-bottom:none; }
tbody tr:hover { background:var(--accent-soft); }
a { color:inherit; text-decoration:none; border-bottom:1px solid transparent; }
a:hover { color:var(--accent); border-bottom-color:var(--accent); }
code, .mono { font-family:var(--mono); font-size:.85em; color:var(--muted); }
.muted { color:var(--muted); }
.chip {
  display:inline-block; padding:.05rem .45rem; border-radius:999px; font-size:.74rem;
  font-weight:550; margin:.08rem .15rem .08rem 0; white-space:nowrap;
}
.empty { color:var(--faint); padding:1rem; }
footer { margin-top:3rem; padding-top:1.1rem; border-top:1px solid var(--line); color:var(--faint); font-size:.8rem; }
footer a { color:var(--accent); }
"""

JS = """
document.querySelectorAll('[data-table]').forEach(function (root) {
  var table = root.querySelector('table');
  var body  = table.querySelector('tbody');
  var box   = root.querySelector('input');
  var count = root.querySelector('.count');
  var rows  = Array.prototype.slice.call(body.rows);
  var total = rows.length;

  function refresh(shown) {
    if (count) count.textContent = shown === total
      ? total.toLocaleString() + ' rows'
      : shown.toLocaleString() + ' of ' + total.toLocaleString();
  }
  refresh(total);

  if (box) box.addEventListener('input', function () {
    var q = box.value.toLowerCase().trim(), shown = 0;
    rows.forEach(function (row) {
      var hit = !q || row.textContent.toLowerCase().indexOf(q) !== -1;
      row.style.display = hit ? '' : 'none';
      if (hit) shown++;
    });
    refresh(shown);
  });

  table.querySelectorAll('th').forEach(function (th, index) {
    th.addEventListener('click', function () {
      var desc = th.getAttribute('data-dir') !== 'desc';
      table.querySelectorAll('th').forEach(function (o) { o.removeAttribute('data-dir'); });
      th.setAttribute('data-dir', desc ? 'desc' : 'asc');
      var sorted = rows.slice().sort(function (a, b) {
        var x = a.cells[index], y = b.cells[index];
        var xs = x ? (x.dataset.sort || x.textContent) : '';
        var ys = y ? (y.dataset.sort || y.textContent) : '';
        var xn = parseFloat(String(xs).replace(/[^0-9.\\-]/g, ''));
        var yn = parseFloat(String(ys).replace(/[^0-9.\\-]/g, ''));
        var cmp = (!isNaN(xn) && !isNaN(yn))
          ? xn - yn
          : String(xs).localeCompare(String(ys), undefined, {sensitivity:'base'});
        return desc ? -cmp : cmp;
      });
      sorted.forEach(function (row) { body.appendChild(row); });
    });
  });
});
"""


def _cell(cell: Cell, column_key: str) -> str:
    if cell.chips:
        if not cell.chips:
            return '<span class="muted">—</span>'
        chips = "".join(
            '<span class="chip" style="background:#{colour};color:{ink}">{name}</span>'.format(
                colour=_escape(colour or "666666"),
                ink=readable_on(colour or "666666"),
                name=_escape(name),
            )
            for name, colour in cell.chips
        )
        return chips or '<span class="muted">—</span>'

    text = _escape(cell.text) if cell.text else "—"
    if not cell.text:
        return '<span class="muted">—</span>'

    inner = text
    if cell.kind in ("mono", "code"):
        inner = f'<span class="mono">{text}</span>'
    elif cell.kind == "muted":
        inner = f'<span class="muted">{text}</span>'

    if cell.href:
        return f'<a href="{_escape(cell.href, quote=True)}" rel="noopener">{inner}</a>'
    return inner


def _section(section: Section, index: int) -> str:
    parts = [f"<h2>{_escape(section.title)}</h2>"]
    if section.subtitle:
        parts.append(f'<p class="section-sub">{_escape(section.subtitle)}</p>')

    if section.empty:
        parts.append('<div class="scroll"><p class="empty">Nothing to show.</p></div>')
        if section.note:
            parts.append(f'<p class="note">{_escape(section.note)}</p>')
        return "\n".join(parts)

    head = "".join(
        '<th class="{cls}">{label}</th>'.format(
            cls="right" if column.align == "right" else "",
            label=_escape(column.label),
        )
        for column in section.columns
    )

    body_rows = []
    for row in section.rows:
        cells = []
        for column, cell in zip(section.columns, row):
            classes = []
            if column.align == "right":
                classes.append("right")
            if column.key == "title":
                classes.append("title")
            attr = f' class="{" ".join(classes)}"' if classes else ""
            sort_hint = ""
            if cell.chips:
                sort_hint = f' data-sort="{_escape(cell.plain, quote=True)}"'
            cells.append(f"<td{attr}{sort_hint}>{_cell(cell, column.key)}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    parts.append(
        f"""<div data-table id="t{index}">
  <div class="controls">
    <input type="search" placeholder="Search {_escape(section.title.lower())}…" aria-label="Search">
    <span class="count"></span>
  </div>
  <div class="scroll">
    <table>
      <thead><tr>{head}</tr></thead>
      <tbody>
        {"".join(body_rows)}
      </tbody>
    </table>
  </div>
</div>"""
    )
    if section.note:
        parts.append(f'<p class="note">{_escape(section.note)}</p>')
    return "\n".join(parts)


def render(report: Report) -> str:
    stamp = report.generated_at.astimezone().strftime("%d %B %Y at %H:%M")

    stats = "".join(
        '<div class="stat"><dt>{label}</dt><dd class="{cls}">{value}</dd></div>'.format(
            label=_escape(label),
            cls="long" if len(value) > 24 else "",
            value=_escape(value),
        )
        for label, value in report.stats
    )
    owner = (
        f' for <a href="https://github.com/{_escape(report.owner, quote=True)}">'
        f"@{_escape(report.owner)}</a>"
        if report.owner
        else ""
    )
    filter_note = (
        f'<div><span class="filter-note">filter: {_escape(report.filter_text)}</span></div>'
        if report.filter_text
        else ""
    )
    sections = "\n".join(_section(s, i) for i, s in enumerate(report.sections))

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="ZDECK">
<title>{_escape(report.title)}{" — @" + _escape(report.owner) if report.owner else ""}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="brand"><b>{MARK}</b> ZDECK</div>
  <h1>{_escape(report.title)}</h1>
  <p class="sub">{_escape(report.subtitle)}</p>
  <div class="meta">Generated {stamp}{owner}</div>
  {filter_note}
</header>

<dl class="stats">{stats}</dl>

{sections}

<footer>
  {report.row_count:,} rows · made with
  <a href="https://github.com/TheHolyOneZ" rel="noopener">ZDECK</a>,
  a GitHub dashboard for the terminal.
</footer>
</div>
<script>{JS}</script>
</body>
</html>
"""
