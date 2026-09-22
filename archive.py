import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "data" / "snapshot.json"
OUT = ROOT / "data" / "snapshots"


def main():
    print(f"Looking for snapshot at: {SRC}")

    if not SRC.exists():
        raise SystemExit(
            f"ERROR: snapshot not found at {SRC}. "
            "The collector did not create data/snapshot.json."
        )

    payload = json.loads(SRC.read_text(encoding="utf-8"))

    captured = payload.get("captured_at") or datetime.now(timezone.utc).isoformat()

    dt = datetime.fromisoformat(captured.replace("Z", "+00:00"))

    payload["date"] = dt.strftime("%Y-%m-%d")
    payload["request_count"] = payload.get("request_count", 0)

    OUT.mkdir(parents=True, exist_ok=True)

    target = OUT / f"{dt.strftime('%Y-%m-%dT%H-%M-%SZ')}.json"

    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Archived snapshot: {target}")


if __name__ == "__main__":
    main()
