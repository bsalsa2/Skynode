"""Tests for brain/dashboard.py (no extra packages needed).

Each test starts a REAL server on a free port and talks to it over HTTP,
like a browser would. The sighting logger, the clock, the camera frames and
the JPEG encoder are small fakes, so the tests run without OpenCV and the
times are exact.
"""
import contextlib
import http.client
import importlib.util
import io
import json
import os
import socket
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from brain.dashboard import MAX_VIEWERS, Dashboard

START = 1_791_000_000.0     # a fixed "now" for the fake clock
INFO = {"model": "yolov8n.onnx", "target_classes": ["airplane", "bird"], "camera": "0",
        "link": "none (detection only)", "config": {"dashboard": {"port": 8080}}}
SNAPSHOT = "20261007-140217-001.jpg"


class FakeClock:
    def __init__(self, t=START):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


class FakeFrame:
    """Stands in for a camera frame: the dashboard only reads .shape (and may call .copy())."""

    def __init__(self, width=1280, height=720, label="frame"):
        self.shape = (height, width, 3)
        self.label = label

    def copy(self):
        return FakeFrame(self.shape[1], self.shape[0], self.label + "-copy")


class FakePictures:
    """Fake shrink() and encode_jpeg() that remember how they were called."""

    def __init__(self):
        self.shrunk = []            # (frame, max_width) per call
        self.encoded = 0

    def shrink(self, frame, max_width):
        self.shrunk.append((frame, max_width))
        return FakeFrame(max_width, 540, frame.label + "-small")

    def encode(self, image):
        self.encoded += 1
        return b"\xff\xd8" + image.label.encode() + b"\xff\xd9"


def jpeg_of(label):
    return b"\xff\xd8" + f"{label}-small".encode() + b"\xff\xd9"


def det(name, confidence, box):
    """A stand-in detection: the dashboard needs class_name, confidence and box (pixels)."""
    return SimpleNamespace(class_name=name, confidence=confidence, box=box)


def record(sighting_id, start, category="aircraft", kind="sighting", **extra):
    item = {"id": sighting_id, "kind": kind, "category": category, "class_name": "airplane",
            "start": start, "end": start + 4.2, "duration_s": 4.2, "confidence": 0.91,
            "pan": 92.5, "tilt": 47.0, "box": [0.1, 0.2, 0.3, 0.4], "frames": 50,
            "snapshot": SNAPSHOT}
    item.update(extra)
    return item


class FakeLogger:
    """Implements the SightingLogger interface the dashboard uses, and records every call."""

    def __init__(self, snapshot_folder):
        self.snapshot_folder = Path(snapshot_folder)
        self.calls = []
        self.open = None
        self.stats_error = None
        self.items = [record("20261007-140217-002", START - 60),
                      record("20261007-130000-001", START - 3600, category="clear",
                             kind="check", class_name="", snapshot=None),
                      record("20261007-120000-003", START - 7200, category="drone",
                             class_name="=HYPERLINK(1)", pan=-12.5)]

    def categorize(self, class_name):
        # Deliberately different from the defaults, to prove the dashboard asks the logger
        return {"kite": "drone", "airplane": "aircraft"}.get(class_name.lower(), "other")

    def current(self):
        return self.open

    def recent(self, limit=50, before=None, category=None, kind=None, since=None):
        self.calls.append(("recent", dict(limit=limit, before=before, category=category,
                                          kind=kind, since=since)))
        return [dict(item) for item in self.items[:limit]], len(self.items) > limit

    def stats(self, now=None, hours=24):
        self.calls.append(("stats", hours))
        if self.stats_error:
            raise self.stats_error
        return {"hours": hours, "now": START, "total": 2, "drone": 1, "aircraft": 1,
                "other": 0, "previous_total": float("nan"),      # NaN must never reach the JSON
                "last": {"drone": START - 60, "aircraft": None, "other": None},
                "buckets": [{"start": START, "aircraft": 1, "drone": 1, "other": 0}]}

    def snapshot_path(self, name):
        self.calls.append(("snapshot_path", name))
        path = self.snapshot_folder / name
        return path if name == SNAPSHOT else None


def strict_json(body):
    """Parse JSON the way a browser does: NaN or Infinity in it is an error."""
    def reject(constant):
        raise ValueError(f"{constant} is not valid JSON")
    return json.loads(body.decode("utf-8"), parse_constant=reject)


