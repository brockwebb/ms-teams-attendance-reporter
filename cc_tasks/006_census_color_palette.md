# CC Task: Apply Census Data Viz Color Palette

## Priority: MEDIUM
## Status: READY
## Depends on: 005_dashboard_cleanup (COMPLETE)

## Objective
Restyle the HTML dashboard to use the U.S. Census Bureau Data Visualization Standards color palette. The palette is documented at https://xdgov.github.io/data-design-standards/components/colors

## Color Palette

### Featured Colors (use these for primary data elements)
```
Teal:    #0095A8  — RGB(0, 149, 168)    — EMP/FED category
Orange:  #FF7043  — RGB(255, 112, 67)   — CTR category
Navy:    #112E51  — RGB(17, 46, 81)     — headers, text, chart frames
Grey:    #78909C  — RGB(120, 144, 156)  — secondary elements, grid lines, axis labels
```

### Teal Sequential Ramp (for single-variable gradients like histogram)
```
Darkest:  #00282E
Darker:   #004851
Dark:     #006C7A
Teal:     #0095A8
Light:    #00B8D4  (approximate — verify from the standards page)
Lighter:  #4DD0E1  (approximate)
Lightest: #B2EBF2  (approximate)
```

### Qualitative Palette (for multi-category charts like org breakdown)
Use these in order when distinguishing more than 2 categories (e.g., major orgs in trend lines):
```
Teal:     #0095A8
Navy:     #112E51
Orange:   #FF7043
Grey:     #78909C
Dark Teal:#006C7A
```
If more than 5 categories needed, pull from the teal and navy ramps at sufficient spacing.

## Color Assignments

### EMP/CTR (or FED/CTR) Stacking
- **EMP/FED**: Teal `#0095A8`
- **CTR**: Orange `#FF7043`

This pairing is colorblind-friendly (strong luminance contrast between teal and orange).

### Chart Elements
- **Chart titles and section headers**: Navy `#112E51`
- **Axis labels and tick marks**: Grey `#78909C`
- **Grid lines**: Light grey `#CFD8DC` or `#ECEFF1`
- **Background**: White `#FFFFFF`
- **Chart borders/frames**: Navy `#112E51` at reduced opacity or Grey

### Histogram
- Use the teal sequential ramp for the duration buckets (darker = longer attendance)
- OR keep it simple: Teal `#0095A8` for EMP bars, Orange `#FF7043` for CTR bars if stacked

### Trend Lines (by major org)
- Assign from the qualitative palette in order
- Line weight: 2-3px
- Use the same color in the legend

### Summary Header / Report Title
- Navy `#112E51` for the main title
- Teal `#0095A8` for accent elements or KPI numbers
- Grey `#78909C` for secondary text

### Tables
- Header row: Navy `#112E51` background, white text
- Alternating rows: white and very light grey `#F5F5F5`
- Sort indicators: Teal `#0095A8`

## Typography (from Census standards, if web-safe available)
The Census digital experience uses system fonts. For the HTML report, use:
```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
```
This is a standard system font stack — no external font files needed, keeps the report self-contained.

## Implementation

1. In `src/reporter.py`, find all color definitions (hex codes, rgb values, CSS color properties)
2. Replace with the Census palette values defined above
3. Apply the color assignments consistently across all chart types
4. Ensure the color scheme is defined in one place (CSS variables or a Python dict) so it's easy to override later
5. Use CSS custom properties if the reporter generates CSS:
```css
:root {
    --census-teal: #0095A8;
    --census-navy: #112E51;
    --census-orange: #FF7043;
    --census-grey: #78909C;
    --census-grid: #CFD8DC;
    --census-bg: #FFFFFF;
    --census-teal-dark: #006C7A;
    --census-teal-darker: #004851;
    --census-teal-darkest: #00282E;
    --census-teal-light: #B2EBF2;
    --color-emp: var(--census-teal);
    --color-ctr: var(--census-orange);
}
```

## Verification

1. Regenerate the report: `python -m src.cli data/synthetic/ --config config/config.yaml --output report.html`
2. Open in browser and verify:
   - EMP bars/segments are teal, CTR bars/segments are orange
   - Headers are navy
   - Grid lines and axis labels are grey
   - No default Chart.js/Plotly colors remain (no random blues, reds, greens)
   - The overall look is clean, professional, consistent
3. Spot-check colorblind accessibility: the teal/orange pairing should remain distinguishable in grayscale (teal is darker than orange)

## Steps
1. Update `src/reporter.py` with Census color palette
2. Regenerate report
3. Visually verify in browser
4. Commit: `git add -A && git commit -m "Apply Census Data Viz Standards color palette"`
5. Push: `git push`

## Acceptance Criteria
- [ ] All chart colors use the Census palette (no default library colors)
- [ ] EMP = teal (#0095A8), CTR = orange (#FF7043)
- [ ] Headers navy, grid lines grey, background white
- [ ] Colors defined via CSS variables or centralized dict (not scattered hex literals)
- [ ] System font stack, no external font dependencies
- [ ] Report remains fully self-contained (no CDN references)
- [ ] Committed and pushed
