#!/usr/bin/env python3
"""
JW U.S. Congregation Tracker - collector v4

Collects congregation observations from the current JW Hub meeting-search API.

v4 changes:
- Searches the U.S. state-by-state instead of using broad continental boxes.
- Keeps only records that have a recognized U.S. state/DC and a U.S.-style ZIP,
  or an explicit "(USA)" marker in the congregation name plus U.S. coordinates.
- Keeps congregation ID (source_id) separate from physical meeting-location ID.
- Recursively subdivides crowded search boxes so the API's 20-result viewport
  limit does not silently hide congregations.
- Rejects suspiciously incomplete snapshots.
- Does NOT call a congregation "closed"; absence in a later snapshot is
  represented later by the analysis layer as "no longer observed."

Environment:
    No API key is required. The endpoint is the public JW Hub meeting search
    endpoint used by the JW Hub website.

Usage:
    python collector.py

Output:
    data/snapshot.json
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

API_URL = "https://hub.jw.org/meetings/api/meeting-search"
SITE_LANGUAGE_GUID = "bafaf6d8-1e69-47c2-abcb-b3bdfc28eebe"

# The API/browser response has a small per-minute request allowance.
# 6.5 seconds is intentionally conservative.
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "6.5"))
TIMEOUT_SECONDS = 45

# Search recursion. The API returns at most 20 results for a viewport.
MAX_RESULTS_PER_BOX = 20
MAX_DEPTH = 12

OUT_DIR = Path("data")
OUT_FILE = OUT_DIR / "snapshot.json"

# U.S. states + DC. Territories are intentionally not included in this v4
# baseline because the project has so far been scoped as the 50 states/DC.
STATE_BBOXES = {
    "AL": (30.13, 35.01, -88.47, -84.89),
    "AK": (51.20, 71.54, -179.15, -129.98),
    "AZ": (31.33, 37.00, -114.82, -109.04),
    "AR": (33.00, 36.50, -94.62, -89.64),
    "CA": (32.53, 42.01, -124.48, -114.13),
    "CO": (36.99, 41.00, -109.06, -102.04),
    "CT": (40.95, 42.05, -73.73, -71.79),
    "DE": (38.45, 39.84, -75.79, -74.98),
    "FL": (24.40, 31.00, -87.63, -80.03),
    "GA": (30.36, 35.00, -85.61, -80.84),
    "HI": (18.91, 22.24, -160.25, -154.81),
    "ID": (41.99, 49.00, -117.24, -111.04),
    "IL": (36.97, 42.51, -91.51, -87.02),
    "IN": (37.77, 41.76, -88.10, -84.78),
    "IA": (40.38, 43.50, -96.64, -90.14),
    "KS": (37.00, 40.00, -102.05, -94.59),
    "KY": (36.50, 39.15, -89.57, -81.96),
    "LA": (28.85, 33.02, -94.04, -88.82),
    "ME": (43.06, 47.46, -71.08, -66.85),
    "MD": (37.89, 39.72, -79.49, -75.05),
    "MA": (41.24, 42.89, -73.51, -69.93),
    "MI": (41.70, 48.31, -90.42, -82.41),
    "MN": (43.50, 49.38, -97.24, -89.49),
    "MS": (30.17, 34.99, -91.65, -88.10),
    "MO": (35.99, 40.61, -95.77, -89.10),
    "MT": (44.36, 49.00, -116.05, -104.04),
    "NE": (40.00, 43.00, -104.05, -95.31),
    "NV": (35.00, 42.00, -120.01, -114.04),
    "NH": (42.70, 45.31, -72.56, -70.61),
    "NJ": (38.93, 41.36, -75.56, -73.89),
    "NM": (31.33, 37.00, -109.05, -103.00),
    "NY": (40.50, 45.02, -79.76, -71.86),
    "NC": (33.84, 36.59, -84.32, -75.46),
    "ND": (45.94, 49.00, -104.05, -96.55),
    "OH": (38.40, 42.00, -84.82, -80.52),
    "OK": (33.62, 37.00, -103.00, -94.43),
    "OR": (41.99, 46.29, -124.57, -116.46),
    "PA": (39.72, 42.27, -80.52, -74.69),
    "RI": (41.15, 42.02, -71.89, -71.12),
    "SC": (32.03, 35.22, -83.35, -78.54),
    "SD": (42.48, 45.95, -104.06, -96.44),
    "TN": (34.98, 36.68, -90.31, -81.65),
    "TX": (25.84, 36.50, -106.65, -93.51),
    "UT": (36.99, 42.00, -114.05, -109.04),
    "VT": (42.73, 45.02, -73.44, -71.46),
    "VA": (36.54, 39.47, -83.68, -75.24),
    "WA": (45.54, 49.00, -124.85, -116.92),
    "WV": (37.20, 40.64, -82.64, -77.72),
    "WI": (42.49, 47.31, -92.89, -86.25),
    "WY": (41.00, 45.01, -111.06, -104.05),
    "DC": (38.79, 39.00, -77.12, -76.90),
}

VALID_STATES = set(STATE_BBOXES)

ZIP_RE = re.compile(r"\b\d{5}(?:-\d{4})?\b")
STATE_ZIP_RE = re.compile(
    r"\b(" + "|".join(sorted(VALID_STATES, key=len, reverse=True)) + r")\s+"
    r"\d{5}(?:-\d{4})?\b",
    re.IGNORECASE,
)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def us_evidence(record: dict[str, Any]) -> bool:
    """Require strong textual U.S. evidence, not just a point in a broad box."""
    state = (record.get("state") or "").upper().strip()
    address = record.get("address") or ""
    name = record.get("name") or ""

    if state in VALID_STATES and ZIP_RE.search(address):
        return True

    # Some JW names explicitly identify the country. Require that marker plus
    # a plausible U.S. state/ZIP in the address to avoid accepting foreign data.
    if "(USA)" in name.upper() and STATE_ZIP_RE.search(address.upper()):
        return True

    return False


class Collector:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "cdh-application",
            "X-Client-Version": "1.40.16",
            "User-Agent": "JW-US-Congregation-Tracker/4.0",
        })
        self.requests_made = 0
        self.errors = 0
        self.raw_items = 0
        self.filtered_out = 0
        self.boxes_completed = 0
        self.last_request_at = 0.0

    def throttle(self) -> None:
        elapsed = time.monotonic() - self.last_request_at
        wait = REQUEST_DELAY_SECONDS - elapsed
        if wait > 0:
            time.sleep(wait)

    def fetch_box(self, north: float, east: float, south: float, west: float,
                  state_hint: str, depth: int = 0) -> dict[str, Any]:
        self.throttle()

        params = {
            "first": "20",
            "northEastLatitude": f"{north:.6f}",
            "northEastLongitude": f"{east:.6f}",
            "southWestLatitude": f"{south:.6f}",
            "southWestLongitude": f"{west:.6f}",
            "searchLatitude": f"{(north + south) / 2:.6f}",
            "searchLongitude": f"{(east + west) / 2:.6f}",
            "eventTypes": "congregation",
            "languageGuids": SITE_LANGUAGE_GUID,
            "siteLanguageGuid": SITE_LANGUAGE_GUID,
            "isInitialLocationSearch": "true",
            "search": f"{state_hint}, USA",
        }

        try:
            response = self.session.get(API_URL, params=params, timeout=TIMEOUT_SECONDS)
            self.requests_made += 1
            self.last_request_at = time.monotonic()
            response.raise_for_status()
            payload = response.json()
            return payload
        except Exception as exc:
            self.errors += 1
            self.last_request_at = time.monotonic()
            print(f"[ERROR] {state_hint} depth={depth}: {exc}")
            return {"items": [], "hasResultsOutsideViewport": False, "_error": str(exc)}

    @staticmethod
    def split_box(north: float, east: float, south: float, west: float):
        mid_lat = (north + south) / 2
        mid_lon = (east + west) / 2
        return [
            (north, mid_lon, mid_lat, west),
            (north, east, mid_lat, mid_lon),
            (mid_lat, mid_lon, south, west),
            (mid_lat, east, south, mid_lon),
        ]

    def collect_box(self, north: float, east: float, south: float, west: float,
                    state_hint: str, depth: int = 0) -> list[dict[str, Any]]:
        payload = self.fetch_box(north, east, south, west, state_hint, depth)
        items = payload.get("items") or []
        outside = bool(payload.get("hasResultsOutsideViewport"))
        self.raw_items += len(items)

        # A full result set of 20 or an outside-viewport flag means the box
        # may contain hidden results. Subdivide until it is safe to retain.
        if (len(items) >= MAX_RESULTS_PER_BOX or outside) and depth < MAX_DEPTH:
            children = self.split_box(north, east, south, west)
            all_items: list[dict[str, Any]] = []
            for child in children:
                all_items.extend(self.collect_box(*child, state_hint, depth + 1))
            return all_items

        self.boxes_completed += 1
        return items

    def normalize(self, item: dict[str, Any], meeting: dict[str, Any]) -> dict[str, Any]:
        address = (meeting.get("address") or "").replace("\r", " ").replace("\n", " ")
        name = meeting.get("name") or ""
        state = self.extract_state(meeting, address, name)

        return {
            "source_id": meeting.get("id"),
            "location_id": item.get("id"),
            "name": name,
            "language": self.language_label(meeting.get("languageGuid")),
            "language_code": meeting.get("languageGuid"),
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
            "city": self.extract_city(meeting, address),
            "state": state,
            "address": address.strip(),
            "phone_number": meeting.get("phoneNumber"),
            "is_private_home": bool(meeting.get("isPrivateHome")),
            "midweek_meeting_day": meeting.get("midweekMeetingDay"),
            "midweek_meeting_time": meeting.get("midweekMeetingTime"),
            "weekend_meeting_day": meeting.get("weekendMeetingDay"),
            "weekend_meeting_time": meeting.get("weekendMeetingTime"),
            "source_record": meeting,
        }

    @staticmethod
    def extract_state(meeting: dict[str, Any], address: str, name: str) -> str | None:
        # The normalized record from the prior collector may not have city/state
        # fields, so derive state from the address/name when necessary.
        direct = (meeting.get("state") or "").upper().strip()
        if direct in VALID_STATES:
            return direct

        m = STATE_ZIP_RE.search(address.upper())
        if m:
            return m.group(1).upper()

        m = re.search(
            r"-\s*(" + "|".join(VALID_STATES) + r")\s*\(USA\)",
            name.upper()
        )
        if m:
            return m.group(1).upper()

        return None

    @staticmethod
    def extract_city(meeting: dict[str, Any], address: str) -> str | None:
        if meeting.get("city"):
            return meeting["city"]
        # City is not reliably separable from every address format. Leave it
        # null rather than inventing a city.
        return None

    @staticmethod
    def language_label(guid: str | None) -> str | None:
        if guid == SITE_LANGUAGE_GUID:
            return "English"
        # Preserve GUIDs for now. A later language-metadata pass can map all
        # GUIDs without changing historical observations.
        return guid

    def run(self) -> dict[str, Any]:
        print("JW U.S. Congregation Tracker v4")
        print(f"States/DC: {len(STATE_BBOXES)}")
        print(f"Request delay: {REQUEST_DELAY_SECONDS:.1f}s")

        raw_by_key: dict[tuple[str, str], dict[str, Any]] = {}

        for idx, (state, bbox) in enumerate(STATE_BBOXES.items(), start=1):
            print(f"[{idx}/{len(STATE_BBOXES)}] {state}")
            items = self.collect_box(*bbox, state)
            for item in items:
                for meeting in (item.get("congregationMeetings") or []):
                    if not meeting.get("id"):
                        continue
                    record = self.normalize(item, meeting)
                    if not us_evidence(record):
                        self.filtered_out += 1
                        continue
                    key = (record["source_id"], record["location_id"])
                    raw_by_key[key] = record

        records = list(raw_by_key.values())
        records.sort(key=lambda x: (
            x.get("state") or "",
            x.get("name") or "",
            x.get("source_id") or "",
        ))

        states_seen = sorted({r["state"] for r in records if r.get("state")})
        languages_seen = sorted({r["language_code"] for r in records if r.get("language_code")})

        snapshot = {
            "schema_version": 4,
            "captured_at": iso_now(),
            "source": API_URL,
            "scope": {
                "geography": "United States, 50 states + District of Columbia",
                "method": "state bounding boxes with recursive subdivision and U.S. address/state filtering",
            },
            "stats": {
                "records": len(records),
                "unique_congregations": len({r["source_id"] for r in records}),
                "unique_locations": len({r["location_id"] for r in records}),
                "states": len(states_seen),
                "languages": len(languages_seen),
                "requests": self.requests_made,
                "errors": self.errors,
                "raw_items_seen": self.raw_items,
                "filtered_out": self.filtered_out,
                "boxes_completed": self.boxes_completed,
            },
            "records": records,
        }

        OUT_DIR.mkdir(parents=True, exist_ok=True)

        # Safety checks. Never overwrite a healthy prior snapshot with a
        # suspiciously empty/incomplete run.
        prior = OUT_FILE.exists()
        if len(records) < 100:
            raise RuntimeError(f"Refusing to write snapshot: only {len(records)} records.")
        if self.errors and self.errors / max(self.requests_made, 1) > 0.20:
            raise RuntimeError(
                f"Refusing to write snapshot: {self.errors} errors / "
                f"{self.requests_made} requests."
            )

        if prior:
            try:
                old = json.loads(OUT_FILE.read_text(encoding="utf-8"))
                old_n = len(old.get("records", []))
                if old_n >= 100 and len(records) < old_n * 0.70:
                    raise RuntimeError(
                        f"Refusing to overwrite prior snapshot: new={len(records)}, old={old_n}."
                    )
            except json.JSONDecodeError:
                pass

        OUT_FILE.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(snapshot["stats"], indent=2))
        print(f"Wrote {OUT_FILE}")
        return snapshot


if __name__ == "__main__":
    Collector().run()
