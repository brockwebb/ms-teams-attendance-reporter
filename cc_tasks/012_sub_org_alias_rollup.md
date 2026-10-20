# CC Task: Sub-Org Alias Support (Roll-Up to Parent Division)

## Priority: MEDIUM
## Status: READY
## Depends on: 010_fix_unmapped_code_handling (COMPLETE)

## Objective
Allow sub_orgs entries in the config to be either:
- A **string**: code maps to itself as the displayed sub_org (current behavior)
- A **dict** `{code: parent}`: code maps to `parent` as the displayed sub_org

This lets sub-units roll up into their parent division without adding
a third hierarchy level. Example: JTC and TTC are sub-offices of NPC.
Rather than appearing as separate divisions in the charts, their
attendance rolls up under "NPC".

## Config Syntax

```yaml
ADFO:
  direct_codes: [ADFO]
  sub_orgs:
    - FLD
    - NPC
    - JTC: NPC    # JTC attendance rolls up under NPC
    - TTC: NPC    # TTC attendance rolls up under NPC
    - NYRO
    - PHRO
```

When a participant has org_code `JTC`:
- `major_org` → `ADFO`
- `sub_org` → `NPC` (not `JTC`)

This is a display-level alias, not a third hierarchy level. The raw
`org_code` column still shows `JTC` for traceability.

## Implementation — `src/enricher.py`

In `load_org_config`, replace the sub_orgs loop:

```python
        for entry in info.get("sub_orgs", []) or []:
            if isinstance(entry, dict):
                # Alias: {code: parent_display_name}
                for code, parent in entry.items():
                    code_to_major[code] = major
                    code_to_sub[code] = parent
            else:
                # Plain string: code is its own sub_org name
                code_to_major[entry] = major
                code_to_sub[entry] = entry
```

That's the only code change.

## Steps
1. Edit `src/enricher.py` — replace the `for code in info.get("sub_orgs", [])` loop with the version above
2. Add JTC and TTC aliases to `config/config-census.yaml` under ADFO (see config syntax above)
3. To test without real data, temporarily add aliased codes to the synthetic config and a synthetic CSV. Or just verify with a quick Python snippet:
   ```python
   from src.enricher import load_org_config
   cfg = load_org_config("config/config-census.yaml")
   print(cfg["_code_to_major"].get("JTC"))  # → ADFO
   print(cfg["_code_to_sub"].get("JTC"))    # → NPC
   print(cfg["_code_to_sub"].get("NPC"))    # → NPC
   ```
4. Commit: `git add -A && git commit -m "Support sub-org aliases for roll-up to parent division"`
5. Push: `git push`

## Acceptance Criteria
- [ ] String sub_orgs entries still work identically (no regression)
- [ ] Dict sub_orgs entries map code → parent as sub_org display name
- [ ] `org_code` column still shows the raw code (JTC, not NPC) for traceability
- [ ] Config loads without error
- [ ] Committed and pushed

## Documentation for Config Authors

Add this comment block to the config file where sub_orgs is used:

```yaml
# sub_orgs entries can be:
#   - CODE          → appears as its own division in reports
#   - CODE: PARENT  → attendance rolls up under PARENT in reports
#                     (use when a sub-office belongs to a named division
#                      but doesn't need its own chart slice)
```
