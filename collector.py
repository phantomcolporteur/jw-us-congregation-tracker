#!/usr/bin/env python3
"""Collect JW.org meeting-finder results for the continental United States.

The collector is intentionally configurable because JW.org can change its public
meeting-search endpoint or response schema. It queries a geographic grid and
stores a normalized snapshot for later comparison.
"""
import argparse, json, math, os, time
from datetime import datetime, timezone
from pathlib import Path
import requests

DEFAULT_URL = os.getenv("JW_API_URL", "https://apps.jw.org/api/public/meeting-search/weekly-meetings")
HEADERS = {"User-Agent": "JW-US-Congregation-Tracker/1.0 (research; contact repository owner)"}

# Rough bounding box for the contiguous U.S.  Alaska/Hawaii can be added as separate grids.
BBOX = (-124.8, 24.3, -66.9, 49.4)  # min_lon, min_lat, max_lon, max_lat


def grid(step_deg=1.0):
    min_lon, min_lat, max_lon, max_lat = BBOX
    lat = min_lat
    while lat <= max_lat:
        lon = min_lon
        while lon <= max_lon:
            yield round(lat, 4), round(lon, 4)
            lon += step_deg
        lat += step_deg


def first(d, keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] not in (None, ""):
            return d[k]
    return default


def walk_records(obj):
    """Find plausible meeting/congregation dictionaries anywhere in a JSON response."""
    if isinstance(obj, dict):
        # Common signals; keep broad to survive modest schema changes.
        keys = {k.lower() for k in obj}
        if keys & {"congregationname", "congregation_name", "meetingname", "congregation", "congregationid"}:
            yield obj
        for v in obj.values():
            yield from walk_records(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_records(v)


def normalize(rec):
    name = first(rec, ["congregationName", "congregation_name", "meetingName", "name"])
    lang = first(rec, ["languageName", "language", "languageDescription", "searchLanguageName"])
    lang_code = first(rec, ["languageCode", "language_code", "searchLanguageCode"])
    cid = first(rec, ["congregationId", "congregationID", "id", "congregation_id"])
    lat = first(rec, ["latitude", "lat"])
    lon = first(rec, ["longitude", "lon", "lng"])
    address = first(rec, ["address", "meetingAddress", "locationAddress"])
    city = first(rec, ["city", "locality", "town"])
    state = first(rec, ["state", "stateName", "province"])
    # Preserve the source object so a later schema mapper can recover fields.
    return {
        "source_id": str(cid) if cid is not None else None,
        "name": name,
        "language": lang,
        "language_code": lang_code,
        "latitude": lat,
        "longitude": lon,
        "city": city,
        "state": state,
        "address": address,
        "source_record": rec,
    }


def stable_key(x):
    if x["source_id"]:
        return "id:" + x["source_id"]
    # Fallback deliberately includes location/language to avoid false merges.
    vals = [x.get("name"), x.get("language"), x.get("latitude"), x.get("longitude"), x.get("city"), x.get("state")]
    return "fallback:" + "|".join("" if v is None else str(v).strip().lower() for v in vals)


def request_point(session, lat, lon):
    params = {"includeSuggestions": "true", "latitude": lat, "longitude": lon}
    r = session.get(DEFAULT_URL, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def collect(step=1.0, delay=0.35, max_points=None):
    session = requests.Session()
    out = {}
    errors = []
    points = list(grid(step))
    if max_points:
        points = points[:max_points]
    for i, (lat, lon) in enumerate(points, 1):
        try:
            payload = request_point(session, lat, lon)
            for raw in walk_records(payload):
                item = normalize(raw)
                if item["name"]:
                    out[stable_key(item)] = item
        except Exception as e:
            errors.append({"lat": lat, "lon": lon, "error": repr(e)})
        time.sleep(delay)
        print(f"{i}/{len(points)} points; {len(out)} records; {len(errors)} errors", flush=True)
    return list(out.values()), errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=float, default=float(os.getenv("GRID_STEP", "1.0")))
    ap.add_argument("--delay", type=float, default=float(os.getenv("REQUEST_DELAY", "0.35")))
    ap.add_argument("--max-points", type=int)
    ap.add_argument("--out", default="data/snapshot.json")
    args = ap.parse_args()
    records, errors = collect(args.step, args.delay, args.max_points)
    now = datetime.now(timezone.utc).isoformat()
    snapshot = {"captured_at": now, "source": DEFAULT_URL, "record_count": len(records), "request_count": len(list(grid(args.step))) if not args.max_points else min(args.max_points, len(list(grid(args.step)))), "records": records, "errors": errors}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"captured_at": now, "records": len(records), "errors": len(errors), "out": args.out}, indent=2))

if __name__ == "__main__":
    main()