class DashboardTestCase(unittest.TestCase):
    """Starts a fresh dashboard (fake logger, fake clock, temp static folder) for every test."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.static = self.root / "static"
        (self.static / "fonts").mkdir(parents=True)
        (self.static / "index.html").write_text("<!doctype html><title>Skynode</title>")
        (self.static / "dashboard.css").write_text("body { color: white }")
        (self.static / "dashboard.js").write_text("console.log('hi')")
        (self.static / "favicon.svg").write_text("<svg/>")
        (self.static / "fonts" / "saira.woff2").write_bytes(b"wOF2")
        (self.static / "fonts" / "OFL.txt").write_text("license")
        (self.static / ".hidden.css").write_text("secret")
        (self.static / "notes.md").write_text("not served")
        (self.root / "secret.txt").write_text("outside the static folder")
        (self.root / "secret.css").write_text("outside the static folder")
        snapshots = self.root / "snapshots"
        snapshots.mkdir()
        (snapshots / SNAPSHOT).write_bytes(b"\xff\xd8snapshot\xff\xd9")

        self.clock = FakeClock()
        self.pictures = FakePictures()
        self.logger = FakeLogger(snapshots)
        self.dash = self.start_dashboard(self.logger)

    def start_dashboard(self, logger, **changes):
        settings = dict(port=0, info=INFO, static_dir=self.static, clock=self.clock,
                        encode_jpeg=self.pictures.encode, shrink=self.pictures.shrink)
        settings.update(changes)
        dash = Dashboard(logger, **settings)
        dash.poll_interval = 0.01       # so stop() is quick
        dash.stream_wait_s = 0.05       # so stream threads notice a closed tab quickly
        self.url = dash.start()
        self.addCleanup(dash.stop)
        self.port = dash.port
        return dash

    def request(self, path, method="GET", headers=None):
        """-> (status, headers, body). http.client sends the path exactly as written."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.request(method, path, headers=headers or {})
            response = conn.getresponse()
            return response.status, response.headers, response.read()
        finally:
            conn.close()

    def get_json(self, path):
        status, headers, body = self.request(path)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIsNone(headers["Access-Control-Allow-Origin"])
        return status, strict_json(body)

    def publish(self, detections=(), target=None, frame=None, **values):
        settings = dict(target_classes=["airplane", "bird"], pan=92.5, tilt=47.0, fps=24.8,
                        link_text="none (detection only)")
        settings.update(values)
        frame = frame if frame is not None else FakeFrame()
        self.dash.publish(frame, list(detections), target, settings["target_classes"],
                          settings["pan"], settings["tilt"], settings["fps"],
                          settings["link_text"])
        return frame

    def open_stream(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("GET", "/stream.mjpg?t=123")
        response = conn.getresponse()

        def close():
            response.close()
            conn.close()
        self.addCleanup(close)
        return response, close

    def read_part(self, response):
        """Read one MJPEG part: boundary line, headers, then exactly Content-Length bytes."""
        self.assertEqual(response.readline(), b"--frame\r\n")
        headers = {}
        while (line := response.readline()) != b"\r\n":
            name, value = line.decode().split(":", 1)
            headers[name.strip().lower()] = value.strip()
        self.assertEqual(headers["content-type"], "image/jpeg")
        body = response.read(int(headers["content-length"]))
        self.assertEqual(response.read(2), b"\r\n")
        return body

    def wait_until(self, condition, timeout=2.0):
        deadline = time.monotonic() + timeout
        while not condition():
            if time.monotonic() > deadline:
                self.fail("timed out waiting")
            time.sleep(0.005)


class StaticFilesTest(DashboardTestCase):
    def test_start_returns_a_localhost_url_with_the_real_port(self):
        self.assertNotEqual(self.port, 0)
        self.assertEqual(self.url, f"http://localhost:{self.port}/")

    def test_index_and_assets_have_the_right_content_types(self):
        expected = {
            "/": "text/html; charset=utf-8",
            "/?from=bookmark": "text/html; charset=utf-8",
            "/assets/dashboard.css": "text/css; charset=utf-8",
            "/assets/dashboard.js?v=2": "text/javascript; charset=utf-8",
            "/assets/favicon.svg": "image/svg+xml",
            "/assets/fonts/saira.woff2": "font/woff2",
            "/assets/fonts/OFL.txt": "text/plain; charset=utf-8",
        }
        for path, content_type in expected.items():
            with self.subTest(path=path):
                status, headers, body = self.request(path)
                self.assertEqual(status, 200)
                self.assertEqual(headers["Content-Type"], content_type)
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(int(headers["Content-Length"]), len(body))
        self.assertEqual(self.request("/assets/fonts/saira.woff2")[2], b"wOF2")

    def test_nothing_outside_the_static_folder_or_off_the_list_is_served(self):
        sneaky = [
            "/assets/../secret.txt", "/assets/../secret.css", "/assets/fonts/../../secret.css",
            "/assets/%2e%2e/secret.css", "/assets/%2E%2E%2Fsecret.css", "/assets/..%2fsecret.css",
            "/assets/%252e%252e/secret.css",                    # encoded twice
            "/assets/..\\secret.css", "/assets/..%5csecret.css",
            "/assets/fonts\\..\\..\\secret.css",
            "/assets//etc/passwd", "/assets/%2fetc%2fpasswd", f"/assets/{self.root}/secret.css",
            "/assets/C:%5cWindows%5cwin.ini", "/assets/./dashboard.css",
            "/assets/.hidden.css", "/assets/%2ehidden.css",     # hidden files
            "/assets/notes.md", "/assets/dashboard.CSS",        # not on the list of file types
            "/assets/fonts", "/assets/fonts/", "/assets/",      # folders
            "/assets/missing.css", "/assets/dash%00.css", "/assets/%ff.css",
            "/index.html", "/assets", "/dashboard.css",
        ]
        for path in sneaky:
            with self.subTest(path=path):
                status, _, body = self.request(path)
                self.assertEqual(status, 404)
                self.assertNotIn(b"outside", body)

    @unittest.skipUnless(hasattr(os, "symlink"), "needs symlinks")
    def test_symlink_pointing_outside_is_refused(self):
        try:
            os.symlink(self.root / "secret.css", self.static / "link.css")
        except OSError:
            self.skipTest("no permission to make symlinks here")
        self.assertEqual(self.request("/assets/link.css")[0], 404)

    def test_missing_index_is_a_404_not_a_crash(self):
        (self.static / "index.html").unlink()
        self.assertEqual(self.request("/")[0], 404)


class RoutingTest(DashboardTestCase):
    def test_only_get_is_allowed(self):
        for method in ("POST", "PUT", "DELETE", "PATCH", "OPTIONS", "BREW"):
            with self.subTest(method=method):
                status, headers, body = self.request("/api/state", method)
                self.assertEqual(status, 405)
                self.assertEqual(headers["Allow"], "GET")
                self.assertIn("error", strict_json(body))
        status, headers, body = self.request("/api/state", "HEAD")
        self.assertEqual((status, body), (405, b""))

    def test_unknown_paths_are_404_json(self):
        for path in ("/nope", "/api/state/", "/api", "/api/stats/x", "/API/state"):
            with self.subTest(path=path):
                status, data = self.get_json(path)
                self.assertEqual(status, 404)
                self.assertIn("error", data)

    def test_config_shows_node_and_settings(self):
        status, data = self.get_json("/api/config")
        self.assertEqual(status, 200)
        self.assertEqual(data["config"], INFO["config"])
        self.assertEqual(data["node"]["model"], "yolov8n.onnx")
        self.assertEqual(data["node"]["name"], "NODE-01")

    def test_config_with_odd_values_is_still_valid_json(self):
        # TOML allows nan and inf, and a setting could be a Path or a tuple
        info = {"config": {"camera": {"hfov_deg": float("nan"), "size": (1280, 720),
                                      "folder": Path("logs")}}}
        self.start_dashboard(None, info=info)
        data = self.get_json("/api/config")[1]
        self.assertEqual(data["config"]["camera"],
                         {"hfov_deg": None, "size": [1280, 720], "folder": "logs"})

    def test_a_failing_handler_answers_500_once_logged_and_the_server_keeps_going(self):
        self.logger.stats_error = RuntimeError("disk on fire")
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            for _ in range(2):
                status, data = self.get_json("/api/stats")
                self.assertEqual(status, 500)
                self.assertIn("error", data)
        self.assertEqual(printed.getvalue().count("disk on fire"), 1)
        self.assertEqual(self.get_json("/api/state")[0], 200)


class HostCheckTest(DashboardTestCase):
    """DNS rebinding: a web site that points its own name at us must get nothing."""

    def test_addresses_and_home_network_names_are_answered(self):
        for host in ("localhost", f"localhost:{self.port}", f"127.0.0.1:{self.port}",
                     f"[::1]:{self.port}", "192.168.1.42:8080", "raspberrypi",
                     "raspberrypi.local:8080", "skynode.lan", "pi.home.arpa", "LOCALHOST"):
            with self.subTest(host=host):
                status, _, body = self.request("/api/state", headers={"Host": host})
                self.assertEqual(status, 200)
                self.assertIn("online", strict_json(body))

    def test_web_site_names_are_refused_everywhere(self):
        self.publish()
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            for host in ("evil.example", f"evil.example:{self.port}", "localhost.evil.com",
                         "127.0.0.1.nip.io", "", "[::1", "a b"):
                for path in ("/", "/api/state", "/api/sightings", "/snapshot.jpg",
                             "/stream.mjpg", f"/snapshots/{SNAPSHOT}", "/assets/dashboard.js"):
                    with self.subTest(host=host, path=path):
                        status, headers, body = self.request(path, headers={"Host": host})
                        self.assertEqual(status, 403)
                        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
                        self.assertEqual(list(strict_json(body)), ["error"])
        self.assertEqual(self.dash.viewers, 0)
        self.assertEqual(self.pictures.encoded, 0)          # no picture was made for them
        self.assertEqual(self.logger.calls, [])             # the log was never read for them
        self.assertEqual(printed.getvalue().count("refused"), 1)    # warned once, not per request


class LiveStateTest(DashboardTestCase):
    def test_state_before_any_frame(self):
        self.clock.advance(60)
        status, state = self.get_json("/api/state")
        self.assertEqual(status, 200)
        self.assertFalse(state["online"])
        self.assertIsNone(state["live"])
        self.assertIsNone(state["current"])
        node = state["node"]
        self.assertEqual(node["started_at"], START)
        self.assertEqual(node["uptime_s"], 60.0)
        self.assertEqual(node["watch_ratio"], 1.0)
        self.assertEqual(node["target_classes"], ["airplane", "bird"])
        self.assertEqual((node["camera"], node["link"]), ("0", "none (detection only)"))

    def test_state_after_publish(self):
        plane = det("airplane", 0.973, (640, 180, 960, 360))
        bird = det("bird", 0.41, (0, 0, 128, 72))
        kite = det("Kite", 0.5, (-50, 700, 1400, 800))          # sticks out of the frame
        self.logger.open = {"category": "aircraft", "class_name": "airplane", "start": START,
                            "confidence": 0.97, "frames": 3}
        self.publish([plane, bird, kite], target=plane)
        state = self.get_json("/api/state")[1]
        self.assertTrue(state["online"])
        self.assertEqual(state["current"], self.logger.open)
        live = state["live"]
        self.assertEqual((live["fps"], live["pan"], live["tilt"]), (24.8, 92.5, 47.0))
        self.assertEqual(live["link"], "none (detection only)")
        self.assertTrue(live["locked"])
        self.assertEqual(live["frame_size"], [1280, 720])
        self.assertEqual(live["frame_time"], START)
        self.assertEqual(live["target"], {"class_name": "airplane", "category": "aircraft",
                                          "confidence": 0.97, "box": [0.5, 0.25, 0.75, 0.5]})
        first, second, third = live["detections"]
        self.assertEqual(first, dict(live["target"], tracked_class=True, is_target=True))
        self.assertEqual(second["box"], [0.0, 0.0, 0.1, 0.1])
        self.assertEqual((second["category"], second["tracked_class"], second["is_target"]),
                         ("other", True, False))
        # The logger decides categories ("kite" is a drone in the fake); boxes stay inside 0..1
        self.assertEqual((third["category"], third["tracked_class"]), ("drone", False))
        self.assertEqual(third["box"], [0.0, 0.9722, 1.0, 1.0])

    def test_without_logger_default_categories_are_used(self):
        dash = self.start_dashboard(None)
        dash.publish(FakeFrame(), [det("Drone", 0.9, (0, 0, 10, 10)),
                                   det("airplane", 0.8, (0, 0, 10, 10)),
                                   det("bird", 0.7, (0, 0, 10, 10))],
                     None, ["bird"], 90, 45, 10, "usb COM5")
        live = dash.state()["live"]
        self.assertFalse(live["locked"])
        self.assertIsNone(live["target"])
        self.assertEqual([d["category"] for d in live["detections"]],
                         ["drone", "aircraft", "other"])

    def test_at_most_20_detections_and_the_target_is_kept(self):
        crowd = [det("bird", 0.5 + i / 100, (i, i, i + 5, i + 5)) for i in range(30)]
        target = det("airplane", 0.1, (100, 100, 200, 200))   # the least confident of all
        self.publish(crowd + [target], target=target)
        detections = self.get_json("/api/state")[1]["live"]["detections"]
        self.assertEqual(len(detections), 20)
        self.assertEqual(sum(d["is_target"] for d in detections), 1)
        # ...and the 19 most confident of the rest (0.79 down to 0.61)
        self.assertEqual(min(d["confidence"] for d in detections if not d["is_target"]), 0.61)

    def test_online_flips_off_three_seconds_after_the_last_frame(self):
        self.publish()
        self.clock.advance(3.0)
        self.assertTrue(self.get_json("/api/state")[1]["online"])
        self.clock.advance(0.5)
        state = self.get_json("/api/state")[1]
        self.assertFalse(state["online"])
        self.assertIsNotNone(state["live"])       # the last frame is still there to look at

    def test_watch_ratio_counts_pauses_longer_than_a_second(self):
        self.clock.advance(1.0)
        self.publish()
        self.clock.advance(0.9)           # a normal gap: still watching
        self.publish()
        self.clock.advance(10.0)          # the camera froze for 10 s
        self.publish()
        self.clock.advance(8.1)
        self.publish()                    # this 8.1 s gap counts too
        # 20 s since start, 18.1 s of it not watching
        self.assertAlmostEqual(self.get_json("/api/state")[1]["node"]["watch_ratio"],
                               round(1 - 18.1 / 20, 4))

    def test_a_pause_still_going_on_counts(self):
        self.publish()
        self.clock.advance(10)
        self.assertEqual(self.get_json("/api/state")[1]["node"]["watch_ratio"], 0.0)

    def test_nan_and_infinity_never_reach_the_json(self):
        nan, inf = float("nan"), float("inf")
        self.publish([det("airplane", nan, (nan, 0, inf, 10))], fps=nan, pan=inf, tilt=-inf)
        live = strict_json(self.request("/api/state")[2])["live"]   # raises on NaN / Infinity
        self.assertEqual((live["fps"], live["pan"], live["tilt"]), (0.0, 0.0, 0.0))
        self.assertEqual(live["detections"][0]["confidence"], 0.0)
        stats = self.get_json("/api/stats")[1]
        self.assertIsNone(stats["previous_total"])      # was NaN in the fake logger

    def test_publish_never_raises(self):
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            self.dash.publish(FakeFrame(), [object()], None, [], 0, 0, 0, "")    # not a detection
            self.dash.publish(FakeFrame(), [object()], None, [], 0, 0, 0, "")
        self.assertEqual(printed.getvalue().count("WARN"), 1)
        self.dash.publish(None, None, None, None, None, None, None, None)
        self.assertEqual(self.dash.state()["live"]["frame_size"], [0, 0])

    def test_publish_keeps_its_own_copy_of_the_frame(self):
        frame = self.publish()
        (shrunk_frame, width), = self.pictures.shrunk
        self.assertIs(shrunk_frame, frame)
        self.assertEqual(width, 960)
        self.assertIsNot(self.dash.latest_picture()[1], frame)

        # Even a shrink() that hands back the frame itself can't make it keep a reference
        same = FakeFrame(label="same")
        dash = self.start_dashboard(None, shrink=lambda frame, width: frame)
        dash.publish(same, [], None, [], 0, 0, 0, "")
        image = dash.latest_picture()[1]
        self.assertIsNot(image, same)
        self.assertEqual(image.label, "same-copy")

    def test_without_viewers_a_still_is_kept_about_once_a_second(self):
        for i in range(10):
            self.clock.t = START + i / 10     # 10 frames in one second
            self.publish()
        self.assertEqual(len(self.pictures.shrunk), 1)
        self.clock.t = START + 1.0
        self.publish()
        self.assertEqual(len(self.pictures.shrunk), 2)
        self.assertEqual(self.pictures.encoded, 0)      # JPEGs are only made when asked for


class LogEndpointsTest(DashboardTestCase):
    def last_call(self):
        return self.logger.calls[-1]

    def test_stats_hours_default_clamp_and_passthrough(self):
        status, data = self.get_json("/api/stats")
        self.assertEqual((status, data["hours"], data["total"]), (200, 24, 2))
        for query, hours in (("hours=6", 6), ("hours=0", 1), ("hours=-5", 1),
                             ("hours=1000", 168), ("hours=", 24), ("hours=%2B12", 12)):
            with self.subTest(query=query):
                self.assertEqual(self.get_json(f"/api/stats?{query}")[0], 200)
                self.assertEqual(self.last_call(), ("stats", hours))

    def test_stats_rejects_bad_hours(self):
        calls = len(self.logger.calls)
        for query in ("hours=abc", "hours=1.5", "hours=1e3", "hours=%20%2024", "hours=0x10",
                      "hours=99999999999", "hours=%D9%A3", "hours=1&hours=2"):
            with self.subTest(query=query):
                status, data = self.get_json(f"/api/stats?{query}")
                self.assertEqual(status, 400)
                self.assertIsInstance(data["error"], str)
        self.assertEqual(len(self.logger.calls), calls)      # the logger was never asked

    def test_too_many_query_parameters_is_a_400(self):
        query = "&".join(f"x{i}=1" for i in range(50))
        self.assertEqual(self.get_json(f"/api/sightings?{query}")[0], 400)

    def test_stats_without_a_logger_is_empty_but_shaped_right(self):
        self.start_dashboard(None)
        data = self.get_json("/api/stats?hours=6")[1]
        self.assertEqual((data["hours"], data["total"], data["drone"]), (6, 0, 0))
        self.assertIsNone(data["previous_total"])
        self.assertEqual(data["last"], {"drone": None, "aircraft": None, "other": None})
        starts = [bucket["start"] for bucket in data["buckets"]]
        self.assertEqual(len(starts), 6)
        self.assertLessEqual(starts[-1], START)              # the last bucket is the current hour
        self.assertGreater(starts[-1] + 3600, START)
        for start in starts:                                 # each on a local clock hour
            local = datetime.fromtimestamp(start)
            self.assertEqual((local.minute, local.second), (0, 0))
        self.assertEqual(self.get_json("/api/sightings")[1], {"items": [], "more": False})

    def test_sightings_passthrough_and_defaults(self):
        status, data = self.get_json("/api/sightings")
        self.assertEqual(status, 200)
        self.assertEqual([item["id"] for item in data["items"]],
                         [item["id"] for item in self.logger.items])
        self.assertFalse(data["more"])
        self.assertEqual(self.last_call(), ("recent", dict(limit=50, before=None, category=None,
                                                          kind=None, since=None)))

    def test_sightings_filters_are_checked_and_passed_on(self):
        self.get_json("/api/sightings?limit=2&before=20261007-140217-002&category=drone"
                      "&kind=sighting&hours=24&t=99")       # unknown parameters are ignored
        self.assertEqual(self.last_call(), ("recent", dict(
            limit=2, before="20261007-140217-002", category="drone", kind="sighting",
            since=START - 24 * 3600)))
        self.assertTrue(self.get_json("/api/sightings?limit=2")[1]["more"])
        for query, limit in (("limit=0", 1), ("limit=5000", 200)):
            self.get_json(f"/api/sightings?{query}")
            self.assertEqual(self.last_call()[1]["limit"], limit)
        self.get_json("/api/sightings?category=&kind=&hours=")      # empty = no filter
        self.assertEqual(self.last_call()[1], dict(limit=50, before=None, category=None,
                                                    kind=None, since=None))

    def test_sightings_rejects_bad_filters(self):
        calls = len(self.logger.calls)
        for query in ("limit=many", "category=bird", "category=DRONE", "kind=checks",
                      "hours=-", "hours=2.5", "before=../../etc", "before=a%2Fb",
                      "before=" + "x" * 65, "category=drone&category=other"):
            with self.subTest(query=query):
                status, data = self.get_json(f"/api/sightings?{query}")
                self.assertEqual(status, 400)
                self.assertIn("error", data)
        self.assertEqual(len(self.logger.calls), calls)

    def test_csv_export(self):
        status, headers, body = self.request("/api/sightings.csv?kind=sighting&hours=48")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/csv; charset=utf-8")
        self.assertEqual(headers["Content-Disposition"],
                         'attachment; filename="skynode-sightings.csv"')
        self.assertEqual(self.last_call(), ("recent", dict(
            limit=10000, before=None, category=None, kind="sighting",
            since=START - 48 * 3600)))
        lines = body.decode("utf-8").split("\r\n")
        self.assertEqual(lines[0], "id,kind,category,class_name,start_iso,end_iso,duration_s,"
                                   "confidence,pan,tilt,frames,snapshot")
        self.assertEqual(len(lines), 5)                   # header, 3 rows, and the final ""
        first = lines[1].split(",")
        self.assertEqual(first[:4], ["20261007-140217-002", "sighting", "aircraft", "airplane"])
        self.assertEqual(first[6:], ["4.2", "0.91", "92.5", "47.0", "50", SNAPSHOT])
        start = datetime.fromisoformat(first[4])
        self.assertIsNotNone(start.tzinfo)                # local time WITH its UTC offset
        self.assertEqual(start.timestamp(), START - 60)
        self.assertEqual(datetime.fromisoformat(first[5]).timestamp(), START - 60 + 4)  # whole s
        check = lines[2].split(",")
        self.assertEqual((check[1], check[3], check[-1]), ("check", "", ""))
        drone = lines[3].split(",")
        self.assertEqual(drone[3], "'=HYPERLINK(1)")      # never a live spreadsheet formula
        self.assertEqual(drone[8], "-12.5")               # but negative numbers stay numbers

    def test_csv_rejects_bad_filters(self):
        self.assertEqual(self.request("/api/sightings.csv?category=planes")[0], 400)

    def test_snapshot_files_come_from_snapshot_path(self):
        status, headers, body = self.request(f"/snapshots/{SNAPSHOT}")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "image/jpeg")
        self.assertEqual(headers["Cache-Control"], "max-age=86400")
        self.assertEqual(body, b"\xff\xd8snapshot\xff\xd9")
        self.assertEqual(self.last_call(), ("snapshot_path", SNAPSHOT))
        self.assertEqual(self.request("/snapshots/20261007-140217-009.jpg")[0], 404)

    def test_bad_snapshot_names_never_reach_the_logger(self):
        calls = len(self.logger.calls)
        for name in ("../secret.txt", "..%2fsecret.jpg", "%2e%2e%2fx.jpg", "..%5cx.jpg",
                     "x.png", ".jpg", "a/b.jpg", "x.jpg%00", "%ff.jpg", "x.JPG", ""):
            with self.subTest(name=name):
                self.assertEqual(self.request(f"/snapshots/{name}")[0], 404)
        self.assertEqual(len(self.logger.calls), calls)

    def test_no_logger_means_no_snapshots(self):
        self.start_dashboard(None)
        self.assertEqual(self.request(f"/snapshots/{SNAPSHOT}")[0], 404)


