# Task 016 — Stable PID + Multi-Session Attendance Analysis

## Overview

Two changes in one task:
1. **Stable PID**: Replace sequential pid assignment with a deterministic hash of the email address, so the same person gets the same pid across all sessions/runs.
2. **Multi-Session Section**: Add a new dashboard section showing cross-session attendance patterns (histogram + summary tiles).

---

## Part 1: Stable PID via Email Hash

### File: `src/reporter.py`

#### Change `_identity_key_series` (line ~91)

Replace the current implementation:

```python
def _identity_key_series(internal: pd.DataFrame, has_config: bool) -> pd.Series:
    if has_config and "clean_name" in internal.columns:
        return internal["clean_name"].fillna(internal["Name"]).astype(str)
    return internal["Name"].astype(str)
```

With:

```python
def _identity_key_series(internal: pd.DataFrame, has_config: bool) -> pd.Series:
    """Stable identity key derived from email address.

    Uses Email when available (preferred — stable across sessions),
    falls back to clean_name or Name. The key is used to build a
    deterministic pid via hashing, so the same person gets the same
    pid regardless of file order or run.
    """
    if "Email" in internal.columns:
        email = internal["Email"].astype(str).str.strip().str.lower()
        # Fall back to name when email is empty/missing
        if has_config and "clean_name" in internal.columns:
            fallback = internal["clean_name"].fillna(internal["Name"]).astype(str)
        else:
            fallback = internal["Name"].astype(str)
        return email.where(email.ne("") & email.ne("nan"), fallback)
    if has_config and "clean_name" in internal.columns:
        return internal["clean_name"].fillna(internal["Name"]).astype(str)
    return internal["Name"].astype(str)
```

#### Change pid assignment in `_build_rows` (line ~112)

Replace the sequential assignment:

```python
    pid_map: dict[str, int] = {}
    for k in key_series:
        if k not in pid_map:
            pid_map[k] = len(pid_map)
```

With deterministic hashing:

```python
    import hashlib
    def _hash_pid(key: str) -> int:
        """Deterministic integer pid from a string key."""
        return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:12], 16)
    pid_map: dict[str, int] = {}
    for k in key_series:
        if k not in pid_map:
            pid_map[k] = _hash_pid(k)
```

Note: Move `import hashlib` to the top of the file with the other imports.

#### Update docstring at top of file

Update the docstring to reflect that `pid` is now a deterministic hash of email, not a sequential integer. Change:

> ``pid`` is a sequential integer assigned by Python — used to dedup participants across meetings without exposing names.

To:

> ``pid`` is a deterministic hash of the participant's email address — stable across runs and sessions, enabling cross-session dedup. No names, emails, or other PII appear anywhere in the rendered HTML.

---

## Part 2: Multi-Session Attendance Section

### File: `src/reporter.py` — HTML template

Add a new section **after** `section-histogram` and **before** `section-fleeting`. This section should be visible regardless of org config (not class="org-only").

```html
  <section id="section-multi-session">
    <h2>Repeat Attendance</h2>
    <div class="note" id="multi-session-note" style="display:none;"></div>
    <div id="multi-session-tiles" class="tiles"></div>
    <div class="chart-wrap"><canvas id="multi-session-chart"></canvas></div>
  </section>
```

### File: `src/reporter.py` — JavaScript

Add a new renderer function `renderMultiSession(rows)` following the existing renderer patterns. Call it from the `redraw()` function alongside the other renderers.

#### Logic:

