"""Tests for brain/adsb.py and brain/adsb_compare.py (standard library only, no network).

The feed is faked: `fetch` is a function that returns a canned answer or raises.
"""
import csv
import math
import tempfile
import unittest
import urllib.error
from pathlib import Path

from brain import adsb, adsb_compare
from brain.logger import Sighting, SightingDB

CAMERA = adsb.Camera(40.0, -100.0, 10.0)        # a made-up spot, not a real address
T0 = 1_760_000_000.0


def aircraft(**overrides):
    entry = {"hex": "A1B2C3", "flight": "TST123 ", "lat": 40.0, "lon": -99.9,
             "alt_baro": 30000, "gs": 400}
    entry.update(overrides)
    return entry


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class Geometry(unittest.TestCase):
    def test_distance_of_one_degree_of_latitude(self):
        self.assertAlmostEqual(adsb.haversine_m(0, 0, 1, 0), 111195, delta=100)

    def test_bearing_points_the_right_way(self):
        self.assertAlmostEqual(adsb.bearing_deg(40, -100, 41, -100), 0, delta=0.01)
        self.assertAlmostEqual(adsb.bearing_deg(40, -100, 40, -99), 90, delta=0.5)
        self.assertAlmostEqual(adsb.bearing_deg(40, -100, 39, -100), 180, delta=0.01)
        self.assertAlmostEqual(adsb.bearing_deg(40, -100, 40, -101), 270, delta=0.5)

    def test_elevation(self):
        self.assertAlmostEqual(adsb.elevation_deg(1000, 1000), 45)
        self.assertEqual(adsb.elevation_deg(0, 500), 90.0)


class Parsing(unittest.TestCase):
    def test_a_normal_aircraft(self):
        (row,) = adsb.parse_aircraft({"ac": [aircraft()]}, CAMERA)
        self.assertEqual(row["hex"], "a1b2c3")
        self.assertEqual(row["callsign"], "TST123")
        self.assertEqual(row["alt_m"], round(30000 * adsb.FT_TO_M))
        self.assertEqual(row["speed_ms"], round(400 * adsb.KNOTS_TO_MS, 1))
        self.assertAlmostEqual(row["azimuth_deg"], 90, delta=0.5)
        self.assertGreater(row["distance_km"], 8)
        self.assertGreater(row["elevation_deg"], 50)

    def test_geometric_altitude_is_preferred(self):
        (row,) = adsb.parse_aircraft({"ac": [aircraft(alt_geom=10000)]}, CAMERA)
        self.assertEqual(row["alt_m"], round(10000 * adsb.FT_TO_M))

    def test_unusable_entries_are_skipped_not_fatal(self):
        payload = {"ac": [aircraft(alt_baro="ground"), aircraft(lat=None), aircraft(lon="x"),
                          aircraft(lat=95), "junk", None, aircraft(alt_baro=math.nan),
                          aircraft(hex="ok")]}
        rows = adsb.parse_aircraft(payload, CAMERA)
        self.assertEqual([r["hex"] for r in rows], ["ok"])

    def test_missing_speed_is_blank(self):
        (row,) = adsb.parse_aircraft({"ac": [aircraft(gs=None)]}, CAMERA)
        self.assertEqual(row["speed_ms"], "")

    def test_distance_filter(self):
        far = aircraft(lon=-99.0)       # about 85 km away
        self.assertEqual(len(adsb.parse_aircraft({"ac": [far]}, CAMERA, max_km=25)), 0)
        self.assertEqual(len(adsb.parse_aircraft({"ac": [far]}, CAMERA, max_km=100)), 1)

    def test_garbage_payloads(self):
        for payload in (None, [], {}, {"ac": None}, {"ac": "x"}, "text"):
            self.assertEqual(adsb.parse_aircraft(payload, CAMERA), [])


