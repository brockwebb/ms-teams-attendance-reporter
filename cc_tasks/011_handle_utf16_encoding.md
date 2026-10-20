# CC Task: Handle UTF-16 Teams Attendance Exports

## Priority: HIGH (blocks real data usage)
## Status: READY
## Depends on: None (independent bug fix)

## Objective
Teams on Windows sometimes exports attendance CSVs as UTF-16 LE (BOM `0xFF 0xFE`) instead of UTF-8. The parser's `_read_lines()` only tries `utf-8-sig` and crashes with `UnicodeDecodeError`.

## Root Cause
`_read_lines()` in `src/parser.py` hardcodes `encoding="utf-8-sig"`. UTF-16 LE files start with bytes `0xFF 0xFE`, which is not valid UTF-8.

## Fix

Replace `_read_lines` in `src/parser.py` with an encoding-fallback version:

```python
def _read_lines(filepath: Path) -> list[str]:
    """Read lines from a Teams CSV, handling encoding variations.

    Teams exports vary by platform:
      - UTF-8 with BOM (utf-8-sig) — most common on web/Mac
      - UTF-16 LE with BOM — sometimes seen on Windows desktop
    Try utf-8-sig first; on failure, fall back to utf-16.
    """
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            with open(filepath, "r", encoding=encoding) as f:
                return f.readlines()
        except (UnicodeDecodeError, UnicodeError):
            continue
    # Last resort: read as latin-1 (never fails, every byte is valid)
    with open(filepath, "r", encoding="latin-1") as f:
        return f.readlines()
```

## Steps
1. Edit `src/parser.py` — replace `_read_lines` function with the version above
2. Test with synthetic data (UTF-8): `python -m src.cli data/synthetic/ --config config/config.yaml`
   - Verify no regressions — same output as before
3. Create a UTF-16 test file to confirm the fix works:
   ```python
   # Quick one-liner to create a UTF-16 version of an existing CSV:
   python -c "
   from pathlib import Path
   p = Path('data/synthetic/copilot_agents_20260518.csv')
   text = p.read_text(encoding='utf-8')
   Path('/tmp/test_utf16.csv').write_text(text, encoding='utf-16')
   "
   python -m src.cli /tmp/test_utf16.csv --config config/config.yaml
   ```
   - Should parse without error and produce the same participant count
4. Clean up test file
5. Commit: `git add -A && git commit -m "Handle UTF-16 LE encoding in Teams CSV exports"`
6. Push: `git push`

## Acceptance Criteria
- [ ] UTF-8-sig files still parse correctly (no regression)
- [ ] UTF-16 LE files parse without UnicodeDecodeError
- [ ] latin-1 fallback exists as last resort (should never trigger for Teams files, but prevents hard crash on unknown encodings)
- [ ] Committed and pushed

## Design Notes
- The encoding list is deliberately short. Teams only produces UTF-8 or UTF-16. Adding more encodings invites silent mojibake.
- `latin-1` as final fallback is a safety net, not a real encoding detection — it accepts any byte sequence. If it ever triggers on a real file, the output will be garbage but the tool won't crash, and the user will see garbled names and know something is wrong.
