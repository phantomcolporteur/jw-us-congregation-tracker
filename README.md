# JW U.S. Congregation Tracker v3

Replace the files in the existing repository with this package. Do not replace the `.git` folder.

This version probes JW.org before the full scan, uses browser-like headers and `searchLanguageCode=E`, retries requests, rejects error-heavy/near-zero collections, and fixes all repository-root paths.

A successful first run establishes the baseline. A second successful run is required for change detection.

“No longer observed” is deliberately not treated as proof that a congregation closed.
