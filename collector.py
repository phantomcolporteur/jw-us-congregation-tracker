#!/usr/bin/env python3
"""Collect U.S. congregation meeting records from the current JW Hub API.

The current JW Hub meeting finder uses /meetings/api/meeting-search and a
geographic bounding box. This collector respects the observed rate limit and
recursively subdivides dense areas so a 20-result page cannot silently hide
additional congregations.
"""
import argparse, json, os, re, time
from datetime import datetime, timezone
from pathlib import Path

import requests

API_URL = os.getenv("JW_API_URL", "https://hub.jw.org/meetings/api/meeting-search")
CLIENT_VERSION = os.getenv("JW_CLIENT_VERSION", "1.40.16")
SITE_LANGUAGE_GUID = os.getenv(
    "JW_SITE_LANGUAGE_GUID",
    "bafaf6d8-1e69-47c2-abcb-b3bdfc28eebe",
)

# (min_lon, min_lat, max_lon, max_lat)
REGIONS = {
    "CONUS": (-124.85, 24.35, -66.85, 49.40),
    "ALASKA": (-170.0, 51.0, -129.8, 71.6),
    "HAWAII": (-160.3, 18.7, -154.7, 22.3),
}

STATE_RE = re.compile(r"\b([A-Z]{2})\s+\d{5}(?:-\d{4})?\b", re.IGNORECASE)

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "JW-US-Congregation-Tracker/3.0 (public-data research)",
    "X-Client-Version": CLIENT_VERSION,
    "X-Requested-With": "cdh-application",
}


def boxes(region, step):
    min_lon, min_lat, max_lon, max_lat = region
    lat = min_lat
    while lat < max_lat:
        lon = min_lon
        while lon < max_lon:
            yield (
                lon,
                lat,
                min(lon + step, max_lon),
                min(lat + step, max_lat),
            )
            lon += step
        lat += step


def midpoint(box):
    min_lon, min_lat, max_lon, max_lat = box
    return (min_lat + max_lat) / 2, (min_lon + max_lon) / 2


def normalize_address(address):
    return re.sub(
        r"\s+",
        " ",
        (address or "").replace("\r", " ").replace("\n", " "),
    ).strip()


def state_from_address(address):
    match = STATE_RE.search(normalize_address(address))
    return match.group(1).upper() if match else None


def city_from_name(name):
    # Example: "East - Americus GA (USA)" -> "Americus"
    if not name:
        return None
    match = re.search(r"-\s*(.+?)\s+[A-Z]{2}\s+\(USA\)", name)
    return match.group(1).strip() if match else None


def language_name(guid):
    # JW Hub currently returns languageGuid rather than display language.
    # Keep the GUID as language_code so historical changes remain detectable.
    if guid == "bafaf6d8-1e69-47c2-abcb-b3bdfc28eebe":
        return "English"
    return guid


def request_box(session, box, first=20, retries=3):
    min_lon, min_lat, max_lon, max_lat = box
    search_lat, search_lon = midpoint(box)

    params = [
        ("first", str(first)),
        ("northEastLatitude", str(max_lat)),
        ("northEastLongitude", str(max_lon)),
        ("southWestLatitude", str(min_lat)),
        ("southWestLongitude", str(min_lon)),
        ("searchLatitude", str(search_lat)),
        ("searchLongitude", str(search_lon)),
        ("eventTypes", "congregation"),
        ("siteLanguageGuid", SITE_LANGUAGE_GUID),
        ("isInitialLocationSearch", "true"),
    ]

    last_error = None
    for attempt in range(retries):
        try:
            response = session.get(
                API_URL,
                params=params,
                headers=HEADERS,
                timeout=45,
            )
            if response.status_code == 429:
                wait = max(65, 60 * (attempt + 1))
                print(f"Rate limited; sleeping {wait}s", flush=True)
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = repr(exc)
            if attempt + 1 < retries:
                time.sleep(5 * (attempt + 1))

    raise RuntimeError(last_error or "request failed")


