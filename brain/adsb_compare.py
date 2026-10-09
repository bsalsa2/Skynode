"""Line the sighting log up with the ADS-B log: did a real aircraft explain each sighting?

    python -m brain.adsb_compare                   # summary of everything in logs/
    python -m brain.adsb_compare --csv result.csv  # plus one row per sighting

Reads logs/skynode.db (the camera) and logs/adsb_log.csv + adsb_polls.csv (written by
`python -m brain.adsb` while the brain was running). Nothing is changed or written
except the optional --csv file.

For each sighting it looks at the ADS-B polls between a little before it started and a
little after it ended, and gives one of three verdicts:

    aircraft_overhead   a logged aircraft came within --max-km of the camera and rose
                        above --min-elev degrees in that window
    none_overhead       the feed answered during the window and nothing qualified
    no_data             the ADS-B logger was not running (or its feed was down) then, so
                        the sighting can't be judged either way. These are left out of
                        every percentage.

HONEST LIMITS. "aircraft_overhead" means an aircraft was NEARBY, not that the camera was
looking at it: the pan and tilt are measured from wherever the camera started, not from
north, so they are not compared. And aircraft without a transponder, such as gliders and
small drones, are invisible to ADS-B. So this measures agreement with the public flight
record, not accuracy. A "none_overhead" on an aircraft sighting is a lead to check
in the snapshot, not proof of a mistake.
"""
import argparse
import csv
import sqlite3
import sys
from collections import Counter
from contextlib import closing
from pathlib import Path

from brain.adsb import DEFAULT_FOLDER, LOG_NAME, POLLS_NAME, iso_utc, number

AIRCRAFT_OVERHEAD, NONE_OVERHEAD, NO_DATA = "aircraft_overhead", "none_overhead", "no_data"
RESULT_COLUMNS = ("id", "category", "class_name", "start_utc", "duration_s", "confidence",
                  "verdict", "nearest_hex", "nearest_callsign", "nearest_km", "peak_elevation_deg")


def load_sightings(db_path, since=None):
    """Sightings (not sky checks), oldest first, as dicts. Opens the database read-only."""
    uri = f"file:{Path(db_path).resolve().as_posix()}?mode=ro"
    query = ("SELECT id, category, class_name, started, ended, duration_s, confidence "
             "FROM sightings WHERE kind = 'sighting' AND started >= ? ORDER BY started")
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        rows = conn.execute(query, (since or 0,)).fetchall()
    keys = ("id", "category", "class_name", "start", "end", "duration_s", "confidence")
    return [dict(zip(keys, row)) for row in rows]


def read_csv(path):
    if not Path(path).is_file():
        return []
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_adsb(folder):
    """(aircraft rows, ok-poll times), keeping only rows with usable numbers."""
    aircraft = []
    for row in read_csv(Path(folder) / LOG_NAME):
        parsed = {key: number(_float(row.get(key)))
                  for key in ("unix", "distance_km", "elevation_deg")}
        if None in parsed.values():
            continue
        aircraft.append({**parsed, "hex": row.get("hex", ""), "callsign": row.get("callsign", "")})
    polls = []
    for row in read_csv(Path(folder) / POLLS_NAME):
        unix = _float(row.get("unix"))
        if unix is not None and row.get("ok") == "1":
            polls.append(unix)
    return aircraft, polls


def _float(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def judge(sighting, aircraft, polls, pad_s=15.0, max_km=15.0, min_elev=10.0):
    """The verdict for one sighting, plus the nearest qualifying aircraft (or None)."""
    start, end = sighting["start"] - pad_s, sighting["end"] + pad_s
    if not any(start <= t <= end for t in polls):
        return NO_DATA, None
    near = [a for a in aircraft
            if start <= a["unix"] <= end and a["distance_km"] <= max_km
            and a["elevation_deg"] >= min_elev]
    if not near:
        return NONE_OVERHEAD, None
    return AIRCRAFT_OVERHEAD, min(near, key=lambda a: a["distance_km"])


def compare(sightings, aircraft, polls, **limits):
    results = []
    for sighting in sightings:
        verdict, nearest = judge(sighting, aircraft, polls, **limits)
        peak = None
        if nearest is not None:
            peak = max(a["elevation_deg"] for a in aircraft
                       if a["hex"] == nearest["hex"]
                       and sighting["start"] - 60 <= a["unix"] <= sighting["end"] + 60)
        results.append({
            "id": sighting["id"], "category": sighting["category"],
            "class_name": sighting["class_name"], "start_utc": iso_utc(sighting["start"]),
            "duration_s": sighting["duration_s"], "confidence": sighting["confidence"],
            "verdict": verdict,
            "nearest_hex": nearest["hex"] if nearest else "",
            "nearest_callsign": nearest["callsign"] if nearest else "",
            "nearest_km": nearest["distance_km"] if nearest else "",
            "peak_elevation_deg": peak if peak is not None else "",
        })
    return results


def percent(part, whole):
    return "n/a" if not whole else f"{100 * part / whole:.0f}%"


def summary(results):
    """The report as text."""
    counts = {}
    for result in results:
        counts.setdefault(result["category"], Counter())[result["verdict"]] += 1
    lines = [f"{len(results)} sightings compared."]
    for category in ("aircraft", "drone", "other"):
        tally = counts.get(category)
        if not tally:
            continue
        judged = tally[AIRCRAFT_OVERHEAD] + tally[NONE_OVERHEAD]
        lines.append(f"\n{category}: {sum(tally.values())} sightings, "
                     f"{tally[NO_DATA]} with no ADS-B data (left out below)")
        lines.append(f"  aircraft nearby   {tally[AIRCRAFT_OVERHEAD]:>4}  "
                     f"({percent(tally[AIRCRAFT_OVERHEAD], judged)})")
        lines.append(f"  none overhead     {tally[NONE_OVERHEAD]:>4}  "
                     f"({percent(tally[NONE_OVERHEAD], judged)})")
        meaning = {
            "aircraft": "'none overhead' = a false alarm, or a plane without ADS-B. Check the snapshots.",
            "drone": "'aircraft nearby' = possibly a misclassified aircraft. Check the snapshots.",
            "other": "birds and the like: ADS-B can't confirm these either way.",
        }[category]
        lines.append(f"  {meaning}")
    lines.append("\nThis is agreement with public flight data, not accuracy: see the notes in "
                 "brain/adsb_compare.py.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare sightings with the ADS-B log.")
    parser.add_argument("--folder", type=Path, default=DEFAULT_FOLDER, help="the logs folder")
    parser.add_argument("--csv", type=Path, help="also write one row per sighting here")
    parser.add_argument("--pad-s", type=float, default=15.0, help="slack either side of a sighting")
    parser.add_argument("--max-km", type=float, default=15.0, help="how close counts as nearby")
    parser.add_argument("--min-elev", type=float, default=10.0, help="lowest angle above the horizon")
    args = parser.parse_args(argv)

    database = args.folder / "skynode.db"
    if not database.is_file():
        raise SystemExit(f"No sighting log at {database}. Run the brain first.")
    if not (args.folder / POLLS_NAME).is_file():
        raise SystemExit(f"No ADS-B log in {args.folder}. Run `python -m brain.adsb` next to "
                         "the brain, and compare afterwards.")
    sightings = load_sightings(database)
    aircraft, polls = load_adsb(args.folder)
    results = compare(sightings, aircraft, polls,
                      pad_s=args.pad_s, max_km=args.max_km, min_elev=args.min_elev)
    print(summary(results))
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=RESULT_COLUMNS)
            writer.writeheader()
            writer.writerows(results)
        print(f"wrote {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
