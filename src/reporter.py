"""Generate self-contained HTML dashboard.

The output is a single HTML file with Chart.js and all data inlined — no
network requests, no companion files. Open it and it works.

Two modes:
  * Config mode  — caller passes a loaded org config; the report shows
    EMP/CTR splits, a By-<level_1> stacked bar, a per-<level_1> drilldown,
    a per-<level_1> trend line, and three cascading filter dropdowns.
  * Generic mode — caller passes ``config=None``; the report shows the
    meeting table, attendance trend, and duration histogram. Only the
    Meeting filter is shown.

Payload model
-------------
Aggregates are computed in the BROWSER from a raw ``rows`` array baked
into the page. Each row is one (meeting × participant) attendance fact:

  {pid, source_file, major_org, sub_org, employee_type, minutes}

``pid`` is a sequential integer assigned by Python — used to dedup
participants across meetings without exposing names. No names, emails,
or other PII appear anywhere in the rendered HTML.

The JS reads ``DATA.rows``, applies the active filter state, and
recomputes the meeting table, all charts, and the summary KPI tiles
each time a filter changes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pandas as pd


ASSETS_DIR = Path(__file__).parent / "assets"
CHART_JS_PATH = ASSETS_DIR / "chart.umd.js"

DEFAULT_TITLE = "Teams Attendance Report"
DEFAULT_CAP_MINUTES = 60.0

# U.S. Census Bureau Data Visualization Standards palette.
# https://xdgov.github.io/data-design-standards/components/colors
# Values are mirrored in the CSS :root block below — keep them in sync.
COLORS = {
    "emp":       "#0095A8",
    "ctr":       "#FF7043",
    "navy":      "#112E51",
    "grey":      "#78909C",
    "grid":      "#CFD8DC",
    "bg":        "#FFFFFF",
    "row_alt":   "#F5F5F5",
    "teal_dark": "#006C7A",
}
ORG_PALETTE = [
    "#0095A8",  # teal
    "#112E51",  # navy
    "#FF7043",  # orange
    "#78909C",  # grey
    "#006C7A",  # dark teal
    "#004851",  # darker teal
    "#B2EBF2",  # lightest teal
]


def _meeting_date_iso(start_time_str) -> str:
    """Pull an ISO date out of Teams' 'M/D/YYYY h:mm:ss AM/PM' string."""
    if not start_time_str:
        return ""
    head = str(start_time_str).split()[0]
    try:
        m, d, y = head.split("/")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except (ValueError, AttributeError):
        return ""


