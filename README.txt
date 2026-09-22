# JW Hub collector replacement

Replace the repository's existing `collector.py` with this file.

This version uses the current JW Hub endpoint:

`https://hub.jw.org/meetings/api/meeting-search`

It records the congregation meeting ID separately from the physical meeting-location ID, preserves the address/schedule/language data, and recursively subdivides dense geographic areas so a 20-result response is not silently treated as complete.

The existing GitHub Actions workflow can remain unchanged.

For the first test, use GitHub Actions' **Run workflow** button. The normal weekly workflow should then run automatically.

The collector intentionally uses a conservative request delay because the live browser response showed a rate limit of about 10 requests per minute.