class LivePictureTest(DashboardTestCase):
    def test_snapshot_jpg_before_and_after_the_first_frame(self):
        status, data = self.get_json("/snapshot.jpg")
        self.assertEqual(status, 503)
        self.assertIn("error", data)
        self.publish(frame=FakeFrame(label="one"))
        status, headers, body = self.request("/snapshot.jpg?t=1")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "image/jpeg")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(body, jpeg_of("one"))
        self.request("/snapshot.jpg")
        self.assertEqual(self.pictures.encoded, 1)       # the same picture is encoded once

    def test_stream_sends_the_latest_picture_first(self):
        self.publish(frame=FakeFrame(label="first"))
        response, _ = self.open_stream()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers["Content-Type"],
                         "multipart/x-mixed-replace; boundary=frame")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(self.read_part(response), jpeg_of("first"))
        self.assertEqual(self.dash.viewers, 1)

    def test_stream_follows_new_frames_at_stream_fps(self):
        response, _ = self.open_stream()          # connected before any frame
        self.assertEqual(self.dash.viewers, 1)
        self.publish(frame=FakeFrame(label="a"))
        self.assertEqual(self.read_part(response), jpeg_of("a"))
        # stream_fps is 12: frames 0.05 s apart, so only every other one becomes a picture
        for label in "bcdefg":
            self.clock.advance(0.05)
            self.publish(frame=FakeFrame(label=label))
        self.assertEqual([f.label for f, _ in self.pictures.shrunk], ["a", "c", "e", "g"])
        # The stream always sends the NEWEST picture, so a slow reader skips some, never lags
        parts = [self.read_part(response)]
        while parts[-1] != jpeg_of("g"):
            parts.append(self.read_part(response))
        self.assertLessEqual(set(parts), {jpeg_of("c"), jpeg_of("e"), jpeg_of("g")})

    def test_viewer_cap(self):
        streams = [self.open_stream() for _ in range(MAX_VIEWERS)]
        self.assertTrue(all(response.status == 200 for response, _ in streams))
        self.assertEqual(self.dash.viewers, MAX_VIEWERS)
        status, data = self.get_json("/stream.mjpg")
        self.assertEqual(status, 503)
        self.assertIn("busy", data["error"])

        # Closing a tab frees its place, even when no new frames arrive
        streams[0][1]()
        self.wait_until(lambda: self.dash.viewers == MAX_VIEWERS - 1)
        response, _ = self.open_stream()
        self.assertEqual(response.status, 200)

    def test_pictures_fail_gracefully_when_shrinking_is_impossible(self):
        def broken(frame, width):
            raise ImportError("No module named 'cv2'")
        with contextlib.redirect_stdout(io.StringIO()):
            dash = self.start_dashboard(None, shrink=broken)
            dash.publish(FakeFrame(), [det("bird", 0.5, (0, 0, 10, 10))], None, [], 0, 0, 0, "")
        for path in ("/snapshot.jpg", "/stream.mjpg"):
            status, data = self.get_json(path)
            self.assertEqual(status, 503)
            self.assertIn("cv2", data["error"])
        state = self.get_json("/api/state")[1]
        self.assertTrue(state["online"])                   # tracking data still flows
        self.assertEqual(len(state["live"]["detections"]), 1)
        self.assertEqual(dash.viewers, 0)

    def test_pictures_fail_gracefully_when_encoding_is_impossible(self):
        def broken(image):
            raise ImportError("No module named 'cv2'")
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            dash = self.start_dashboard(None, encode_jpeg=broken)
            dash.publish(FakeFrame(), [], None, [], 0, 0, 0, "")
            for path in ("/snapshot.jpg", "/stream.mjpg"):
                status, data = self.get_json(path)
                self.assertEqual(status, 503)
                self.assertIn("cv2", data["error"])
            self.assertEqual(self.get_json("/api/state")[0], 200)     # the rest still works
        self.assertEqual(dash.viewers, 0)
        self.assertEqual(printed.getvalue().count("WARN"), 1)

    def test_stop_hangs_up_streams_and_frees_the_port(self):
        self.publish()
        response, _ = self.open_stream()
        self.read_part(response)
        started = time.monotonic()
        self.dash.stop()
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertEqual(response.read(), b"")             # the stream ended
        self.assertEqual(self.dash.viewers, 0)
        self.assertFalse(self.dash._thread.is_alive())
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", self.port), timeout=1).close()
        self.dash.stop()                                   # twice is fine

    def test_a_port_in_use_raises_oserror(self):
        other = Dashboard(None, port=self.port, static_dir=self.static)
        with self.assertRaises(OSError):
            other.start()


