# CC Task: Improve Unmapped Org Code Handling

## Priority: MEDIUM
## Status: READY
## Depends on: 009_timestamped_outputs_and_csv (COMPLETE)

## Objective
Two fixes to org code handling:
1. **Bug fix**: `map_major()` in `enrich_participants` doesn't guard against pandas NaN (only checks `None`), so external participants whose `classify_name` returns `None` produce `org_code: NaN` in the pandas Series. This NaN passes the `if code is None` check, misses all lookups, and gets added to `unmapped` as the string `"nan"`. Fix by checking for both None and NaN.
2. **Feature**: Surface unmapped codes with enough context to update the config — print each unmapped code with a count and example name, then offer a summary block the user can paste into their YAML.

## Part 1: Fix NaN Guard in enricher.py

In `enrich_participants()`, the two inner functions `map_major` and `map_sub` only check `if code is None`. Pandas converts `None` → `NaN` in mixed-type Series, so this check misses NaN values.

### Change in `src/enricher.py`

Replace the `map_major` function inside `enrich_participants`:

```python
    def map_major(code):
        if code is None or (isinstance(code, float) and pd.isna(code)):
            return None
        if code in code_to_major:
            return code_to_major[code]
        unmapped.add(code)
        return "UNMAPPED"
```

Same guard in `map_sub`:

```python
    def map_sub(code):
        if code is None or (isinstance(code, float) and pd.isna(code)):
            return None
        return code_to_sub.get(code, code)
```

## Part 2: Better Unmapped Code Reporting in cli.py

Currently the CLI prints:
```
Unmapped org codes (consider adding to config): ['nan']
```

Replace with a detailed report showing each unmapped code, its frequency, and an example name. Then print a YAML snippet the user can paste into their config.

### Change in `src/cli.py`

After the enrichment loop, collect unmapped details (not just the code set). Change the enrichment section to also track example names per code.

Add tracking dict before the loop:
```python
    unmapped_details: dict[str, dict] = {}  # code → {count, example_name}
```

Inside the per-file loop, after `enrich_participants`:
```python
            if unmapped:
                unmapped_total.update(unmapped)
                for code in unmapped:
                    if code not in unmapped_details:
                        # Grab an example name with this code
                        example_rows = df[df["org_code"] == code]
                        example_name = example_rows.iloc[0]["Name"] if not example_rows.empty else "?"
                        unmapped_details[code] = {"count": 0, "example": example_name}
                    unmapped_details[code]["count"] += int((df["org_code"] == code).sum())
```

Replace the final unmapped warning block with:
```python
    if unmapped_details:
        print("\n" + "=" * 60, file=sys.stderr)
        print("UNMAPPED ORG CODES", file=sys.stderr)
        print("These codes appeared in the data but aren't in your config.", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        for code in sorted(unmapped_details):
            info = unmapped_details[code]
            print(f"  {code:12s}  ({info['count']} occurrence(s))  e.g. {info['example']}", file=sys.stderr)
        print("\nTo fix, add each code to the appropriate section in your config:", file=sys.stderr)
        print("  org_mapping:", file=sys.stderr)
        print("    EXISTING_MAJOR_ORG:", file=sys.stderr)
        print(f"      sub_orgs: [{', '.join(sorted(unmapped_details))}]", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
```

## Steps
1. Edit `src/enricher.py` — fix NaN guard in `map_major` and `map_sub`
2. Edit `src/cli.py` — add `unmapped_details` tracking and improved warning output
3. Regenerate with synthetic data: `python -m src.cli data/synthetic/ --config config/config.yaml`
4. Verify:
   - No more `nan` in unmapped warnings
   - If you intentionally remove a code from config (e.g., delete BOOM from ROCKETWORKS sub_orgs), the warning shows BOOM with count and example name
   - Report still generates correctly
   - Restore config after testing
5. Commit: `git add -A && git commit -m "Fix NaN guard in enricher, improve unmapped code reporting"`
6. Push: `git push`

## Acceptance Criteria
- [ ] `nan` no longer appears in unmapped code warnings
- [ ] External participants (no pattern match) produce no unmapped warning
- [ ] Genuinely unmapped codes show code, count, and example name
- [ ] YAML snippet suggestion is printed to stderr
- [ ] No regressions in HTML or CSV output
- [ ] Committed and pushed
