# JW U.S. Congregation Tracker — collector v4

This package updates the collector to produce a **U.S.-only baseline** from the current JW Hub meeting-search endpoint.

## What changed from v3

The previous continental search boxes returned some Canada/Mexico records because the API viewport could cross international borders.

v4:

- searches each U.S. state plus Washington, D.C.;
- recursively subdivides crowded map boxes so 20-result API responses are not treated as complete;
- requires U.S. state + ZIP evidence (or the explicit `(USA)` marker together with U.S. address evidence);
- deduplicates by congregation ID + physical location ID;
- keeps congregation identity (`source_id`) separate from physical meeting location (`location_id`);
- does not interpret disappearance as a closure.

## Run locally

```bash
pip install requests
python collector.py
```

The result is:

`data/snapshot.json`

## GitHub Actions

Replace the repository's existing `collector.py` with this version. Keep your existing workflow if it already installs `requests` and runs `python collector.py`.

The collector intentionally waits between API requests because the JW Hub endpoint applies a small request-rate limit.

## Scope

The v4 baseline is **50 states + Washington, D.C.** U.S. territories are not included in this baseline.

## Important interpretation

A later snapshot that does not contain a congregation should be labeled **"no longer observed"**, not "closed". The public meeting finder alone does not establish why an entry disappeared.

The dashboard/analysis layer should use the congregation ID for congregation history and the location ID for physical-location history.