```javascript
function renderMultiSession(rows) {
    const meetingCount = DATA.meetings.length;
    const noteEl = document.getElementById('multi-session-note');

    // Single meeting: show note, hide chart
    if (meetingCount <= 1) {
        noteEl.textContent = 'Multi-session analysis requires 2+ meetings loaded.';
        noteEl.style.display = '';
        setEmpty('section-multi-session', true);
        return;
    }
    noteEl.style.display = 'none';

    // Group by pid → set of source_files attended
    const pidSessions = {};
    rows.forEach(r => {
        if (!pidSessions[r.pid]) pidSessions[r.pid] = { files: new Set(), type: r.employee_type };
        pidSessions[r.pid].files.add(r.source_file);
    });

    // Build histogram: for each session count (1..meetingCount), how many pids
    const empBuckets = new Array(meetingCount).fill(0);
    const ctrBuckets = new Array(meetingCount).fill(0);
    const allBuckets = new Array(meetingCount).fill(0);
    let totalUnique = 0;

    Object.values(pidSessions).forEach(p => {
        const n = p.files.size;  // sessions attended (1-based)
        const idx = n - 1;       // array index (0-based)
        allBuckets[idx]++;
        if (p.type === labels.employee) empBuckets[idx]++;
        else if (p.type === labels.contractor) ctrBuckets[idx]++;
        totalUnique++;
    });

    // Summary tiles
    const tilesEl = document.getElementById('multi-session-tiles');
    tilesEl.innerHTML = '';
    const allSessions = allBuckets[meetingCount - 1];
    const multiCount = allBuckets.reduce((sum, v, i) => i > 0 ? sum + v : sum, 0);
    const tiles = [
        { label: 'Sessions Loaded', value: meetingCount },
        { label: 'Total Records', value: rows.length },
        { label: 'Unique Participants', value: totalUnique },
        { label: 'Attended 2+', value: multiCount },
        { label: 'All Sessions', value: allSessions },
    ];
    tiles.forEach(t => {
        const div = document.createElement('div'); div.className = 'tile';
        const v = document.createElement('div'); v.className = 'value'; v.textContent = t.value;
        const l = document.createElement('div'); l.className = 'label'; l.textContent = t.label;
        div.appendChild(v); div.appendChild(l);
        tilesEl.appendChild(div);
    });

    // Bar chart
    const barLabels = [];
    for (let i = 1; i <= meetingCount; i++) barLabels.push(i.toString());

    setEmpty('section-multi-session', false);
    const datasets = hasOrg
        ? [
            { label: labels.employee, data: empBuckets, backgroundColor: palette.emp, stack: 's' },
            { label: labels.contractor, data: ctrBuckets, backgroundColor: palette.ctr, stack: 's' },
          ]
        : [{ label: 'Participants', data: allBuckets, backgroundColor: palette.emp }];

    ensureChart('multi-session-chart', {
        type: 'bar',
        data: { labels: barLabels, datasets: datasets },
        options: {
            responsive: true,
            plugins: {
                title: { display: true, text: 'Participants by Number of Sessions Attended' },
                legend: { display: hasOrg },
            },
            scales: {
                x: { title: { display: true, text: 'Sessions Attended' } },
                y: {
                    title: { display: true, text: 'Participants' },
                    beginAtZero: true,
                    ticks: { stepSize: 1, callback: v => Number.isInteger(v) ? v : '' },
                },
            },
        },
    });
}
```

#### Add to `redraw()`:

Find the `redraw()` function. At the end, after the existing renderer calls (after `renderFleeting` or wherever the last renderer is called), add:

```javascript
    renderMultiSession(filtered);
```

The `filtered` variable is the threshold-filtered rows — this ensures the multi-session view respects the min-attendance filter.

---

## Testing

Run against synthetic data (4 ACNE Corp meetings):

```bash
cd /Users/brock/Documents/GitHub/ms-teams-attendance-reporter
python -m src.cli data/synthetic/ --config config/config.yaml --output output/
```

Verify:
1. Dashboard loads without JS errors
2. "Repeat Attendance" section appears with histogram (4 sessions in synthetic data)
3. Histogram x-axis shows 1, 2, 3, 4
4. Summary tiles show correct counts
5. Changing filters (meeting, directorate, threshold) updates the section
6. CSV export still works
7. Stacked bars show EMP/CTR split

---

## Do NOT change
- CSS color palette
- Other section renderers
- CSV export logic (pid format change is fine — it's just an integer column)
- config.yaml structure
