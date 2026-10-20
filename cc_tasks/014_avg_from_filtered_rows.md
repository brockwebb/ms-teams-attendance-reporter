# CC Task: Compute Avg Attendance From Filtered Rows

## Priority: HIGH
## Status: READY
## Depends on: 013_min_threshold_fleeting_birds_drilldown_sync (COMPLETE)

## Objective
The "Avg (min)" column in the meetings table uses `m.avg_attendance_min` from the Teams CSV metadata header. This is a static value that ignores the minimum attendance threshold filter — so when you filter out <5min attendees, the average doesn't change.

Fix: compute the average from the actual filtered rows for each meeting.

## Implementation — JS change in `_HTML_TEMPLATE`

In `renderMeetingsTable`, replace this line in the `tableRows` mapping:

```javascript
avg_attendance_min: m.avg_attendance_min,
```

With:

```javascript
avg_attendance_min: rs.length > 0
  ? Math.round(rs.reduce((sum, r) => sum + r.minutes, 0) / rs.length * 10) / 10
  : 0,
```

That's it. One line. The `rs` variable already contains only the filtered rows for that meeting.

## Steps
1. Edit `src/reporter.py` — find the `avg_attendance_min: m.avg_attendance_min` line in the `renderMeetingsTable` JS function and replace it
2. Regenerate: `python -m src.cli data/synthetic/ --config config/config.yaml`
3. Verify:
   - With threshold at 0, avg should be close to (but not necessarily identical to) the old metadata value — small differences are expected since the metadata value is computed by Teams before any capping or aggregation
   - Set threshold to 5 — avg should increase noticeably as short-duration attendees are excluded
   - Set threshold back to 0 — avg returns to baseline
4. Commit: `git add -A && git commit -m "Compute avg attendance from filtered rows, not static metadata"`
5. Push: `git push`

## Acceptance Criteria
- [ ] Avg attendance column recomputes when threshold changes
- [ ] Avg is computed from filtered rows, not metadata
- [ ] Avg shows one decimal place
- [ ] No regressions
- [ ] Committed and pushed
