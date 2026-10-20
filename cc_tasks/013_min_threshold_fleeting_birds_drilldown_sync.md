# CC Task: Minimum Attendance Threshold Filter + Fleeting Birds View + Drilldown Sync

## Priority: HIGH
## Status: READY
## Depends on: 012_sub_org_alias_rollup (COMPLETE)

## Objective
Four changes to the HTML dashboard:

1. **Minimum attendance threshold** — a numeric input in the filter bar that excludes participants under N minutes from all charts, tiles, and table aggregations. Default 0 (show everyone). The filter is view-only; CSV and underlying data are unchanged.

2. **All charts respect the threshold** — the threshold feeds into `filterRows()` so every downstream renderer automatically excludes short-duration attendees.

3. **Fleeting Birds section** — a new chart section showing the excluded attendees (those *below* the threshold) broken out by directorate. Only visible when threshold > 0. Answers: "who did I just filter out?"

4. **Drilldown picker sync** — when a directorate is selected in the top-level filter bar, the drilldown section's own picker should sync to that value and disable (since the choice is already made). When the top filter is "All", the drilldown picker is active as before.

## Part 1: Minimum Attendance Threshold in Filter Bar

### HTML change in `_HTML_TEMPLATE`

Add to the filter bar div, after the division filter label:

```html
<label>
  Min. attendance
  <input id="filter-min-minutes" type="number" min="0" max="60" value="0" step="1" style="width:70px;">
  <span style="font-size:0.85rem;color:var(--muted);">min</span>
</label>
```

### JS changes

Add `minMinutes` to the state object:
```javascript
const state = { meeting: 'ALL', directorate: 'ALL', division: 'ALL', minMinutes: 0 };
```

Wire up the input:
```javascript
const minMinInput = document.getElementById('filter-min-minutes');
minMinInput.addEventListener('change', e => {
  state.minMinutes = Math.max(0, parseInt(e.target.value) || 0);
  redraw();
});
```

Add to the reset handler:
```javascript
state.minMinutes = 0;
minMinInput.value = 0;
```

## Part 2: Threshold Applied in filterRows

Modify `filterRows` to accept and apply the threshold:

```javascript
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
    if (st.minMinutes > 0 && r.minutes < st.minMinutes) return false;
    return true;
  });
}
```

That's it — every chart already consumes the output of `filterRows`, so the threshold propagates everywhere automatically.

## Part 3: Fleeting Birds Section

### HTML

Add a new section after the histogram section (before `</main>`):

```html
<section id="section-fleeting" class="org-only" style="display:none;">
  <h2>Fleeting Attendees</h2>
  <div class="note" id="fleeting-note"></div>
  <div class="chart-wrap"><canvas id="fleeting-chart"></canvas></div>
</section>
```

### JS — new renderer

Add `renderFleetingBirds` function and call it from `redraw()`.

The function needs the *excluded* rows — those that match meeting/directorate/division filters but fall *below* the threshold:

```javascript
function getExcludedRows(rows, st) {
  // Apply all filters EXCEPT minMinutes, then keep only those below threshold
  if (st.minMinutes <= 0) return [];
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
    return r.minutes < st.minMinutes;
  });
}

function renderFleetingBirds(excludedRows) {
  const section = document.getElementById('section-fleeting');
  if (!section) return;
  if (excludedRows.length === 0) {
    section.style.display = 'none';
    destroyChart('fleeting-chart');
    return;
  }
  section.style.display = '';
  const noteEl = document.getElementById('fleeting-note');
  const uniqueExcluded = uniquePids(excludedRows);
  noteEl.textContent = `${excludedRows.length} attendance records (${uniqueExcluded} unique participants) below the ${state.minMinutes}-minute threshold.`;

  const grouped = groupBy(excludedRows, 'major_org');
  const items = Object.entries(grouped).map(([org, rs]) => ({
    major_org: org,
    EMP: countByType(rs, labels.employee),
    CTR: countByType(rs, labels.contractor),
    total: rs.length,
  })).sort((a, b) => b.total - a.total);

  ensureChart('fleeting-chart', {
    type: 'bar',
    data: {
      labels: items.map(r => r.major_org),
      datasets: [
        { label: labels.employee, data: items.map(r => r.EMP), backgroundColor: palette.emp, stack: 's' },
        { label: labels.contractor, data: items.map(r => r.CTR), backgroundColor: palette.ctr, stack: 's' },
      ],
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      scales: {
        x: { stacked: true, beginAtZero: true, ticks: { precision: 0 } },
        y: { stacked: true },
      },
    },
  });
}
```

Update `redraw()`:
```javascript
function redraw() {
  const rows = filterRows(DATA.rows, state);
  const excluded = getExcludedRows(DATA.rows, state);
  renderHeaderTiles(rows);
  renderMeetingsTable(rows);
  renderMajorStack(rows);
  renderTrend(rows);
  renderTrendByOrg(rows);
  renderDrilldown(rows);
  renderHistogram(rows);
  renderFleetingBirds(excluded);
}
```

## Part 4: Drilldown Picker Sync

In `renderDrilldown`, after building the picker options, add sync logic:

```javascript
// If top-level filter already picks a directorate, lock the drilldown picker
if (state.directorate !== 'ALL') {
  picker.value = state.directorate;
  picker.disabled = true;
  paint(state.directorate);
} else {
  picker.disabled = false;
  picker.value = initial;
  paint(initial);
}
```

This disables the redundant picker when the top filter already narrows to one directorate, and re-enables it when the top filter is "All".

## Steps
1. Edit `src/reporter.py` — apply all HTML and JS changes to `_HTML_TEMPLATE`
2. Regenerate with synthetic data: `python -m src.cli data/synthetic/ --config config/config.yaml`
3. Open the report and verify:
   - Filter bar shows "Min. attendance" input, defaults to 0
   - Setting it to 5 removes short-duration attendees from ALL charts and tiles
   - Fleeting Birds section appears when threshold > 0, disappears when 0
   - Fleeting Birds shows excluded attendees by directorate with count note
   - Drilldown picker syncs to top-level directorate selection and disables
   - Drilldown picker re-enables when top filter is "All"
   - Reset button clears the threshold back to 0
   - Histogram responds to directorate filter
4. Commit: `git add -A && git commit -m "Add minimum attendance threshold, Fleeting Birds view, sync drilldown picker"`
5. Push: `git push`

## Acceptance Criteria
- [ ] Min. attendance input in filter bar, default 0
- [ ] All charts/tiles/table exclude attendees below threshold
- [ ] Fleeting Birds section shows excluded attendees by directorate (org-only)
- [ ] Fleeting Birds hidden when threshold is 0
- [ ] Fleeting Birds note shows count of excluded records and unique participants
- [ ] Drilldown picker syncs to top-level directorate filter
- [ ] Drilldown picker disabled when directorate is selected, enabled when "All"
- [ ] Reset clears threshold to 0 and hides Fleeting Birds
- [ ] No regressions in existing charts
- [ ] Committed and pushed

## Design Notes
- The threshold is a VIEW filter, not data modification. CSV export is unaffected.
- `getExcludedRows` duplicates some filter logic from `filterRows` — this is intentional.
  Extracting a shared filter-minus-threshold function would be cleaner but harder for
  Claude Code to implement correctly in one pass. If it bothers you later, refactor.
- The Fleeting Birds chart reuses the same stacked horizontal bar style as the
  By Directorate chart for visual consistency.
- The `min` attribute on the input prevents negative values; `step="1"` keeps it to
  whole minutes. Users can still type decimals — `parseInt` in the handler floors them.
