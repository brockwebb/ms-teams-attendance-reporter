# CC Task: Dashboard Cleanup

## Priority: HIGH
## Status: READY
## Depends on: 004_migrate_config_to_yaml (COMPLETE)

## Objective
Clean up the HTML dashboard report to remove PII, hide data-cleaning internals, and reorder sections to lead with what matters.

## Changes

### 1. Meeting cap from config
`cap_minutes` is already in `config/config.yaml` and the enricher reads it. Verify the reporter uses `config['cap_minutes']` for the histogram cap label (e.g., "Capped at 60 min") rather than a hardcoded value. If it's hardcoded anywhere in `src/reporter.py`, fix it to read from config. The CLI `--cap-minutes` flag should override the config value if provided.

### 2. Remove ALL individual names from the report
- Delete the Participant Detail Table section entirely (Section 8 — the searchable/sortable table with Name, Org Code, etc.)
- Grep `src/reporter.py` for any other place individual names appear in the HTML output. Remove them all. No names in tooltips, no names in hover text, no names in data attributes.
- The underlying processed data can still have names (for the pipeline's internal use), but the HTML output must be name-free.

### 3. Remove "Dropped External" count from display
- The meeting summary table currently shows how many external/non-org participants were dropped. Remove this column from the visible table.
- The drop logic stays in the pipeline (it's data cleaning, not reporting). Just don't surface it in the HTML.

### 4. Reorder: attendance metrics before duration histogram
Current order has the duration histogram prominent. Reorder the dashboard sections to:

1. Summary header (total meetings, unique participants, EMP/CTR split, date range)
2. Meeting summary table (date, title, total attendees, EMP/CTR counts, avg duration) — NO dropped-external column
3. EMP/CTR by major org (horizontal stacked bar)
4. Attendance trend over time (stacked bar/area by meeting date)
5. Trend by major org (line chart)
6. Major org drilldown (dropdown → sub-org breakdown)
7. Attendance duration histogram (moved to end — it's secondary)

### 5. No participant detail table
Already covered by item 2 — just confirming: the entire section is deleted, not collapsed or hidden.

## Steps
1. Edit `src/reporter.py` to implement all changes above
2. Regenerate report: `python -m src.cli data/synthetic/ --config config/config.yaml --output report.html`
3. Open `report.html` in browser and verify:
   - No names anywhere in the page (search the HTML source for character names like "Bugz" to confirm)
   - No "dropped" column in meeting table
   - Section order matches the spec above
   - Histogram cap label reads from config value
4. Commit: `git add -A && git commit -m "Dashboard cleanup: remove names, reorder sections, hide internals"`
5. Push: `git push`

## Acceptance Criteria
- [ ] Zero individual names in the HTML output (grep the generated HTML for any ACNE character name — must find nothing)
- [ ] No "dropped external" column in meeting summary table
- [ ] Dashboard section order: summary → meeting table → org bar → trend → org trend → drilldown → histogram
- [ ] Histogram cap label uses config value, not hardcoded
- [ ] Participant detail table completely removed
- [ ] Report still generates and renders correctly
- [ ] Committed and pushed