def _safe_float(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _identity_key_series(internal: pd.DataFrame, has_config: bool) -> pd.Series:
    """The series used to dedup unique participants in the JS payload.

    Uses ``clean_name`` after enrichment, falls back to ``Name``. Never
    leaves Python — only the integer ``pid`` derived from it ships.
    """
    if has_config and "clean_name" in internal.columns:
        return internal["clean_name"].fillna(internal["Name"]).astype(str)
    return internal["Name"].astype(str)


def _build_rows(internal: pd.DataFrame, has_config: bool) -> list[dict]:
    """Stripped-down attendance facts. No names.

    One row per (meeting × participant) post-aggregation. Integer ``pid``
    is the only identity-bearing field, used by the JS to dedup
    participants across meetings when computing the unique-count KPI.
    """
    if internal.empty:
        return []
    key_series = _identity_key_series(internal, has_config)
    # First-seen order assigns pids; the mapping never leaves Python.
    pid_map: dict[str, int] = {}
    for k in key_series:
        if k not in pid_map:
            pid_map[k] = len(pid_map)

    mins_col = (
        "attendance_minutes_capped"
        if "attendance_minutes_capped" in internal.columns
        else "attendance_minutes"
    )

    def _str_or_none(value):
        if value is None:
            return None
        if isinstance(value, float) and pd.isna(value):
            return None
        s = str(value).strip()
        return s if s else None

    rows = []
    for (_, row), key in zip(internal.iterrows(), key_series):
        rows.append({
            "pid": pid_map[key],
            "source_file": str(row.get("source_file", "")),
            "major_org": _str_or_none(row.get("major_org")) if has_config else None,
            "sub_org": _str_or_none(row.get("sub_org")) if has_config else None,
            "employee_type": _str_or_none(row.get("employee_type")) if has_config else None,
            "minutes": round(_safe_float(row.get(mins_col, 0)), 2),
        })
    return rows


def _build_meetings_meta(meetings: list[dict]) -> list[dict]:
    out = []
    for m in meetings:
        out.append({
            "source_file": m.get("source_file", ""),
            "meeting_title": m.get("meeting_title", ""),
            "date": _meeting_date_iso(m.get("start_time", "")),
            "duration_min": round(_safe_float(m.get("meeting_duration_min")), 1),
            "avg_attendance_min": round(_safe_float(m.get("avg_attendance_min")), 1),
        })
    out.sort(key=lambda r: r["date"] or r["source_file"])
    return out


def _build_filters(config: dict | None, meetings_meta: list[dict]) -> dict:
    """Dropdown choices for the filter bar.

    ``divisions_by_directorate`` is sourced from the config (not the data),
    so the dropdown lists every known sub-org even if no one in the
    current data attended from it.
    """
    meeting_choices = []
    for m in meetings_meta:
        title = m["meeting_title"] or m["source_file"]
        label = f"{m['date']} — {title}" if m["date"] else title
        meeting_choices.append({"source_file": m["source_file"], "label": label})

    directorates: list[str] = []
    divisions: dict[str, list[str]] = {}
    if config is not None:
        for major, info in (config.get("org_mapping") or {}).items():
            directorates.append(major)
            info = info or {}
            divs: list[str] = []
            if info.get("direct_codes"):
                divs.append("(direct)")
            for sub in info.get("sub_orgs") or []:
                divs.append(str(sub))
            divisions[major] = divs

    return {
        "meetings": meeting_choices,
        "directorates": directorates,
        "divisions_by_directorate": divisions,
    }


def _build_payload(meetings: list[dict],
                   participants: pd.DataFrame,
                   config: dict | None,
                   cap_minutes: float) -> dict:
    has_config = config is not None
    cfg_labels = (config or {}).get("labels", {}) if has_config else {}
    org_name = (config or {}).get("org_name", "") if has_config else ""

    if has_config and "is_internal" in participants.columns:
        internal = participants[participants["is_internal"]].copy()
    else:
        internal = participants.copy()

    rows = _build_rows(internal, has_config)
    meetings_meta = _build_meetings_meta(meetings)
    cap_repr = int(cap_minutes) if float(cap_minutes).is_integer() else float(cap_minutes)

    return {
        "config": {
            "has_org_config": has_config,
            "org_name": org_name,
            "cap_minutes": cap_repr,
            "labels": {
                "employee": cfg_labels.get("employee", "EMP"),
                "contractor": cfg_labels.get("contractor", "CTR"),
                "level_1": cfg_labels.get("level_1", "Major Org"),
                "level_2": cfg_labels.get("level_2", "Sub Org"),
            },
        },
        "rows": rows,
        "meetings": meetings_meta,
        "filters": _build_filters(config, meetings_meta),
        "palette": {
            "emp":  COLORS["emp"],
            "ctr":  COLORS["ctr"],
            "navy": COLORS["navy"],
            "grey": COLORS["grey"],
            "grid": COLORS["grid"],
            "org":  ORG_PALETTE,
        },
    }


def _combine_participants(meetings: list[dict],
                          participants_per_meeting: Iterable[pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for meta, df in zip(meetings, participants_per_meeting):
        if df is None or df.empty:
            continue
        tagged = df.copy()
        tagged["source_file"] = meta.get("source_file", "")
        frames.append(tagged)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def generate_report(meetings: list[dict],
                    participants: pd.DataFrame,
                    config: dict | None = None,
                    output_path: str | Path = "output/report.html",
                    title: str | None = None,
                    cap_minutes: float | None = None) -> Path:
    """Render the dashboard. Returns the output path.

    ``participants`` must already include a ``source_file`` column linking
    each row to a meeting from ``meetings``. The CLI handles this.
    """
    if cap_minutes is None:
        cap_minutes = float((config or {}).get("cap_minutes", DEFAULT_CAP_MINUTES))
    cap_minutes = float(cap_minutes)

    payload = _build_payload(meetings, participants, config, cap_minutes)
    if title is None:
        org_name = payload["config"]["org_name"]
        title = f"{org_name} Attendance Report" if org_name else DEFAULT_TITLE
    payload["title"] = title

    data_json = json.dumps(payload, default=str)
    # Defensive: prevent the JSON breaking out of the <script> tag
    data_json = data_json.replace("</", "<\\/")

    chart_js = CHART_JS_PATH.read_text(encoding="utf-8")

    html = (_HTML_TEMPLATE
            .replace("__TITLE__", _escape_html(title))
            .replace("__CHART_JS__", chart_js)
            .replace("__DATA_JSON__", data_json))

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def _escape_html(value: str) -> str:
    return (value
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# ---------------------------------------------------------------------------
# HTML template — sentinels (__CHART_JS__, __DATA_JSON__, __TITLE__) are
# substituted in generate_report(). All CSS and dashboard JS live below.
#
# Section order is deliberate:
#   1. Header (totals, EMP/CTR split, date range)
#   2. Filter bar (sticky)
#   3. Meetings table
#   4. By <level_1>            ← org-only
#   5. Attendance over time
#   6. Trend by <level_1>      ← org-only
#   7. <level_1> drilldown     ← org-only
#   8. Attendance duration histogram (last — secondary signal)
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>__TITLE__</title>
<style>
  :root {
    /* U.S. Census Bureau Data Visualization Standards palette.
       Mirrors COLORS dict in reporter.py — keep in sync. */
    --census-teal:      #0095A8;
    --census-navy:      #112E51;
    --census-orange:    #FF7043;
    --census-grey:      #78909C;
    --census-grid:      #CFD8DC;
    --census-bg:        #FFFFFF;
    --census-row-alt:   #F5F5F5;
    --census-teal-dark: #006C7A;

    --bg:       var(--census-bg);
    --fg:       var(--census-navy);
    --muted:    var(--census-grey);
    --border:   var(--census-grid);
    --row-alt:  var(--census-row-alt);
    --emp:      var(--census-teal);
    --ctr:      var(--census-orange);
    --th-bg:    var(--census-navy);
    --th-fg:    #FFFFFF;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background: var(--bg);
    color: var(--fg);
    line-height: 1.5;
  }
  header { padding: 1.5rem 2rem 1rem; border-bottom: 1px solid var(--border); }
  header h1 { margin: 0 0 0.5rem; font-size: 1.6rem; }
  header .subtitle { color: var(--muted); font-size: 0.9rem; }
  .summary-tiles {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
    margin-top: 1rem;
  }
  .tile {
    background: var(--row-alt);
    border-radius: 8px;
    padding: 0.9rem 1rem;
  }
  .tile .value { font-size: 1.4rem; font-weight: 600; }
  .tile .label { color: var(--muted); font-size: 0.85rem; margin-top: 0.15rem; }

  .filter-bar {
    position: sticky;
    top: 0;
    z-index: 10;
    display: flex;
    flex-wrap: wrap;
    gap: 1rem 1.5rem;
    align-items: center;
    background: var(--bg);
    padding: 0.85rem 2rem;
    border-bottom: 1px solid var(--border);
    box-shadow: 0 1px 2px rgba(17, 46, 81, 0.04);
  }
  .filter-bar label {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    color: var(--fg);
    font-size: 0.9rem;
  }
  .filter-bar select {
    font: inherit;
    color: var(--fg);
    background: white;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.35rem 0.55rem;
    max-width: 280px;
  }
  .filter-bar button {
    font: inherit;
    color: var(--muted);
    background: white;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.35rem 0.85rem;
    cursor: pointer;
  }
  .filter-bar button:hover { color: var(--fg); border-color: var(--muted); }

  main { padding: 1.5rem 2rem 3rem; }
  section { margin-bottom: 2.5rem; }
  section h2 { font-size: 1.15rem; margin: 0 0 0.75rem; }
  .chart-wrap { position: relative; height: 320px; max-width: 1000px; }
  .chart-wrap.tall { height: 420px; }

  table.data {
    width: 100%;
    max-width: 1000px;
    table-layout: fixed;
    border-collapse: collapse;
    font-size: 0.92rem;
  }
  table.data th, table.data td {
    text-align: left;
    padding: 0.6rem 0.75rem;
    border-bottom: 1px solid var(--border);
    overflow: hidden;
    text-overflow: ellipsis;
    word-wrap: break-word;
  }
  table.data th.numeric, table.data td.numeric { text-align: right; }
  table.data th {
    background: var(--th-bg);
    color: var(--th-fg);
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
    border-bottom: none;
  }
  table.data th::after { content: ""; margin-left: 0.3rem; opacity: 0.5; }
  table.data th[data-sort="asc"]::after  { content: "▲"; opacity: 1; }
  table.data th[data-sort="desc"]::after { content: "▼"; opacity: 1; }
  table.data tbody tr:nth-child(even) { background: var(--row-alt); }

  .controls { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem; flex-wrap: wrap; }
  .controls label { font-size: 0.9rem; color: var(--muted); }
  .controls input, .controls select {
    font: inherit;
    padding: 0.4rem 0.55rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: white;
  }

  .empty-state {
    color: var(--muted);
    font-style: italic;
    padding: 1.5rem 0;
  }
  .note { color: var(--muted); font-size: 0.85rem; margin-top: 0.4rem; }
  body.no-org .org-only { display: none; }
</style>
</head>
<body>
<header>
  <h1 id="page-title">__TITLE__</h1>
  <div class="subtitle" id="page-subtitle"></div>
  <div class="summary-tiles" id="summary-tiles"></div>
</header>

<div class="filter-bar" id="filter-bar">
  <label>
    Meeting
    <select id="filter-meeting"></select>
  </label>
  <label class="org-only">
    <span id="filter-directorate-label">Directorate</span>
    <select id="filter-directorate"></select>
  </label>
  <label class="org-only">
    <span id="filter-division-label">Division</span>
    <select id="filter-division"></select>
  </label>
  <button id="filter-reset" type="button">Reset</button>
</div>

<main>
  <section id="section-meetings">
    <h2>Meetings</h2>
    <table class="data" id="meetings-table">
      <thead><tr></tr></thead>
      <tbody></tbody>
    </table>
  </section>

  <section id="section-major-stack" class="org-only">
    <h2 id="major-stack-title">By Major Org</h2>
    <div class="chart-wrap"><canvas id="major-stack-chart"></canvas></div>
  </section>

  <section id="section-trend">
    <h2>Attendance Over Time</h2>
    <div class="chart-wrap"><canvas id="trend-chart"></canvas></div>
  </section>

  <section id="section-trend-org" class="org-only">
    <h2 id="trend-org-title">Trend by Major Org</h2>
    <div class="chart-wrap tall"><canvas id="trend-org-chart"></canvas></div>
    <div class="note">Click a legend entry to toggle that series.</div>
  </section>

  <section id="section-drilldown" class="org-only">
    <h2 id="drilldown-title">Drilldown</h2>
    <div class="controls">
      <label for="major-org-picker">Select:</label>
      <select id="major-org-picker"></select>
    </div>
    <div class="chart-wrap"><canvas id="drilldown-chart"></canvas></div>
  </section>

  <section id="section-histogram">
    <h2>Attendance Duration Distribution</h2>
    <div class="chart-wrap"><canvas id="hist-chart"></canvas></div>
    <div class="note" id="hist-note"></div>
  </section>
</main>

<script>__CHART_JS__</script>
<script>
(function () {
  const DATA = __DATA_JSON__;
  const hasOrg = DATA.config.has_org_config;
  const labels = DATA.config.labels;
  const cap = DATA.config.cap_minutes;
  const palette = DATA.palette;
  const filters = DATA.filters;

  // ---- Chart.js defaults (one place, every chart inherits) ----
  Chart.defaults.color = palette.grey;
  Chart.defaults.borderColor = palette.grid;
  Chart.defaults.font.family =
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

  if (!hasOrg) document.body.classList.add("no-org");

  // ---- State + chart instance registry (so we can destroy on redraw) ----
  const state = { meeting: 'ALL', directorate: 'ALL', division: 'ALL' };
  const chartInstances = {};

  // ---- Page subtitle: full date range, immutable ----
  const allDates = DATA.meetings.map(m => m.date).filter(Boolean).sort();
  const subtitleEl = document.getElementById("page-subtitle");
  if (allDates.length === 1) subtitleEl.textContent = allDates[0];
  else if (allDates.length > 1) subtitleEl.textContent = `${allDates[0]} → ${allDates[allDates.length - 1]}`;

  // ---- Filter bar ----
  const sel = {
    meeting: document.getElementById('filter-meeting'),
    directorate: document.getElementById('filter-directorate'),
    division: document.getElementById('filter-division'),
  };
  if (hasOrg) {
    document.getElementById('filter-directorate-label').textContent = labels.level_1;
    document.getElementById('filter-division-label').textContent = labels.level_2;
  }

  function addOption(selectEl, value, text) {
    const opt = document.createElement('option');
    opt.value = value; opt.textContent = text;
    selectEl.appendChild(opt);
  }
  function populateMeetingFilter() {
    sel.meeting.innerHTML = '';
    addOption(sel.meeting, 'ALL', 'All meetings');
    filters.meetings.forEach(m => addOption(sel.meeting, m.source_file, m.label));
  }
  function populateDirectorateFilter() {
    sel.directorate.innerHTML = '';
    addOption(sel.directorate, 'ALL', `All ${labels.level_1}s`);
    filters.directorates.forEach(d => addOption(sel.directorate, d, d));
  }
  function populateDivisionFilter() {
    sel.division.innerHTML = '';
    addOption(sel.division, 'ALL', `All ${labels.level_2}s`);
    if (state.directorate !== 'ALL') {
      (filters.divisions_by_directorate[state.directorate] || []).forEach(d => {
        addOption(sel.division, d, d);
      });
    } else {
      Object.entries(filters.divisions_by_directorate).forEach(([dir, divs]) => {
        const og = document.createElement('optgroup');
        og.label = dir;
        divs.forEach(d => {
          const opt = document.createElement('option');
          opt.value = d; opt.textContent = d;
          og.appendChild(opt);
        });
        sel.division.appendChild(og);
      });
    }
  }
  function parentDirectorateOf(division) {
    for (const [dir, divs] of Object.entries(filters.divisions_by_directorate)) {
      if (divs.includes(division)) return dir;
    }
    return null;
  }

  populateMeetingFilter();
  if (hasOrg) { populateDirectorateFilter(); populateDivisionFilter(); }

  sel.meeting.addEventListener('change', e => { state.meeting = e.target.value; redraw(); });
  if (hasOrg) {
    sel.directorate.addEventListener('change', e => {
      state.directorate = e.target.value;
      if (state.directorate === 'ALL') {
        state.division = 'ALL';
      } else {
        // Drop division if it doesn't belong to the new directorate
        const valid = filters.divisions_by_directorate[state.directorate] || [];
        if (state.division !== 'ALL' && !valid.includes(state.division)) {
          state.division = 'ALL';
        }
      }
      populateDivisionFilter();
      sel.division.value = state.division;
      redraw();
    });
    sel.division.addEventListener('change', e => {
      state.division = e.target.value;
      if (state.division !== 'ALL' && state.directorate === 'ALL') {
        const parent = parentDirectorateOf(state.division);
        if (parent) {
          state.directorate = parent;
          sel.directorate.value = parent;
          populateDivisionFilter();
          sel.division.value = state.division;
        }
      }
      redraw();
    });
  }
  document.getElementById('filter-reset').addEventListener('click', () => {
    state.meeting = 'ALL'; state.directorate = 'ALL'; state.division = 'ALL';
    sel.meeting.value = 'ALL';
    if (hasOrg) {
      sel.directorate.value = 'ALL';
      populateDivisionFilter();
      sel.division.value = 'ALL';
    }
    redraw();
  });

  // ---- Filtering + aggregation helpers (pure, no DOM) ----
  function filterRows(rows, st) {
    return rows.filter(r => {
      if (st.meeting !== 'ALL' && r.source_file !== st.meeting) return false;
      if (st.directorate !== 'ALL' && r.major_org !== st.directorate) return false;
      if (st.division !== 'ALL') {
        if (st.division === '(direct)') {
          if (r.sub_org) return false;
        } else if (r.sub_org !== st.division) {
          return false;
        }
      }
      return true;
    });
  }
  function uniquePids(rows) {
    const s = new Set();
    rows.forEach(r => s.add(r.pid));
    return s.size;
  }
  function uniquePidsByType(rows, type) {
    const s = new Set();
    rows.forEach(r => { if (r.employee_type === type) s.add(r.pid); });
    return s.size;
  }
  function countByType(rows, type) {
    let n = 0;
    rows.forEach(r => { if (r.employee_type === type) n++; });
    return n;
  }
  function groupBy(rows, key) {
    const out = {};
    rows.forEach(r => {
      const k = r[key];
      if (k === null || k === undefined) return;
      (out[k] = out[k] || []).push(r);
    });
    return out;
  }
  function histogramBuckets(rows, capVal) {
    const upper = Math.max(5, Math.ceil(capVal / 5) * 5);
    const nBins = upper / 5;
    const lbls = [], emp = [], ctr = [], all = [];
    for (let i = 0; i < nBins; i++) {
      lbls.push(`${i * 5}-${(i + 1) * 5}`);
      emp.push(0); ctr.push(0); all.push(0);
    }
    rows.forEach(r => {
      const m = Math.min(capVal, Math.max(0, r.minutes));
      let idx = Math.floor(m / 5);
      if (idx >= nBins) idx = nBins - 1;
      all[idx]++;
      if (r.employee_type === labels.employee) emp[idx]++;
      else if (r.employee_type === labels.contractor) ctr[idx]++;
    });
    return { labels: lbls, EMP: emp, CTR: ctr, All: all };
  }

  // ---- Chart instance + empty-state plumbing ----
  function ensureChart(canvasId, cfg) {
    const el = document.getElementById(canvasId);
    if (!el) return;
    if (chartInstances[canvasId]) chartInstances[canvasId].destroy();
    chartInstances[canvasId] = new Chart(el.getContext('2d'), cfg);
  }
  function destroyChart(canvasId) {
    if (chartInstances[canvasId]) {
      chartInstances[canvasId].destroy();
      delete chartInstances[canvasId];
    }
  }
  function setEmpty(sectionId, isEmpty) {
    const section = document.getElementById(sectionId);
    if (!section) return;
    let note = section.querySelector(':scope > .empty-state');
    const targets = section.querySelectorAll(':scope > .chart-wrap, :scope > table.data, :scope > .controls, :scope > .note');
    if (isEmpty) {
      if (!note) {
        note = document.createElement('div');
        note.className = 'empty-state';
        note.textContent = 'No data for current filter selection.';
        section.appendChild(note);
      }
      note.style.display = '';
      targets.forEach(el => el.style.display = 'none');
    } else {
      if (note) note.style.display = 'none';
      targets.forEach(el => el.style.display = '');
    }
  }

  // ---- Section renderers ----
  function renderHeaderTiles(rows) {
    const tilesEl = document.getElementById("summary-tiles");
    tilesEl.innerHTML = '';
    const meetingsShown = state.meeting === 'ALL' ? DATA.meetings.length : 1;
    const tiles = [
      { label: "Meetings", value: meetingsShown },
      { label: "Unique participants", value: uniquePids(rows) },
    ];
    if (hasOrg) {
      const empU = uniquePidsByType(rows, labels.employee);
      const ctrU = uniquePidsByType(rows, labels.contractor);
      const total = empU + ctrU;
      const share = total ? Math.round((empU / total) * 100) : 0;
      tiles.push({ label: `${labels.employee} / ${labels.contractor}`, value: `${empU} / ${ctrU}` });
      tiles.push({ label: `${labels.employee} share`, value: share + "%" });
    }
    tiles.forEach(t => {
      const div = document.createElement("div"); div.className = "tile";
      const v = document.createElement("div"); v.className = "value"; v.textContent = t.value;
      const l = document.createElement("div"); l.className = "label"; l.textContent = t.label;
      div.appendChild(v); div.appendChild(l);
      tilesEl.appendChild(div);
    });
  }

  function renderMeetingsTable(rows) {
    const cols = hasOrg
      ? [
          { key: "date", label: "Date", width: "110px" },
          { key: "meeting_title", label: "Meeting" },
          { key: "total_attendees", label: "Attendees", numeric: true, width: "100px" },
          { key: "emp_count", label: labels.employee, numeric: true, width: "80px" },
          { key: "ctr_count", label: labels.contractor, numeric: true, width: "80px" },
          { key: "avg_attendance_min", label: "Avg (min)", numeric: true, width: "100px" },
        ]
      : [
          { key: "date", label: "Date", width: "120px" },
          { key: "meeting_title", label: "Meeting" },
          { key: "total_attendees", label: "Attendees", numeric: true, width: "120px" },
          { key: "avg_attendance_min", label: "Avg (min)", numeric: true, width: "120px" },
        ];
    const rowsBySource = groupBy(rows, 'source_file');
    const visibleMeetings = DATA.meetings
      .filter(m => state.meeting === 'ALL' || m.source_file === state.meeting);
    const tableRows = visibleMeetings.map(m => {
      const rs = rowsBySource[m.source_file] || [];
      return {
        date: m.date,
        meeting_title: m.meeting_title,
        total_attendees: rs.length,
        emp_count: countByType(rs, labels.employee),
        ctr_count: countByType(rs, labels.contractor),
        avg_attendance_min: m.avg_attendance_min,
      };
    });
    setEmpty('section-meetings', tableRows.length === 0);
    if (tableRows.length === 0) return;
    renderTable(document.getElementById("meetings-table"), cols, tableRows);
  }

  function renderMajorStack(rows) {
    if (!hasOrg) return;
    const grouped = groupBy(rows, 'major_org');
    const items = Object.entries(grouped).map(([org, rs]) => ({
      major_org: org,
      EMP: countByType(rs, labels.employee),
      CTR: countByType(rs, labels.contractor),
      total: rs.length,
    })).sort((a, b) => b.total - a.total);
    const hasData = items.length > 0;
    setEmpty('section-major-stack', !hasData);
    if (!hasData) { destroyChart('major-stack-chart'); return; }
    document.getElementById("major-stack-title").textContent = `By ${labels.level_1}`;
    ensureChart('major-stack-chart', {
      type: "bar",
      data: {
        labels: items.map(r => r.major_org),
        datasets: [
          { label: labels.employee, data: items.map(r => r.EMP), backgroundColor: palette.emp, stack: "s" },
          { label: labels.contractor, data: items.map(r => r.CTR), backgroundColor: palette.ctr, stack: "s" },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true, maintainAspectRatio: false,
        scales: { x: { stacked: true, beginAtZero: true }, y: { stacked: true } },
      },
    });
  }

  function renderTrend(rows) {
    const meetingsToShow = DATA.meetings
      .filter(m => state.meeting === 'ALL' || m.source_file === state.meeting);
    const rowsBySource = groupBy(rows, 'source_file');
    const labels_x = meetingsToShow.map(m => m.date || m.source_file);
    const titles = meetingsToShow.map(m => m.meeting_title);
    const empArr = [], ctrArr = [], totalArr = [];
    meetingsToShow.forEach(m => {
      const rs = rowsBySource[m.source_file] || [];
      empArr.push(countByType(rs, labels.employee));
      ctrArr.push(countByType(rs, labels.contractor));
      totalArr.push(rs.length);
    });
    const hasData = totalArr.some(v => v > 0);
    setEmpty('section-trend', !hasData);
    if (!hasData) { destroyChart('trend-chart'); return; }
    const datasets = hasOrg
      ? [
          { label: labels.employee, data: empArr, backgroundColor: palette.emp, stack: "s" },
          { label: labels.contractor, data: ctrArr, backgroundColor: palette.ctr, stack: "s" },
        ]
      : [
          { label: "Attendees", data: totalArr, backgroundColor: palette.emp },
        ];
    ensureChart('trend-chart', {
      type: "bar",
      data: { labels: labels_x, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        scales: {
          x: { stacked: hasOrg },
          y: { stacked: hasOrg, beginAtZero: true, title: { display: true, text: "Attendees" } },
        },
        plugins: {
          legend: { display: hasOrg },
          tooltip: { callbacks: { afterTitle: (items) => titles[items[0].dataIndex] || "" } },
        },
      },
    });
  }

  function renderTrendByOrg(rows) {
    if (!hasOrg) return;
    const meetingsToShow = DATA.meetings
      .filter(m => state.meeting === 'ALL' || m.source_file === state.meeting);
    const rowsBySource = groupBy(rows, 'source_file');
    const orgsSet = new Set();
    rows.forEach(r => { if (r.major_org) orgsSet.add(r.major_org); });
    const orgs = Array.from(orgsSet).sort();
    const xLabels = meetingsToShow.map(m => m.date || m.source_file);
    const series = {};
    orgs.forEach(org => {
      series[org] = meetingsToShow.map(m => {
        const rs = rowsBySource[m.source_file] || [];
        let n = 0;
        rs.forEach(r => { if (r.major_org === org) n++; });
        return n;
      });
    });
    const hasData = orgs.length > 0 && xLabels.length > 0;
    setEmpty('section-trend-org', !hasData);
    if (!hasData) { destroyChart('trend-org-chart'); return; }
    document.getElementById("trend-org-title").textContent = `Trend by ${labels.level_1}`;
    ensureChart('trend-org-chart', {
      type: "line",
      data: {
        labels: xLabels,
        datasets: orgs.map((name, i) => ({
          label: name,
          data: series[name],
          borderColor: palette.org[i % palette.org.length],
          backgroundColor: palette.org[i % palette.org.length],
          tension: 0.25,
          fill: false,
        })),
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: "top" } },
        scales: { y: { beginAtZero: true, title: { display: true, text: "Attendees" } } },
      },
    });
  }

  function renderDrilldown(rows) {
    if (!hasOrg) return;
    const dirsSet = new Set();
    rows.forEach(r => { if (r.major_org) dirsSet.add(r.major_org); });
    const dirsArray = Array.from(dirsSet).sort();
    const picker = document.getElementById("major-org-picker");
    picker.innerHTML = '';
    if (dirsArray.length === 0) {
      setEmpty('section-drilldown', true);
      destroyChart('drilldown-chart');
      return;
    }
    setEmpty('section-drilldown', false);
    document.getElementById("drilldown-title").textContent = `${labels.level_1} Drilldown`;
    dirsArray.forEach(d => {
      const opt = document.createElement('option');
      opt.value = d; opt.textContent = d;
      picker.appendChild(opt);
    });
    const initial = (state.directorate !== 'ALL' && dirsArray.includes(state.directorate))
      ? state.directorate : dirsArray[0];
    picker.value = initial;

    function paint(major) {
      const subRows = rows.filter(r => r.major_org === major);
      const grouped = {};
      subRows.forEach(r => {
        const k = r.sub_org || '(direct)';
        (grouped[k] = grouped[k] || []).push(r);
      });
      const items = Object.entries(grouped).map(([sub, rs]) => ({
        sub_org: sub,
        EMP: countByType(rs, labels.employee),
        CTR: countByType(rs, labels.contractor),
        total: rs.length,
      })).sort((a, b) => b.total - a.total);
      ensureChart('drilldown-chart', {
        type: "bar",
        data: {
          labels: items.map(r => r.sub_org),
          datasets: [
            { label: labels.employee, data: items.map(r => r.EMP), backgroundColor: palette.emp, stack: "s" },
            { label: labels.contractor, data: items.map(r => r.CTR), backgroundColor: palette.ctr, stack: "s" },
          ],
        },
        options: {
          indexAxis: "y",
          responsive: true, maintainAspectRatio: false,
          scales: { x: { stacked: true, beginAtZero: true }, y: { stacked: true } },
        },
      });
    }
    paint(initial);
    picker.onchange = (e) => paint(e.target.value);
  }

  function renderHistogram(rows) {
    const h = histogramBuckets(rows, cap);
    const hasData = h.All.some(v => v > 0);
    setEmpty('section-histogram', !hasData);
    if (!hasData) { destroyChart('hist-chart'); return; }
    const datasets = hasOrg
      ? [
          { label: labels.employee, data: h.EMP, backgroundColor: palette.emp, stack: "stack" },
          { label: labels.contractor, data: h.CTR, backgroundColor: palette.ctr, stack: "stack" },
        ]
      : [
          { label: "Attendees", data: h.All, backgroundColor: palette.emp },
        ];
    ensureChart('hist-chart', {
      type: "bar",
      data: { labels: h.labels, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        scales: {
          x: { stacked: hasOrg, title: { display: true, text: `Attendance minutes (capped at ${cap})` } },
          y: { stacked: hasOrg, beginAtZero: true, title: { display: true, text: "Participant count" } },
        },
        plugins: { legend: { display: hasOrg } },
      },
    });
    document.getElementById("hist-note").textContent =
      `Buckets are 5 minutes wide. Values capped at ${cap} min.`;
  }

  // ---- Table helpers (used by the meetings table) ----
  function renderTable(table, columns, rows) {
    const thead = table.tHead.querySelector("tr");
    thead.innerHTML = "";
    columns.forEach((c, idx) => {
      const th = document.createElement("th");
      th.textContent = c.label;
      if (c.width) th.style.width = c.width;
      if (c.numeric) th.classList.add("numeric");
      th.addEventListener("click", () => sortBy(table, columns, rows, idx, c));
      thead.appendChild(th);
    });
    paintRows(table, columns, rows);
  }
  function paintRows(table, columns, rows) {
    const tbody = table.tBodies[0];
    tbody.innerHTML = "";
    rows.forEach(r => {
      const tr = document.createElement("tr");
      columns.forEach(c => {
        const td = document.createElement("td");
        const v = r[c.key];
        td.textContent = (v === null || v === undefined) ? "" : v;
        if (c.numeric) td.classList.add("numeric");
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  }
  function sortBy(table, columns, rows, idx, col) {
    const thead = table.tHead.querySelector("tr");
    const th = thead.children[idx];
    const current = th.dataset.sort;
    const next = current === "asc" ? "desc" : "asc";
    Array.from(thead.children).forEach(other => delete other.dataset.sort);
    th.dataset.sort = next;
    const direction = next === "asc" ? 1 : -1;
    const sorted = rows.slice().sort((a, b) => {
      const av = a[col.key], bv = b[col.key];
      if (col.numeric) return ((av || 0) - (bv || 0)) * direction;
      return String(av || "").localeCompare(String(bv || "")) * direction;
    });
    paintRows(table, columns, sorted);
  }

  // ---- Master redraw ----
  function redraw() {
    const rows = filterRows(DATA.rows, state);
    renderHeaderTiles(rows);
    renderMeetingsTable(rows);
    renderMajorStack(rows);
    renderTrend(rows);
    renderTrendByOrg(rows);
    renderDrilldown(rows);
    renderHistogram(rows);
  }
  redraw();
})();
</script>
</body>
</html>
"""
