# JW U.S. Congregation Tracker — v2.3

This is the non-programmer version.

## Put it on GitHub

1. Create a NEW empty GitHub repository named `jw-us-congregation-tracker`.
2. Download and unzip this package.
3. Upload everything inside this folder to the TOP LEVEL of the GitHub repository.
4. Confirm that `.github/workflows/weekly.yml` exists exactly there.
5. Open the GitHub repository's **Actions** tab.
6. Select **JW U.S. Congregation Tracker**.
7. Click **Run workflow** and then the green **Run workflow** button.

The workflow also runs every Monday automatically.

## Important

The first run establishes the baseline. A later run is needed before change detection can report additions/removals/changes.

A record that disappears from the meeting finder is labeled `NO_LONGER_OBSERVED`, not "closed". That distinction is intentional.
