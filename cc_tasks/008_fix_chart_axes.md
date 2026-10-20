# CC Task: Fix Chart Axis Scaling

## Priority: HIGH
## Status: READY
## Depends on: 007_filtering_and_layout (COMPLETE)

## Objective
Fix Y-axis scaling on all charts. Attendee counts are integers — axes should show integers, not decimals like 0.2, 0.4, 1.8.

## Problem
Chart.js auto-scales Y-axes based on data range. With small synthetic data (2-10 people per org per meeting), the axis renders decimal ticks (0.2, 0.4, 0.6...) which is nonsensical for human counts. The "Attendance Trend" chart may also be rendering empty/zero when it shouldn't.

## Fix

In `src/reporter.py`, find every Chart.js chart configuration and apply these Y-axis settings:

### For all count-based charts (attendance trend, trend by directorate, EMP/CTR bar, directorate drilldown):
```javascript
scales: {
    y: {
        beginAtZero: true,
        ticks: {
            precision: 0,    // no decimal places
            stepSize: 1      // integer steps (Chart.js will increase step if range is large)
        }
    }
}
```

Note: `stepSize: 1` works fine for small counts. For large counts (500+ attendees), Chart.js is smart enough to override stepSize when it would create too many ticks — but verify this doesn't create 500 tick marks. If it does, remove `stepSize` and keep only `precision: 0`, which forces integers but lets Chart.js pick the interval.

### For the duration histogram:
Y-axis is also a count (number of people in each duration bucket). Same fix: `precision: 0`.

### For the attendance trend (stacked area/bar over time):
- Verify the data binding is correct — the chart should show total attendees per meeting, not zero
- `stacked: true` on both x and y if it's a stacked bar
- Check that the dataset `data` arrays actually have values (not all zeros)

## Debugging the Zero Chart
Open the generated HTML, open browser dev console, look for JS errors. If the attendance trend is showing 0:
- Check the dataset objects in the chart config — are the `data` arrays populated?
- Check if the filter logic is accidentally filtering everything out on initial load
- The default filter state should be "All" for all three dropdowns, showing all data

## Steps
1. Edit `src/reporter.py` — fix Y-axis config on all charts
2. Regenerate: `python -m src.cli data/synthetic/ --config config/config.yaml --output output/report.html`
3. Open in browser, verify:
   - All Y-axes show integers only (1, 2, 3... not 0.2, 0.4...)
   - Attendance trend chart shows actual data (not empty/zero)
   - All charts render correctly with no filter selected
   - Charts still look correct when filters are applied
   - No JS console errors
4. Commit: `git add -A && git commit -m "Fix chart Y-axis scaling: integer ticks, fix empty trend chart"`
5. Push: `git push`

## Acceptance Criteria
- [ ] No decimal values on any Y-axis (all counts are integers)
- [ ] All Y-axes start at 0
- [ ] Attendance trend chart shows data on default load (no filters)
- [ ] All charts render correctly with and without filters
- [ ] No JS console errors in browser
- [ ] Committed and pushed
