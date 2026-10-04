# JW U.S. Congregation Tracker — v3.2 geography layer

This package is a cleaned next step from the 2026-10-03 JW Hub collection.

## What changed
v3.1 incorrectly treated the entire broad coordinate collection as U.S. The new classifier uses explicit address/name evidence first and refuses to guess when evidence is insufficient.

Current classification:
- U.S.: 11,409
- Mexico: 1,946
- Canada: 791
- Uncertain: 19
- Total collected: 14,165

The raw collection is preserved in `snapshot_v3.2.json`.
The U.S.-only dataset is `us_snapshot_v3.2.json`.
`geography_audit_v3.2.json` records the classification counts and reasons.

## Dashboard
`dashboard.html` is a dependency-free static dashboard. It loads `us_snapshot_v3.2.json` from the same folder.

For GitHub Pages, put these files in the repository root (or the Pages folder) and open the published site. For local testing, use any simple local web server; opening the HTML directly as a `file://` URL may block the JSON fetch in some browsers.

## Important
This is a classification layer, not a claim that JW.org itself provides an official country field. The raw JW Hub records remain preserved, and ambiguous records are excluded from the U.S. dataset rather than silently included.
