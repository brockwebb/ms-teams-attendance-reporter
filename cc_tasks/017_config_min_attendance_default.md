# Task 017 — Configurable Default Min Attendance Threshold

## Overview

The min-attendance threshold filter currently defaults to 0 in the HTML/JS.
Add a `min_attendance_minutes` field to the YAML config so orgs can set a
non-zero default (e.g., 5 minutes to flush drive-by joins). The UI control
still lets the user change it at runtime — this just sets the initial value.

---

## Changes

### 1. Config schema: add `min_attendance_minutes`

In `config/config.yaml` (the synthetic ACNE example), add under the
`cap_minutes` line in the "Attendance Settings" section:

```yaml
# Default minimum attendance threshold (minutes). Participants below
# this are excluded from main charts and shown in "Fleeting Birds".
# The dashboard filter still lets users adjust at runtime. Default: 0.
min_attendance_minutes: 0
```

### 2. Thread config value into reporter

**File: `src/reporter.py`**

In the `generate_html_report` function (the one that builds the HTML string),
read the config value and bake it into the JS DATA object and the HTML input default.

Find where `cap_repr` is set and the DATA dict is assembled. Add:

```python
min_att_default = int((config or {}).get("min_attendance_minutes", 0))
```

Then in the JS DATA object (the `const DATA = { ... }` block that gets
json-serialized into the page), add a new field:

```python
"min_attendance_default": min_att_default,
```

In the HTML template, change the input default from hardcoded `value="0"`:

```html
<input id="filter-min-minutes" type="number" min="0" max="60" value="0"
```

To use the config value. Since this is inside a Python f-string or template,
inject `min_att_default`:

```html
<input id="filter-min-minutes" type="number" min="0" max="60" value="{min_att_default}"
```

In the JS, change the state initialization from:

```javascript
const state = { meeting: 'ALL', directorate: 'ALL', division: 'ALL', minMinutes: 0 };
```

To:

```javascript
const state = { meeting: 'ALL', directorate: 'ALL', division: 'ALL', minMinutes: DATA.min_attendance_default || 0 };
```

And in the reset handler, change:

```javascript
    state.minMinutes = 0;
    ...
    minMinInput.value = 0;
```

To:

```javascript
    state.minMinutes = DATA.min_attendance_default || 0;
    ...
    minMinInput.value = DATA.min_attendance_default || 0;
```

### 3. Same for CSV export path

In `generate_csv_report`, read the same config field. The CSV currently
exports ALL records regardless of threshold — keep that behavior. No change
needed here unless the intent changes.

---

## Testing

```bash
cd /Users/brock/Documents/GitHub/ms-teams-attendance-reporter
python -m src.cli data/synthetic/ --config config/config.yaml --output output/
```

1. With `min_attendance_minutes: 0` — behaves exactly as before
2. With `min_attendance_minutes: 5` — dashboard loads with filter pre-set to 5,
   Fleeting Birds section visible on load, charts exclude <5min attendees
3. Reset button restores to config default (not 0)
4. User can still manually change the filter at runtime

## Do NOT change
- CSS
- Other section renderers
- CSV export (always includes all records)
