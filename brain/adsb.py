"""Log which real aircraft are overhead, so sightings can be checked against them.

Free public ADS-B feeds only answer "what is flying near here right now". They keep
no history you can ask for later. So this runs next to the brain and writes down,
every few seconds, each aircraft within range of the camera:

    logs/adsb_log.csv     one row per aircraft per poll (where it was, how high,
                          and where it is in YOUR sky: azimuth and elevation)
    logs/adsb_polls.csv   one row per poll (when, did the feed answer, how many).
                          It tells "no aircraft overhead" apart from "this was not running".

    python -m brain.adsb                       # runs until Ctrl+C
    python -m brain.adsb --once                # one poll, then stop (a quick check)

`python -m brain.adsb_compare` then lines the sightings up with this log.

Your location. The camera's latitude and longitude are needed to work out where an
aircraft is in your sky, and they point at your home. They are NEVER read from
brain/config.toml (this is a public repo). Put them in one of:

    environment:   SKYNODE_LAT, SKYNODE_LON, SKYNODE_ALT_M (altitude is optional)
    file:          brain/location.local.toml   (git ignores it)
                       lat = 40.1234
                       lon = -73.5678
                       alt_m = 12

What the feed learns. The request itself contains a position. To keep your address from
the feed's logs, the request uses your location rounded to 0.01 degree (about 1 km) and a
radius that is 2 km larger than you asked for; the exact distances are worked out here,
on your computer. Use --exact if you don't mind sending the precise position.

Needs nothing but the standard library. A feed error never stops the loop.
"""
import argparse
import csv
import json
import math
import os
import time
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOCATION_FILE = Path(__file__).resolve().parent / "location.local.toml"
DEFAULT_FOLDER = REPO / "logs"
LOG_NAME, POLLS_NAME = "adsb_log.csv", "adsb_polls.csv"

# Both feeds answer the same way (the "readsb" format) and need no account or key.
FEEDS = {
    "adsb.lol": "https://api.adsb.lol/v2/point/{lat}/{lon}/{radius_nm}",
    "airplanes.live": "https://api.airplanes.live/v2/point/{lat}/{lon}/{radius_nm}",
}
USER_AGENT = "skynode-adsb-logger (+https://github.com/bsalsa2/skynode)"
EARTH_RADIUS_M = 6371000.0
KM_PER_NM = 1.852
FT_TO_M = 0.3048
KNOTS_TO_MS = 0.514444
PRIVACY_MARGIN_KM = 2.0     # extra radius asked for when the position is rounded
MIN_INTERVAL_S = 5.0        # be gentle with a free service
LOG_COLUMNS = ("time_iso", "unix", "hex", "callsign", "lat", "lon", "alt_m", "speed_ms",
               "distance_km", "azimuth_deg", "elevation_deg")
POLL_COLUMNS = ("unix", "time_iso", "ok", "aircraft")


@dataclass
class Camera:
    lat: float
    lon: float
    alt_m: float = 0.0


class LocationError(ValueError):
    """The camera's position is missing or unusable (the message says what to do)."""


def load_location(environ=None, path=LOCATION_FILE):
    """The camera position from the environment, else from brain/location.local.toml."""
    environ = os.environ if environ is None else environ
    if environ.get("SKYNODE_LAT") or environ.get("SKYNODE_LON"):
        values = {"lat": environ.get("SKYNODE_LAT"), "lon": environ.get("SKYNODE_LON"),
                  "alt_m": environ.get("SKYNODE_ALT_M", 0)}
        origin = "SKYNODE_LAT / SKYNODE_LON"
    elif Path(path).is_file():
        with open(path, "rb") as handle:
            values = tomllib.load(handle)
        origin = str(path)
    else:
        raise LocationError(
            "No camera location. Set SKYNODE_LAT and SKYNODE_LON, or create "
            f"{LOCATION_FILE.name} next to brain/config.toml containing lat = ... and "
            "lon = ... (git ignores that file). It is never read from config.toml.")
    try:
        camera = Camera(float(values["lat"]), float(values["lon"]), float(values.get("alt_m", 0)))
    except (KeyError, TypeError, ValueError):
        raise LocationError(f"{origin}: lat and lon must be numbers (alt_m is optional).") from None
    if not (-90 <= camera.lat <= 90 and -180 <= camera.lon <= 180):
        raise LocationError(f"{origin}: lat must be -90..90 and lon -180..180.")
    return camera


# ---- Geometry -------------------------------------------------------------------

def haversine_m(lat1, lon1, lat2, lon2):
    """Ground distance between two points, in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def bearing_deg(lat1, lon1, lat2, lon2):
    """Compass direction from point 1 to point 2: 0 = north, 90 = east."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlon)
    return math.degrees(math.atan2(y, x)) % 360


def elevation_deg(ground_m, height_m):
    """Angle above the horizon of something `height_m` higher than the camera.

    Ignores the curve of the Earth, which is below 1 degree inside 40 km.
    """
    return math.degrees(math.atan2(height_m, ground_m)) if ground_m > 0 else 90.0


