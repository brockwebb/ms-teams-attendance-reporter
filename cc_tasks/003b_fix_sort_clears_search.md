# CC Task: Fix Participant Table Sort Clearing Search Filter

## Priority: LOW
## Status: READY
## Depends on: 003_implement_reporter_cli (COMPLETE)
## Date: 2026-05-13

## Objective
Sorting the Participant Detail table by column header currently wipes
any active search filter — every row becomes visible again and the
"X of N participants" counter resets. Fix it so sort composes with
search: after a header click, the displayed set should be the filtered
set in the new order, with the counter still accurate.

## Context
- Bug lives in `src/reporter.py`, inside the inline dashboard JS
  embedded in `_HTML_TEMPLATE`.
- Root cause: there are two row-painting paths — `renderTable()` for the
  initial render and `sortBy()` for click-to-sort. Both replace
  `tbody.innerHTML` with freshly-built `<tr>` elements (default visible).
  The search handler hides rows via `row.hidden = true` based on text
  match, but `sortBy` doesn't know the filter exists, so its freshly
  painted rows are all visible regardless of the search box's contents.
- Scope: participants table only. The meetings table has no search box
  attached, so the bug doesn't manifest there.

## Steps
1. Refactor: extract a single `paintRows(table, columns, rows)` helper
   that owns the tbody-clear-and-rebuild logic. Both `renderTable` and
   `sortBy` call it (eliminates a duplicate <tr>/<td> build block).
2. Add an optional `afterRender` callback parameter to both
   `renderTable` and `sortBy`. Invoke it after every repaint.
3. Promote the search-input handler body to a named function
   `applyParticipantSearch()`. The input listener calls it; pass it
   as `afterRender` to the participant table's `renderTable`.
4. Move the visible-count text logic entirely into
   `applyParticipantSearch` so there is one source of truth. Empty
   query → "N participants"; non-empty → "X of N participants".
5. Reorder so the `search` element constant is declared *before* the
   participant table is rendered (otherwise `applyParticipantSearch`
   references it before assignment).
6. Regenerate both reports
   (`python -m src.cli ... --output data/processed/report.html` and
   the generic variant) and re-run the structural validator from
   task 003 to confirm nothing else broke.
7. Commit and push.

## Acceptance Criteria
- [ ] Type a query in the participant search → click a column header →
      the filtered set is preserved, sorted within the visible rows.
- [ ] "X of N participants" stays accurate after sort.
- [ ] Empty query renders show "N participants" (no "X of N" form).
- [ ] Structural validation from task 003 still passes for both reports.
- [ ] Meetings table sort behavior unchanged (still works, no search).
- [ ] Committed and pushed.

## What NOT to do
- Don't add a JS dependency — keep it vanilla.
- Don't fix this with a synthetic `dispatchEvent('input')` inside
  `sortBy`. The callback-based fix is local and easier to reason about.
- Don't touch parser / enricher / CLI — this is presentation-layer only.
- Don't widen scope (e.g., don't add column-pinned sort persistence,
  multi-key sort, or remembered sort across reloads). One fix, one PR.