@unittest.skipUnless(importlib.util.find_spec("brain.logger"), "brain/logger.py not there yet")
class RealLoggerTest(DashboardTestCase):
    """The same server with the real SightingLogger behind it."""

    def test_a_logged_sighting_shows_up_everywhere(self):
        from brain.logger import SightingLogger
        logger = SightingLogger(self.root / "logs", clock=self.clock, heartbeat_min=0,
                                encode_jpeg=lambda image: b"\xff\xd8real\xff\xd9",
                                shrink=lambda frame, width: FakeFrame(width, 360, "snap"))
        self.start_dashboard(logger)
        plane = det("airplane", 0.9, (640, 180, 960, 360))
        frame = FakeFrame()
        logger.update(plane, True, frame, 90.0, 45.0)
        self.assertEqual(self.get_json("/api/state")[1]["current"]["class_name"], "airplane")
        self.clock.advance(2.0)
        logger.update(plane, True, frame, 91.0, 46.0)
        self.clock.advance(1.0)
        logged = logger.update(None, False, frame, 91.0, 46.0)
        self.assertIsNotNone(logged)

        items = self.get_json("/api/sightings?kind=sighting&hours=1")[1]["items"]
        self.assertEqual([item["id"] for item in items], [logged.id])
        self.assertEqual(self.get_json("/api/stats?hours=24")[1]["aircraft"], 1)
        status, _, body = self.request(f"/snapshots/{items[0]['snapshot']}")
        self.assertEqual((status, body), (200, b"\xff\xd8real\xff\xd9"))
        csv_rows = self.request("/api/sightings.csv")[2].decode().split("\r\n")
        self.assertTrue(csv_rows[1].startswith(f"{logged.id},sighting,aircraft,airplane,"))


if __name__ == "__main__":
    unittest.main()
