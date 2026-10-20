# CC Task: Report Title From Config

## Priority: LOW
## Status: READY
## Depends on: 014_avg_from_filtered_rows (COMPLETE)

## Objective
Add a `report_title` field to the YAML config so the report title is set once, not passed via `--title` every run. CLI `--title` still overrides if provided.

## Config Change

Add to config YAML (anywhere at the top level):

```yaml
report_title: "MS Copilot Training Report"
```

## Implementation

### `src/reporter.py`

In `generate_report`, change the title resolution:

```python
    if title is None:
        title = (config or {}).get("report_title") or None
    if title is None:
        org_name = payload["config"]["org_name"]
        title = f"{org_name} Attendance Report" if org_name else DEFAULT_TITLE
```

That's it. The CLI already passes `args.title` (which is `None` when not provided), so the fallback chain is: `--title` flag → `config.report_title` → `"{org_name} Attendance Report"` → `"Teams Attendance Report"`.

### Note
`_build_payload` is called before the title is resolved, and `payload["title"]` is set after. This is fine — title is only used for the HTML `<title>` and `<h1>`, not the data payload.

## Steps
1. Edit `src/reporter.py` — change the title resolution block in `generate_report` as shown above
2. Regenerate with synthetic config (no `report_title` field) — verify title still defaults to org_name-based title
3. Add `report_title: "Test Title"` to `config/config.yaml`, regenerate — verify title shows "Test Title"
4. Run with `--title "Override"` — verify CLI wins over config
5. Remove the test title from `config/config.yaml`
6. Commit: `git add -A && git commit -m "Support report_title in config YAML"`
7. Push: `git push`

## Acceptance Criteria
- [ ] `report_title` in config sets the report title
- [ ] `--title` CLI flag overrides config value
- [ ] Omitting both falls back to existing behavior (org_name or default)
- [ ] No regressions
- [ ] Committed and pushed