# ---- Reading the feed -------------------------------------------------------------

def number(value):
    """A finite float, or None for anything else (the feeds send "ground" and nulls)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def parse_aircraft(payload, camera, max_km=None):
    """Aircraft rows (dicts keyed by LOG_COLUMNS minus time) from one feed answer.

    Skips aircraft with no position, no usable altitude, or on the ground, and (if
    max_km is given) those farther than that from the camera. A damaged entry is
    skipped, never fatal.
    """
    rows = []
    entries = payload.get("ac") if isinstance(payload, dict) else None
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        lat, lon = number(entry.get("lat")), number(entry.get("lon"))
        altitude_ft = number(entry.get("alt_geom"))
        if altitude_ft is None:
            altitude_ft = number(entry.get("alt_baro"))     # "ground" is a string: skipped
        if lat is None or lon is None or altitude_ft is None:
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        ground_m = haversine_m(camera.lat, camera.lon, lat, lon)
        if max_km is not None and ground_m > max_km * 1000:
            continue
        alt_m = altitude_ft * FT_TO_M
        speed = number(entry.get("gs"))
        rows.append({
            "hex": str(entry.get("hex", "")).strip().lower(),
            "callsign": str(entry.get("flight", "")).strip(),
            "lat": round(lat, 5), "lon": round(lon, 5), "alt_m": round(alt_m),
            "speed_ms": "" if speed is None else round(speed * KNOTS_TO_MS, 1),
            "distance_km": round(ground_m / 1000, 2),
            "azimuth_deg": round(bearing_deg(camera.lat, camera.lon, lat, lon), 1),
            "elevation_deg": round(elevation_deg(ground_m, alt_m - camera.alt_m), 1),
        })
    return rows


def feed_url(feed, camera, radius_km, exact=False):
    """The request address. Unless `exact`, the position is rounded to ~1 km (see top)."""
    if exact:
        lat, lon, margin = camera.lat, camera.lon, 0.0
    else:
        lat, lon, margin = round(camera.lat, 2), round(camera.lon, 2), PRIVACY_MARGIN_KM
    radius_nm = max(1, math.ceil((radius_km + margin) / KM_PER_NM))
    return FEEDS[feed].format(lat=f"{lat:.5f}", lon=f"{lon:.5f}", radius_nm=min(radius_nm, 250))


def fetch_json(url, timeout=10):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read(5_000_000))


# ---- Writing the log ----------------------------------------------------------------

def iso_utc(unix):
    return datetime.fromtimestamp(unix, timezone.utc).isoformat(timespec="seconds")


def append_rows(path, columns, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = not path.is_file() or path.stat().st_size == 0
    with open(path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        if fresh:
            writer.writeheader()
        writer.writerows(rows)


def poll_once(camera, folder, feed="adsb.lol", radius_km=25.0, exact=False,
              fetch=fetch_json, now=None):
    """Ask the feed once and log the answer. Returns the number of aircraft logged, or None
    if the feed could not be read (that is logged too, as ok = 0)."""
    now = time.time() if now is None else now
    folder = Path(folder)
    stamp = {"unix": round(now, 1), "time_iso": iso_utc(now)}
    try:
        payload = fetch(feed_url(feed, camera, radius_km, exact))
        rows = parse_aircraft(payload, camera, max_km=radius_km)
    except (OSError, ValueError, urllib.error.URLError) as error:   # includes JSON errors, timeouts
        append_rows(folder / POLLS_NAME, POLL_COLUMNS, [{**stamp, "ok": 0, "aircraft": 0}])
        print(f"WARN ADS-B feed: {error}")
        return None
    append_rows(folder / LOG_NAME, LOG_COLUMNS, [{**stamp, **row} for row in rows])
    append_rows(folder / POLLS_NAME, POLL_COLUMNS, [{**stamp, "ok": 1, "aircraft": len(rows)}])
    return len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Log the aircraft overhead to logs/adsb_log.csv.")
    parser.add_argument("--feed", choices=sorted(FEEDS), default="adsb.lol")
    parser.add_argument("--radius-km", type=float, default=25.0, help="how far out to log")
    parser.add_argument("--interval", type=float, default=10.0, help="seconds between polls")
    parser.add_argument("--folder", type=Path, default=DEFAULT_FOLDER, help="where the logs go")
    parser.add_argument("--exact", action="store_true",
                        help="send your precise position to the feed (default: rounded to ~1 km)")
    parser.add_argument("--once", action="store_true", help="poll one time, then stop")
    args = parser.parse_args(argv)

    try:
        camera = load_location()
    except LocationError as error:
        raise SystemExit(str(error)) from None
    interval = max(args.interval, MIN_INTERVAL_S)
    print(f"ADS-B logger: {args.feed}, within {args.radius_km:g} km, every {interval:g} s, "
          f"into {args.folder}. Ctrl+C to stop.")
    try:
        while True:
            count = poll_once(camera, args.folder, args.feed, args.radius_km, args.exact)
            if args.once:
                print("feed unreachable" if count is None else f"{count} aircraft in range")
                return 0 if count is not None else 1
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