class Privacy(unittest.TestCase):
    def setUp(self):
        self.camera = adsb.Camera(40.123456, -100.987654)

    def test_the_request_is_rounded_by_default(self):
        url = adsb.feed_url("adsb.lol", self.camera, 25)
        self.assertIn("/40.12000/-100.99000/", url)
        self.assertNotIn("123456", url)
        self.assertNotIn("987654", url)

    def test_the_radius_grows_to_cover_the_rounding(self):
        rounded = int(adsb.feed_url("adsb.lol", self.camera, 25).rsplit("/", 1)[1])
        exact = int(adsb.feed_url("adsb.lol", self.camera, 25, exact=True).rsplit("/", 1)[1])
        self.assertGreater(rounded, exact)
        self.assertGreaterEqual(rounded * adsb.KM_PER_NM, 25 + 1.5)    # rounding moves <= ~0.8 km

    def test_exact_sends_the_precise_position(self):
        self.assertIn("/40.12346/-100.98765/", adsb.feed_url("adsb.lol", self.camera, 25, exact=True))

    def test_radius_is_capped_by_the_feed_limit(self):
        self.assertEqual(adsb.feed_url("adsb.lol", self.camera, 5000).rsplit("/", 1)[1], "250")


class Location(unittest.TestCase):
    def test_from_environment(self):
        camera = adsb.load_location({"SKYNODE_LAT": "40.5", "SKYNODE_LON": "-100.5",
                                     "SKYNODE_ALT_M": "12"}, path="/nonexistent")
        self.assertEqual((camera.lat, camera.lon, camera.alt_m), (40.5, -100.5, 12.0))

    def test_from_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "location.local.toml"
            path.write_text("lat = 41.0\nlon = -101.0\n")
            camera = adsb.load_location({}, path=path)
        self.assertEqual((camera.lat, camera.lon, camera.alt_m), (41.0, -101.0, 0.0))

    def test_environment_wins_over_the_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "location.local.toml"
            path.write_text("lat = 41.0\nlon = -101.0\n")
            camera = adsb.load_location({"SKYNODE_LAT": "1", "SKYNODE_LON": "2"}, path=path)
        self.assertEqual(camera.lat, 1.0)

    def test_missing_location_explains_what_to_do(self):
        with self.assertRaises(adsb.LocationError) as caught:
            adsb.load_location({}, path="/nonexistent")
        self.assertIn("SKYNODE_LAT", str(caught.exception))

    def test_bad_values(self):
        for environ in ({"SKYNODE_LAT": "north", "SKYNODE_LON": "1"},
                        {"SKYNODE_LAT": "95", "SKYNODE_LON": "1"},
                        {"SKYNODE_LAT": "1"}):
            with self.assertRaises(adsb.LocationError):
                adsb.load_location(environ, path="/nonexistent")

    def test_the_location_file_is_ignored_by_git(self):
        ignore = (Path(__file__).resolve().parent.parent / ".gitignore").read_text()
        self.assertIn("location.local.toml", ignore)


