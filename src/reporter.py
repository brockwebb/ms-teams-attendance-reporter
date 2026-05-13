"""Generate self-contained HTML dashboard.

The output is a single HTML file with Chart.js and all data inlined — no
network requests, no companion files. Open it and it works.

Two modes:
  * Config mode  — caller passes a loaded org config; the report shows
    EMP/CTR splits, major-org stacked bars, the major-org drilldown, and
    a per-major-org trend line.
  * Generic mode — caller passes ``config=None``; the report still shows
    meeting summary, attendance histogram, attendance trend, and the
    participant detail table, but skips the org-specific sections.

Math (histogram bins, per-meeting/per-org rollups, participant summary)
is computed in Python and baked into a JSON blob. The browser-side JS
only renders.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pandas as pd


ASSETS_DIR = Path(__file__).parent / "assets"
CHART_JS_PATH = ASSETS_DIR / "chart.umd.js"

DEFAULT_TITLE = "Teams Attendance Report"
HISTOGRAM_EDGES = list(range(0, 65, 5))  # 0,5,...,60 → 12 bins of width 5
EMP_COLOR = "#2a9d8f"
CTR_COLOR = "#e76f51"
# ColorBrewer Set2-ish palette for major-org lines / segments
ORG_PALETTE = ["#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3",
               "#a6d854", "#ffd92f", "#e5c494", "#b3b3b3"]


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


def _safe_int(value) -> int:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _compute_meetings_payload(meetings: list[dict],
                              participants_by_source: dict[str, pd.DataFrame],
                              has_config: bool) -> list[dict]:
    """Per-meeting stats for the summary table and trend charts."""
    rows: list[dict] = []
    for meta in meetings:
        source = meta.get("source_file", "")
        df = participants_by_source.get(source, pd.DataFrame())
        if has_config and "is_internal" in df.columns:
            internal = df[df["is_internal"]]
            external_dropped = int((~df["is_internal"]).sum())
            emp = int((internal["employee_type"] == "EMP").sum()) if "employee_type" in internal.columns else 0
            ctr = int((internal["employee_type"] == "CTR").sum()) if "employee_type" in internal.columns else 0
        else:
            internal = df
            external_dropped = 0
            emp = ctr = 0
        rows.append({
            "source_file": source,
            "meeting_title": meta.get("meeting_title", ""),
            "date": _meeting_date_iso(meta.get("start_time", "")),
            "duration_min": round(_safe_float(meta.get("meeting_duration_min")), 1),
            "avg_attendance_min": round(_safe_float(meta.get("avg_attendance_min")), 1),
            "total_attendees": int(len(internal)),
            "emp_count": emp,
            "ctr_count": ctr,
            "dropped_external": external_dropped,
        })
    rows.sort(key=lambda r: r["date"] or r["source_file"])
    return rows


def _bucket_index(minutes: float) -> int:
    if minutes < 0:
        return 0
    idx = int(minutes // 5)
    return min(idx, len(HISTOGRAM_EDGES) - 2)


def _compute_histogram(combined: pd.DataFrame, has_config: bool) -> dict:
    labels = [f"{HISTOGRAM_EDGES[i]}-{HISTOGRAM_EDGES[i + 1]}" for i in range(len(HISTOGRAM_EDGES) - 1)]
    duration_col = "attendance_minutes_capped" if "attendance_minutes_capped" in combined.columns else "attendance_minutes"
    emp_buckets = [0] * (len(HISTOGRAM_EDGES) - 1)
    ctr_buckets = [0] * (len(HISTOGRAM_EDGES) - 1)
    all_buckets = [0] * (len(HISTOGRAM_EDGES) - 1)
    if duration_col not in combined.columns or combined.empty:
        return {"labels": labels, "EMP": emp_buckets, "CTR": ctr_buckets, "All": all_buckets}
    for value, etype in zip(combined[duration_col], combined.get("employee_type", pd.Series([None] * len(combined)))):
        mins = min(60.0, _safe_float(value))
        idx = _bucket_index(mins)
        all_buckets[idx] += 1
        if has_config:
            if etype == "EMP":
                emp_buckets[idx] += 1
            elif etype == "CTR":
                ctr_buckets[idx] += 1
    return {"labels": labels, "EMP": emp_buckets, "CTR": ctr_buckets, "All": all_buckets}


def _compute_major_org_stack(combined: pd.DataFrame) -> list[dict]:
    if "major_org" not in combined.columns:
        return []
    grouped = combined.groupby(["major_org", "employee_type"]).size().unstack(fill_value=0)
    grouped = grouped.reindex(columns=["EMP", "CTR"], fill_value=0)
    grouped["total"] = grouped.sum(axis=1)
    grouped = grouped.sort_values("total", ascending=False)
    return [
        {"major_org": idx, "EMP": int(row["EMP"]), "CTR": int(row["CTR"])}
        for idx, row in grouped.iterrows()
    ]


def _compute_sub_org_by_major(combined: pd.DataFrame) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    if "major_org" not in combined.columns or "sub_org" not in combined.columns:
        return out
    for major, sub_df in combined.groupby("major_org"):
        sub_df = sub_df.copy()
        sub_df["sub_org_display"] = sub_df["sub_org"].fillna("(direct)")
        grouped = sub_df.groupby(["sub_org_display", "employee_type"]).size().unstack(fill_value=0)
        grouped = grouped.reindex(columns=["EMP", "CTR"], fill_value=0)
        grouped["total"] = grouped.sum(axis=1)
        grouped = grouped.sort_values("total", ascending=False)
        out[str(major)] = [
            {"sub_org": idx, "EMP": int(row["EMP"]), "CTR": int(row["CTR"])}
            for idx, row in grouped.iterrows()
        ]
    return out


def _compute_trend(meetings_payload: list[dict]) -> dict:
    """Stacked-bar trend: dates × [EMP, CTR]."""
    return {
        "labels": [m["date"] or m["source_file"] for m in meetings_payload],
        "titles": [m["meeting_title"] for m in meetings_payload],
        "EMP": [m["emp_count"] for m in meetings_payload],
        "CTR": [m["ctr_count"] for m in meetings_payload],
        "Total": [m["total_attendees"] for m in meetings_payload],
    }


def _compute_trend_by_major_org(combined: pd.DataFrame,
                                meetings_payload: list[dict]) -> dict:
    """One series per major org, counts per meeting (in display order)."""
    ordered_sources = [m["source_file"] for m in meetings_payload]
    labels = [m["date"] or m["source_file"] for m in meetings_payload]
    if "major_org" not in combined.columns or "source_file" not in combined.columns:
        return {"labels": labels, "series": {}}
    pivot = combined.pivot_table(
        index="source_file",
        columns="major_org",
        values="attendance_minutes",
        aggfunc="count",
        fill_value=0,
    )
    pivot = pivot.reindex(index=ordered_sources, fill_value=0)
    series = {str(col): [int(v) for v in pivot[col].tolist()] for col in pivot.columns}
    return {"labels": labels, "series": series}


def _compute_participant_summary(combined: pd.DataFrame, has_config: bool) -> list[dict]:
    if combined.empty:
        return []
    if has_config and "clean_name" in combined.columns:
        key = combined["clean_name"].fillna(combined["Name"])
    else:
        key = combined["Name"]
    work = combined.assign(_key=key.astype(str))
    rows = []
    for k, group in work.groupby("_key", sort=False):
        first = group.iloc[0]
        rows.append({
            "name": k,
            "org_code": str(first["org_code"]) if "org_code" in group.columns and not pd.isna(first.get("org_code")) else "",
            "major_org": str(first["major_org"]) if "major_org" in group.columns and not pd.isna(first.get("major_org")) else "",
            "sub_org": str(first["sub_org"]) if "sub_org" in group.columns and not pd.isna(first.get("sub_org")) else "",
            "employee_type": str(first["employee_type"]) if "employee_type" in group.columns and not pd.isna(first.get("employee_type")) else "",
            "sessions_attended": int(len(group)),
            "total_duration_min": round(float(group["attendance_minutes"].sum()), 1),
            "avg_duration_min": round(float(group["attendance_minutes"].mean()), 1),
        })
    rows.sort(key=lambda r: (-r["sessions_attended"], -r["total_duration_min"], r["name"]))
    return rows


def _build_payload(meetings: list[dict],
                   participants: pd.DataFrame,
                   config: dict | None) -> dict:
    has_config = config is not None
    org_labels = (config or {}).get("org_labels", {}) if has_config else {}
    org_name = (config or {}).get("org_name", "") if has_config else ""

    participants_by_source: dict[str, pd.DataFrame] = {}
    if not participants.empty and "source_file" in participants.columns:
        for source, df in participants.groupby("source_file"):
            participants_by_source[str(source)] = df

    meetings_payload = _compute_meetings_payload(meetings, participants_by_source, has_config)

    if has_config and "is_internal" in participants.columns:
        internal = participants[participants["is_internal"]].copy()
    else:
        internal = participants.copy()

    return {
        "config": {
            "has_org_config": has_config,
            "org_name": org_name,
            "org_labels": {
                "level_1": org_labels.get("level_1", "Agency"),
                "level_2": org_labels.get("level_2", "Major Org"),
                "level_3": org_labels.get("level_3", "Sub Org"),
                "employee_type": org_labels.get("employee_type", "Status"),
            },
        },
        "meetings": meetings_payload,
        "histogram": _compute_histogram(internal, has_config),
        "major_org_stack": _compute_major_org_stack(internal) if has_config else [],
        "sub_org_by_major": _compute_sub_org_by_major(internal) if has_config else {},
        "trend": _compute_trend(meetings_payload),
        "trend_by_major_org": _compute_trend_by_major_org(internal, meetings_payload) if has_config else {"labels": [], "series": {}},
        "participants": _compute_participant_summary(internal, has_config),
        "palette": {
            "emp": EMP_COLOR,
            "ctr": CTR_COLOR,
            "org": ORG_PALETTE,
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
                    output_path: str | Path = "report.html",
                    title: str | None = None) -> Path:
    """Render the dashboard. Returns the output path.

    ``participants`` must already include a ``source_file`` column linking
    each row to a meeting from ``meetings``. The CLI handles this; tests
    can call ``_combine_participants`` if they have per-file frames.
    """
    payload = _build_payload(meetings, participants, config)
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
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>__TITLE__</title>
<style>
  :root {
    --bg: #ffffff;
    --fg: #1f2937;
    --muted: #6b7280;
    --border: #e5e7eb;
    --accent: #2a9d8f;
    --emp: #2a9d8f;
    --ctr: #e76f51;
    --row-alt: #f9fafb;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
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
    background: #f3f4f6;
    border-radius: 8px;
    padding: 0.9rem 1rem;
  }
  .tile .value { font-size: 1.4rem; font-weight: 600; }
  .tile .label { color: var(--muted); font-size: 0.85rem; margin-top: 0.15rem; }
  main { padding: 1.5rem 2rem 3rem; }
  section { margin-bottom: 2.5rem; }
  section h2 { font-size: 1.15rem; margin: 0 0 0.75rem; }
  .chart-wrap { position: relative; height: 320px; max-width: 980px; }
  .chart-wrap.tall { height: 420px; }
  table.data {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.92rem;
  }
  table.data th, table.data td {
    text-align: left;
    padding: 0.55rem 0.7rem;
    border-bottom: 1px solid var(--border);
  }
  table.data th {
    background: #f3f4f6;
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
  }
  table.data th::after { content: ""; margin-left: 0.3rem; opacity: 0.4; }
  table.data th[data-sort="asc"]::after { content: "▲"; opacity: 1; }
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
  details > summary {
    cursor: pointer;
    font-size: 1.15rem;
    font-weight: 600;
    list-style: none;
    padding: 0.4rem 0;
  }
  details > summary::-webkit-details-marker { display: none; }
  details > summary::before { content: "▶ "; display: inline-block; transition: transform 0.15s; }
  details[open] > summary::before { transform: rotate(90deg); }
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
<main>
  <section id="section-meetings">
    <h2>Meetings</h2>
    <table class="data" id="meetings-table">
      <thead><tr id="meetings-head"></tr></thead>
      <tbody></tbody>
    </table>
  </section>

  <section id="section-histogram">
    <h2>Attendance Duration Distribution</h2>
    <div class="chart-wrap"><canvas id="hist-chart"></canvas></div>
    <div class="note">Buckets are 5 minutes wide. Values capped at 60 min.</div>
  </section>

  <section id="section-major-stack" class="org-only">
    <h2 id="major-stack-title">By Major Org</h2>
    <div class="chart-wrap"><canvas id="major-stack-chart"></canvas></div>
  </section>

  <section id="section-drilldown" class="org-only">
    <h2 id="drilldown-title">Drilldown</h2>
    <div class="controls">
      <label for="major-org-picker">Select:</label>
      <select id="major-org-picker"></select>
    </div>
    <div class="chart-wrap"><canvas id="drilldown-chart"></canvas></div>
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

  <section id="section-participants">
    <details>
      <summary>Participant Detail</summary>
      <div class="controls">
        <input type="search" id="participant-search" placeholder="Search by name or org…">
        <span id="participant-count" class="note"></span>
      </div>
      <table class="data" id="participant-table">
        <thead><tr id="participants-head"></tr></thead>
        <tbody></tbody>
      </table>
    </details>
  </section>
</main>

<script>__CHART_JS__</script>
<script>
(function () {
  const DATA = __DATA_JSON__;
  const hasOrg = DATA.config.has_org_config;
  const labels = DATA.config.org_labels;
  const palette = DATA.palette;

  if (!hasOrg) document.body.classList.add("no-org");

  // ---- Header ----
  const meetings = DATA.meetings;
  const dates = meetings.map(m => m.date).filter(Boolean).sort();
  const totalParticipants = DATA.participants.length;
  const empTotal = DATA.participants.filter(p => p.employee_type === "EMP").length;
  const ctrTotal = DATA.participants.filter(p => p.employee_type === "CTR").length;
  const empCtrTotal = empTotal + ctrTotal;

  const subtitleParts = [];
  if (dates.length === 1) subtitleParts.push(dates[0]);
  else if (dates.length > 1) subtitleParts.push(`${dates[0]} → ${dates[dates.length - 1]}`);
  document.getElementById("page-subtitle").textContent = subtitleParts.join(" · ");

  const tiles = [
    { label: "Meetings", value: meetings.length },
    { label: "Unique participants", value: totalParticipants },
  ];
  if (hasOrg) {
    const empShare = empCtrTotal ? Math.round((empTotal / empCtrTotal) * 100) : 0;
    tiles.push({ label: `${labels.employee_type} (EMP/CTR)`, value: `${empTotal} / ${ctrTotal}` });
    tiles.push({ label: "EMP share", value: empShare + "%" });
  }
  const tilesEl = document.getElementById("summary-tiles");
  tiles.forEach(t => {
    const div = document.createElement("div");
    div.className = "tile";
    div.innerHTML = `<div class="value"></div><div class="label"></div>`;
    div.querySelector(".value").textContent = t.value;
    div.querySelector(".label").textContent = t.label;
    tilesEl.appendChild(div);
  });

  // ---- Meetings table ----
  const meetingCols = hasOrg
    ? [
        { key: "date", label: "Date" },
        { key: "meeting_title", label: "Meeting" },
        { key: "total_attendees", label: "Attendees", numeric: true },
        { key: "emp_count", label: "EMP", numeric: true },
        { key: "ctr_count", label: "CTR", numeric: true },
        { key: "avg_attendance_min", label: "Avg (min)", numeric: true },
        { key: "dropped_external", label: "External Dropped", numeric: true },
      ]
    : [
        { key: "date", label: "Date" },
        { key: "meeting_title", label: "Meeting" },
        { key: "total_attendees", label: "Attendees", numeric: true },
        { key: "avg_attendance_min", label: "Avg (min)", numeric: true },
      ];
  renderTable(document.getElementById("meetings-table"), meetingCols, meetings);

  // ---- Charts ----
  const histogramData = DATA.histogram;
  const histDatasets = hasOrg
    ? [
        { label: "EMP", data: histogramData.EMP, backgroundColor: palette.emp, stack: "stack" },
        { label: "CTR", data: histogramData.CTR, backgroundColor: palette.ctr, stack: "stack" },
      ]
    : [
        { label: "Attendees", data: histogramData.All, backgroundColor: palette.emp },
      ];
  new Chart(document.getElementById("hist-chart").getContext("2d"), {
    type: "bar",
    data: { labels: histogramData.labels, datasets: histDatasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { stacked: hasOrg, title: { display: true, text: "Attendance minutes (capped at 60)" } },
        y: { stacked: hasOrg, beginAtZero: true, title: { display: true, text: "Participant count" } },
      },
      plugins: { legend: { display: hasOrg } },
    },
  });

  if (hasOrg) {
    // Major-org stacked bar (horizontal)
    document.getElementById("major-stack-title").textContent = `By ${labels.level_2}`;
    const majorStack = DATA.major_org_stack;
    new Chart(document.getElementById("major-stack-chart").getContext("2d"), {
      type: "bar",
      data: {
        labels: majorStack.map(r => r.major_org),
        datasets: [
          { label: "EMP", data: majorStack.map(r => r.EMP), backgroundColor: palette.emp, stack: "s" },
          { label: "CTR", data: majorStack.map(r => r.CTR), backgroundColor: palette.ctr, stack: "s" },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        scales: { x: { stacked: true, beginAtZero: true }, y: { stacked: true } },
      },
    });

    // Drilldown
    document.getElementById("drilldown-title").textContent = `${labels.level_2} Drilldown`;
    const picker = document.getElementById("major-org-picker");
    const subOrgData = DATA.sub_org_by_major;
    const majors = Object.keys(subOrgData);
    majors.forEach(m => {
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = m;
      picker.appendChild(opt);
    });

    const drillCtx = document.getElementById("drilldown-chart").getContext("2d");
    let drillChart = null;
    function renderDrill(major) {
      const rows = subOrgData[major] || [];
      if (drillChart) drillChart.destroy();
      drillChart = new Chart(drillCtx, {
        type: "bar",
        data: {
          labels: rows.map(r => r.sub_org),
          datasets: [
            { label: "EMP", data: rows.map(r => r.EMP), backgroundColor: palette.emp, stack: "s" },
            { label: "CTR", data: rows.map(r => r.CTR), backgroundColor: palette.ctr, stack: "s" },
          ],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          scales: { x: { stacked: true, beginAtZero: true }, y: { stacked: true } },
        },
      });
    }
    if (majors.length) {
      renderDrill(majors[0]);
      picker.addEventListener("change", () => renderDrill(picker.value));
    }
  }

  // Attendance trend (stacked bar EMP/CTR per meeting)
  const trend = DATA.trend;
  const trendDatasets = hasOrg
    ? [
        { label: "EMP", data: trend.EMP, backgroundColor: palette.emp, stack: "s" },
        { label: "CTR", data: trend.CTR, backgroundColor: palette.ctr, stack: "s" },
      ]
    : [
        { label: "Attendees", data: trend.Total, backgroundColor: palette.emp },
      ];
  new Chart(document.getElementById("trend-chart").getContext("2d"), {
    type: "bar",
    data: { labels: trend.labels, datasets: trendDatasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { stacked: hasOrg },
        y: { stacked: hasOrg, beginAtZero: true, title: { display: true, text: "Attendees" } },
      },
      plugins: {
        legend: { display: hasOrg },
        tooltip: { callbacks: { afterTitle: (items) => trend.titles[items[0].dataIndex] || "" } },
      },
    },
  });

  if (hasOrg) {
    document.getElementById("trend-org-title").textContent = `Trend by ${labels.level_2}`;
    const tbm = DATA.trend_by_major_org;
    const orgs = Object.keys(tbm.series);
    new Chart(document.getElementById("trend-org-chart").getContext("2d"), {
      type: "line",
      data: {
        labels: tbm.labels,
        datasets: orgs.map((name, i) => ({
          label: name,
          data: tbm.series[name],
          borderColor: palette.org[i % palette.org.length],
          backgroundColor: palette.org[i % palette.org.length],
          tension: 0.25,
          fill: false,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "top" } },
        scales: { y: { beginAtZero: true, title: { display: true, text: "Attendees" } } },
      },
    });
  }

  // ---- Participant detail table ----
  const participantCols = hasOrg
    ? [
        { key: "name", label: "Name" },
        { key: "org_code", label: "Org Code" },
        { key: "major_org", label: labels.level_2 },
        { key: "sub_org", label: labels.level_3 },
        { key: "employee_type", label: labels.employee_type },
        { key: "sessions_attended", label: "Sessions", numeric: true },
        { key: "total_duration_min", label: "Total (min)", numeric: true },
        { key: "avg_duration_min", label: "Avg (min)", numeric: true },
      ]
    : [
        { key: "name", label: "Name" },
        { key: "sessions_attended", label: "Sessions", numeric: true },
        { key: "total_duration_min", label: "Total (min)", numeric: true },
        { key: "avg_duration_min", label: "Avg (min)", numeric: true },
      ];

  // Single source of truth for the search filter: applied on every repaint
  // (initial render, sort) so the active query survives a re-sort.
  const search = document.getElementById("participant-search");
  function applyParticipantSearch() {
    const q = search.value.toLowerCase();
    let shown = 0;
    document.querySelectorAll("#participant-table tbody tr").forEach(row => {
      const visible = !q || row.textContent.toLowerCase().includes(q);
      row.hidden = !visible;
      if (visible) shown += 1;
    });
    document.getElementById("participant-count").textContent =
      q ? `${shown} of ${DATA.participants.length} participants`
        : `${DATA.participants.length} participants`;
  }
  search.addEventListener("input", applyParticipantSearch);

  renderTable(document.getElementById("participant-table"), participantCols,
              DATA.participants, applyParticipantSearch);

  // ---- Table helpers ----
  function paintRows(table, columns, rows) {
    const tbody = table.tBodies[0];
    tbody.innerHTML = "";
    rows.forEach(r => {
      const tr = document.createElement("tr");
      columns.forEach(c => {
        const td = document.createElement("td");
        const v = r[c.key];
        td.textContent = (v === null || v === undefined) ? "" : v;
        if (c.numeric) td.style.textAlign = "right";
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  }

  function renderTable(table, columns, rows, afterRender) {
    const thead = table.tHead.querySelector("tr");
    thead.innerHTML = "";
    columns.forEach((c, idx) => {
      const th = document.createElement("th");
      th.textContent = c.label;
      th.addEventListener("click", () => sortBy(table, columns, rows, idx, c, afterRender));
      thead.appendChild(th);
    });
    paintRows(table, columns, rows);
    if (afterRender) afterRender();
  }

  function sortBy(table, columns, rows, idx, col, afterRender) {
    const thead = table.tHead.querySelector("tr");
    const th = thead.children[idx];
    const current = th.dataset.sort;
    const next = current === "asc" ? "desc" : "asc";
    Array.from(thead.children).forEach(other => delete other.dataset.sort);
    th.dataset.sort = next;
    const direction = next === "asc" ? 1 : -1;
    const sorted = rows.slice().sort((a, b) => {
      const av = a[col.key];
      const bv = b[col.key];
      if (col.numeric) return ((av || 0) - (bv || 0)) * direction;
      return String(av || "").localeCompare(String(bv || "")) * direction;
    });
    paintRows(table, columns, sorted);
    if (afterRender) afterRender();
  }
})();
</script>
</body>
</html>
"""
