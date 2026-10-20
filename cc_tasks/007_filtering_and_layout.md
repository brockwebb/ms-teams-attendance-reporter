# CC Task: Dashboard Filtering and Layout Fixes

## Priority: HIGH
## Status: READY
## Depends on: 006_census_color_palette (COMPLETE)

## Objective
Fix table layout issues, add global filtering (meeting, directorate, sub-org), and add a gitignored output directory.

---

## 1. Output Directory

Create `output/` directory at project root with a `.gitkeep`. Add to `.gitignore`:
```
output/**
!output/.gitkeep
```

Update CLI default output path from `report.html` to `output/report.html`. Update README and CLAUDE.md accordingly.

---

## 2. Fix Meeting Summary Table Layout

The current table has a spacing/alignment problem: the Meeting column is too wide and numeric columns are cramped to the right.

Fix:
- Meeting title column: reasonable max-width, allow text wrapping
- Date column: fixed width (~110px), left-aligned
- Numeric columns (Attendees, EMP, CTR, Avg min): fixed width (~90-100px), **right-aligned** (numbers should always be right-aligned)
- Use `table-layout: fixed` or explicit column widths
- Add subtle cell padding (8-12px)
- Ensure the table doesn't stretch to 100% viewport width — max-width ~1000px with auto margins

---

## 3. Global Filter Controls

Add a filter bar at the top of the dashboard (below the summary header, above all charts). Three dropdown filters:

### Filter: Meeting
- Options: "All Meetings" (default) + one entry per meeting (format: "YYYY-MM-DD — Title")
- When a specific meeting is selected, ALL charts and tables below filter to that meeting's data only
- The meeting summary table highlights the selected row (or shows only that row)

### Filter: Directorate (Major Org)
- Options: "All Directorates" (default) + one entry per major org from the data
- When selected, all charts filter to participants from that directorate
- The "By Directorate" stacked bar highlights/isolates the selected one
- The drilldown auto-opens to show sub-orgs of the selected directorate
- Use the label from config (`labels.level_1`) for the dropdown label

### Filter: Division (Sub-Org)
- Options: "All Divisions" (default) + dynamically populated based on selected Directorate
- If no Directorate is selected, show all sub-orgs grouped by directorate (optgroup)
- If a Directorate IS selected, show only that directorate's sub-orgs
- When selected, all charts filter to participants from that specific sub-org
- Use the label from config (`labels.level_2`) for the dropdown label

### Filter Interaction Logic
- Filters are **cascading**: selecting a Directorate narrows the Division dropdown. Selecting a Division doesn't change the Directorate dropdown (it stays on the parent).
- Selecting a Division auto-sets the Directorate to its parent (if "All" was selected)
- Clearing a Directorate clears the Division selection too
- Meeting filter is independent of org filters. They combine: "Show me Agents session, ROCKETWORKS only" = both filters active
- All charts, tables, and KPIs in the summary header update reactively when filters change

### Which Filters Apply to Which Sections

| Section | Meeting | Directorate | Division |
|---------|---------|-------------|----------|
| Summary KPIs (header) | ✓ | ✓ | ✓ |
| Meeting summary table | ✓ (highlight/filter rows) | ✓ (recount per meeting) | ✓ |
| EMP/CTR by Directorate bar | ✓ | ✓ (highlight) | ✓ |
| Attendance trend over time | ✓ (highlight point) | ✓ | ✓ |
| Trend by Directorate | ✓ | ✓ (highlight line) | ✓ |
| Directorate drilldown | ✓ | ✓ (auto-select) | ✓ (highlight) |
| Duration histogram | ✓ | ✓ | ✓ |

### Implementation Notes
- The data is already baked into the HTML as a JSON blob. Filtering happens client-side in JavaScript — no re-running the pipeline.
- All chart redraw logic must handle the case where the filtered dataset is empty (show "No data for selection" rather than a broken chart).
- Filter state should be reflected in a URL hash or query param so the view can be bookmarked/shared (nice to have, not required).
- Keep the filter bar compact — one row of dropdowns with labels inline. Don't let it dominate the page.

### Filter Bar Styling
- Background: very light grey `#F5F5F5` or white with a subtle bottom border
- Dropdown labels: Navy `#112E51`, using config labels
- Dropdowns: standard native HTML `<select>` elements — don't over-engineer custom dropdowns
- Position: sticky at top so filters remain visible when scrolling (optional but nice)

---

## 4. Duration Histogram Filter Behavior

The histogram is the one chart where all three filters matter most:
- **No filters**: shows all attendance durations across all meetings
- **Meeting selected**: shows duration distribution for just that session
- **Directorate selected**: shows durations for that org
- **Division selected**: shows durations for that sub-org
- **Multiple filters**: intersection (e.g., "Agents session + ROCKETWORKS" = only ROCKETWORKS people at the Agents session)

The histogram should always show the EMP/CTR stacked breakdown regardless of filter state.

---

## Steps
1. Create `output/` directory with `.gitkeep`, update `.gitignore`
2. Update CLI default output path to `output/report.html`
3. Fix the meeting summary table column widths and alignment in `src/reporter.py`
4. Implement the three-dropdown filter bar
5. Wire all charts to respond to filter changes
6. Test with synthetic data:
   - Default view (all filters on "All") looks correct
   - Selecting a single meeting shows only that meeting's data
   - Selecting a directorate filters org charts
   - Selecting a division narrows further
   - Combining meeting + directorate works
   - Empty filter results show graceful message, not broken charts
7. Verify the table layout is fixed (right-aligned numbers, reasonable column widths)
8. Update README if the output path changed
9. Commit: `git add -A && git commit -m "Add dashboard filtering, fix table layout, add output dir"`
10. Push: `git push`

## Acceptance Criteria
- [ ] `output/` directory exists, gitignored except .gitkeep
- [ ] CLI defaults to `output/report.html`
- [ ] Meeting summary table has proper column widths and right-aligned numbers
- [ ] Three filter dropdowns visible at top of dashboard
- [ ] Meeting filter controls all sections
- [ ] Directorate filter cascades to Division dropdown
- [ ] Division filter narrows data within selected Directorate
- [ ] All charts update reactively on filter change
- [ ] Duration histogram respects all three filters
- [ ] Empty filter combinations show graceful "no data" state
- [ ] Filter dropdown labels use config labels (level_1, level_2)
- [ ] Committed and pushed