class Polling(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name)

    def test_one_poll_writes_aircraft_and_a_poll_row(self):
        count = adsb.poll_once(CAMERA, self.path, fetch=lambda url: {"ac": [aircraft()]}, now=T0)
        self.assertEqual(count, 1)
        (row,) = read_rows(self.path / adsb.LOG_NAME)
        self.assertEqual(tuple(row), adsb.LOG_COLUMNS)
        self.assertEqual(row["hex"], "a1b2c3")
        self.assertEqual(row["unix"], str(T0))
        (poll,) = read_rows(self.path / adsb.POLLS_NAME)
        self.assertEqual((poll["ok"], poll["aircraft"]), ("1", "1"))

    def test_an_empty_sky_still_records_that_the_feed_answered(self):
        adsb.poll_once(CAMERA, self.path, fetch=lambda url: {"ac": []}, now=T0)
        self.assertEqual(read_rows(self.path / adsb.LOG_NAME), [])
        (poll,) = read_rows(self.path / adsb.POLLS_NAME)
        self.assertEqual((poll["ok"], poll["aircraft"]), ("1", "0"))

    def test_a_feed_failure_is_logged_and_does_not_raise(self):
        def broken(url):
            raise urllib.error.URLError("down")
        self.assertIsNone(adsb.poll_once(CAMERA, self.path, fetch=broken, now=T0))
        (poll,) = read_rows(self.path / adsb.POLLS_NAME)
        self.assertEqual(poll["ok"], "0")
        self.assertFalse((self.path / adsb.LOG_NAME).exists())

    def test_bad_json_counts_as_a_failure(self):
        def bad(url):
            raise ValueError("not json")
        self.assertIsNone(adsb.poll_once(CAMERA, self.path, fetch=bad, now=T0))

    def test_header_is_written_once(self):
        for step in range(3):
            adsb.poll_once(CAMERA, self.path, fetch=lambda url: {"ac": [aircraft()]}, now=T0 + step)
        self.assertEqual(len(read_rows(self.path / adsb.LOG_NAME)), 3)
        text = (self.path / adsb.LOG_NAME).read_text()
        self.assertEqual(text.count("time_iso"), 1)


def make_sighting(started, category="aircraft", duration=20.0, name="airplane"):
    return Sighting(id=f"s{int(started)}", kind="sighting", category=category, class_name=name,
                    start=started, end=started + duration, duration_s=duration, confidence=0.8,
                    pan=10.0, tilt=20.0, box=None, frames=50, snapshot=None)


