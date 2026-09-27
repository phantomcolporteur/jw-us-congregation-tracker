# JW Hub Collector v3 — RESTORE

This is the last known-working collector version used in the project before the v4/v4.1 experiments.

## What this restores

- Current JW Hub API: `https://hub.jw.org/meetings/api/meeting-search`
- Geographic grid collection across CONUS, Alaska, and Hawaii
- Recursive subdivision of dense areas
- Congregation ID kept separate from physical meeting-location ID
- Deduplication by congregation ID
- Conservative ~6.5 second request delay
- Existing snapshot/error safety checks

## Important

This is intentionally a **restore**, not the improved U.S.-only collector.

The September 22 baseline produced 14,175 records with 0 request errors, but later analysis showed that the broad geographic collection can include records outside the U.S. and may still require better coverage/deduplication analysis. Do not treat the raw record count as an authoritative U.S. congregation count.

For now, restore this `collector.py` only. Do not replace the rest of the repository.

## Restore steps

1. Download the ZIP.
2. Extract `collector.py`.
3. Replace the repository's current `collector.py` with it.
4. Commit and push.
5. Run the GitHub Action manually.

Do not disable the collector's safety checks and do not change the request delay for the first restore run.
