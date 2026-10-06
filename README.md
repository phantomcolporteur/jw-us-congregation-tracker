# JW U.S. Congregation Tracker v3.3

v3.3 adds the historical/event layer on top of the working JW Hub collector.

## What you do

1. Keep your existing collector/workflow.
2. Add `run_tracker.py` to the repository root.
3. Keep the collector writing `data/snapshot.json`.
4. Run the collector first, then run `python run_tracker.py`.
5. Open `dashboard/index.html` through GitHub Pages (or a local web server).

The first run establishes a dated baseline and intentionally reports no historical changes. The next run compares the new U.S. snapshot with the previous one.

## Events detected

- new congregation
- no longer observed
- name change
- language change
- likely relocation (up to about 50 miles, with stronger confidence inside 30 miles)
- location changes
- new non-English/non-Spanish language congregation
- new non-English/non-Spanish language at an existing physical location
- major local-area change using an approximately 30-mile radius

The wording is deliberately conservative: disappearance is reported as **no longer observed**, not closed; reorganization is not asserted as fact.

## Important geography behavior

The collector's raw `data/snapshot.json` is preserved. v3.3 creates its own U.S. snapshot in `data/snapshots/` and uses explicit evidence such as `(USA)`, recognized Canadian postal/province patterns, Mexican abbreviations, Bahamas markers, and previously verified U.S. congregation IDs. It does not treat broad coordinates alone as proof of U.S. status.

If a new record lacks enough country evidence, it is left Uncertain rather than guessed into the U.S.

## Files created

- `data/snapshots/YYYY-MM-DD.json` — archived U.S. snapshot
- `data/current_us.json` — current U.S. data
- `data/summary.json` — dashboard summary
- `data/events/latest.json` — latest detected changes
- `dashboard/index.html` — simple dashboard

## Next stage

Once several weekly snapshots exist, v3.4 can add longer-term trend scoring, change clusters, richer maps, and automated alert summaries.