def flatten(payload):
    """Return one normalized record per congregation meeting."""
    records = []

    for result in payload.get("items", []) or []:
        location_id = result.get("id")
        latitude = result.get("latitude")
        longitude = result.get("longitude")

        for meeting in result.get("congregationMeetings", []) or []:
            congregation_id = meeting.get("id")
            address = normalize_address(meeting.get("address"))
            name = meeting.get("name")
            language_guid = meeting.get("languageGuid")

            records.append({
                # Congregation ID is the primary identity.
                "source_id": str(congregation_id or location_id),
                # Location ID is kept separately so physical-location changes
                # can be tracked independently from congregation identity.
                "location_id": str(location_id) if location_id else None,
                "name": name,
                "language": language_name(language_guid),
                "language_code": language_guid,
                "latitude": latitude,
                "longitude": longitude,
                "city": city_from_name(name),
                "state": state_from_address(address),
                "address": address,
                "phone_number": meeting.get("phoneNumber"),
                "is_private_home": meeting.get("isPrivateHome"),
                "midweek_meeting_day": meeting.get("midweekMeetingDay"),
                "midweek_meeting_time": meeting.get("midweekMeetingTime"),
                "weekend_meeting_day": meeting.get("weekendMeetingDay"),
                "weekend_meeting_time": meeting.get("weekendMeetingTime"),
                "source_record": meeting,
            })

    return records


def stable_key(record):
    if record.get("source_id"):
        return "id:" + record["source_id"]

    return "fallback:" + "|".join(
        str(record.get(key) or "").strip().lower()
        for key in (
            "name",
            "language_code",
            "latitude",
            "longitude",
            "address",
        )
    )


def collect(step=6.0, min_step=0.5, delay=6.5, max_boxes=None):
    session = requests.Session()
    queue = []

    for region_name, region in REGIONS.items():
        for box in boxes(region, step):
            queue.append((region_name, box))

    if max_boxes:
        queue = queue[:max_boxes]

    records = {}
    errors = []
    seen_boxes = set()
    request_count = 0

    while queue:
        region_name, box = queue.pop(0)
        box_key = tuple(round(value, 6) for value in box)

        if box_key in seen_boxes:
            continue
        seen_boxes.add(box_key)

        try:
            payload = request_box(session, box)
            request_count += 1

            items = payload.get("items", []) or []
            for record in flatten(payload):
                records[stable_key(record)] = record

            crowded = (
                len(items) >= 20
                or bool(payload.get("hasResultsOutsideViewport"))
            )

            width = box[2] - box[0]
            height = box[3] - box[1]

            # Split potentially truncated areas until tiles are reasonably
            # small. This is what prevents a dense metro from hiding records.
            if crowded and min(width, height) > min_step:
                mid_lon = (box[0] + box[2]) / 2
                mid_lat = (box[1] + box[3]) / 2

                queue.extend([
                    (region_name, (box[0], box[1], mid_lon, mid_lat)),
                    (region_name, (mid_lon, box[1], box[2], mid_lat)),
                    (region_name, (box[0], mid_lat, mid_lon, box[3])),
                    (region_name, (mid_lon, mid_lat, box[2], box[3])),
                ])

            print(
                f"{request_count} requests | {len(records)} congregations | "
                f"queue {len(queue)} | {region_name}",
                flush=True,
            )

        except Exception as exc:
            errors.append({
                "region": region_name,
                "box": box,
                "error": repr(exc),
            })
            print(
                f"ERROR {region_name} {box}: {exc}",
                flush=True,
            )

        # The captured browser response showed about 10 requests/minute.
        # 6.5 seconds keeps the automated scan below that rate.
        time.sleep(delay)

    return list(records.values()), errors, request_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--step",
        type=float,
        default=float(os.getenv("GRID_STEP", "6.0")),
    )
    parser.add_argument(
        "--min-step",
        type=float,
        default=float(os.getenv("MIN_GRID_STEP", "0.5")),
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=float(os.getenv("REQUEST_DELAY", "6.5")),
    )
    parser.add_argument("--max-boxes", type=int)
    parser.add_argument("--out", default="data/snapshot.json")
    args = parser.parse_args()

    print(
        "Collecting from current JW Hub meeting-search API...",
        flush=True,
    )

    records, errors, requests_made = collect(
        args.step,
        args.min_step,
        args.delay,
        args.max_boxes,
    )

    captured_at = datetime.now(timezone.utc).isoformat()

    snapshot = {
        "captured_at": captured_at,
        "source": API_URL,
        "record_count": len(records),
        "request_count": requests_made,
        "error_count": len(errors),
        "records": records,
        "errors": errors,
    }

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "captured_at": captured_at,
                "records": len(records),
                "errors": len(errors),
                "requests": requests_made,
                "out": str(output),
            },
            indent=2,
        )
    )

    if len(records) < 100:
        raise SystemExit(
            "Snapshot rejected: fewer than 100 congregation records collected."
        )

    if errors and len(errors) > max(10, requests_made * 0.20):
        raise SystemExit(
            "Snapshot rejected: too many request errors."
        )


if __name__ == "__main__":
    main()