class Comparing(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name)

    def log_polls(self, times, ok=1):
        adsb.append_rows(self.path / adsb.POLLS_NAME, adsb.POLL_COLUMNS,
                         [{"unix": t, "time_iso": adsb.iso_utc(t), "ok": ok, "aircraft": 0}
                          for t in times])

    def log_aircraft(self, times, **overrides):
        entry = {"hex": "a1b2c3", "callsign": "TST123", "lat": 40.0, "lon": -99.9, "alt_m": 9000,
                 "speed_ms": 200, "distance_km": 8.5, "azimuth_deg": 90, "elevation_deg": 45}
        entry.update(overrides)
        adsb.append_rows(self.path / adsb.LOG_NAME, adsb.LOG_COLUMNS,
                         [{**entry, "unix": t, "time_iso": adsb.iso_utc(t)} for t in times])

    def verdict(self, sighting, **limits):
        aircraft_rows, polls = adsb_compare.load_adsb(self.path)
        return adsb_compare.judge(sighting, aircraft_rows, polls, **limits)

    def test_an_aircraft_in_the_window_agrees(self):
        self.log_polls([T0 + 5, T0 + 15])
        self.log_aircraft([T0 + 5, T0 + 15])
        verdict, nearest = self.verdict(adsb_compare_sighting(T0))
        self.assertEqual(verdict, adsb_compare.AIRCRAFT_OVERHEAD)
        self.assertEqual(nearest["hex"], "a1b2c3")

    def test_polls_without_an_aircraft_is_none_overhead(self):
        self.log_polls([T0 + 5, T0 + 15])
        self.assertEqual(self.verdict(adsb_compare_sighting(T0))[0], adsb_compare.NONE_OVERHEAD)

    def test_no_polls_means_no_data_not_none_overhead(self):
        self.log_polls([T0 - 3600])         # the logger ran, but an hour earlier
        self.assertEqual(self.verdict(adsb_compare_sighting(T0))[0], adsb_compare.NO_DATA)

    def test_failed_polls_do_not_count_as_coverage(self):
        self.log_polls([T0 + 5, T0 + 15], ok=0)
        self.assertEqual(self.verdict(adsb_compare_sighting(T0))[0], adsb_compare.NO_DATA)

    def test_too_far_or_too_low_does_not_count(self):
        self.log_polls([T0 + 5])
        self.log_aircraft([T0 + 5], distance_km=40.0)
        self.assertEqual(self.verdict(adsb_compare_sighting(T0))[0], adsb_compare.NONE_OVERHEAD)
        self.log_aircraft([T0 + 5], elevation_deg=3.0)
        self.assertEqual(self.verdict(adsb_compare_sighting(T0))[0], adsb_compare.NONE_OVERHEAD)

    def test_the_padding_catches_a_pass_just_before(self):
        self.log_polls([T0 - 10])
        self.log_aircraft([T0 - 10])
        self.assertEqual(self.verdict(adsb_compare_sighting(T0))[0], adsb_compare.AIRCRAFT_OVERHEAD)
        self.assertEqual(self.verdict(adsb_compare_sighting(T0), pad_s=2)[0], adsb_compare.NO_DATA)

    def test_damaged_log_rows_are_skipped(self):
        self.log_polls([T0 + 5])
        self.log_aircraft([T0 + 5], distance_km="far")
        self.assertEqual(self.verdict(adsb_compare_sighting(T0))[0], adsb_compare.NONE_OVERHEAD)

    def test_end_to_end_with_a_real_database(self):
        db = SightingDB(self.path)
        db.insert(make_sighting(T0))                                   # aircraft, with a flight
        db.insert(make_sighting(T0 + 600))                             # aircraft, empty sky
        db.insert(make_sighting(T0 + 1200, "drone", name="drone"))     # drone, with a flight
        db.insert(make_sighting(T0 + 99999))                           # nothing logged then
        db.insert(Sighting(id="check1", kind="check", category="clear", class_name="", start=T0,
                           end=T0, duration_s=0, confidence=0, pan=0, tilt=0, box=None,
                           frames=0, snapshot=None))                   # sky checks are not sightings
        db.close()
        self.log_polls([T0 + 5, T0 + 605, T0 + 1205])
        self.log_aircraft([T0 + 5, T0 + 1205])

        sightings = adsb_compare.load_sightings(self.path / "skynode.db")
        self.assertEqual(len(sightings), 4)
        aircraft_rows, polls = adsb_compare.load_adsb(self.path)
        results = adsb_compare.compare(sightings, aircraft_rows, polls)
        self.assertEqual([r["verdict"] for r in results],
                         [adsb_compare.AIRCRAFT_OVERHEAD, adsb_compare.NONE_OVERHEAD,
                          adsb_compare.AIRCRAFT_OVERHEAD, adsb_compare.NO_DATA])
        self.assertEqual(results[0]["nearest_callsign"], "TST123")
        self.assertEqual(results[0]["peak_elevation_deg"], 45.0)
        text = adsb_compare.summary(results)
        self.assertIn("4 sightings compared", text)
        self.assertIn("1 with no ADS-B data", text)
        self.assertIn("not accuracy", text)

    def test_main_writes_the_csv_and_needs_both_logs(self):
        with self.assertRaises(SystemExit):
            adsb_compare.main(["--folder", str(self.path)])             # no database yet
        db = SightingDB(self.path)
        db.insert(make_sighting(T0))
        db.close()
        with self.assertRaises(SystemExit):
            adsb_compare.main(["--folder", str(self.path)])             # no ADS-B log yet
        self.log_polls([T0 + 5])
        out = self.path / "result.csv"
        self.assertEqual(adsb_compare.main(["--folder", str(self.path), "--csv", str(out)]), 0)
        (row,) = read_rows(out)
        self.assertEqual(row["verdict"], adsb_compare.NONE_OVERHEAD)

    def test_the_database_is_opened_read_only(self):
        db = SightingDB(self.path)
        db.insert(make_sighting(T0))
        db.close()
        before = (self.path / "skynode.db").read_bytes()
        adsb_compare.load_sightings(self.path / "skynode.db")
        self.assertEqual((self.path / "skynode.db").read_bytes(), before)


def adsb_compare_sighting(started):
    return {"start": started, "end": started + 20.0}


if __name__ == "__main__":
    unittest.main()
