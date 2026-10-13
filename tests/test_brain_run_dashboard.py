"""End-to-end tests of brain/run.py with the sighting logger and the live dashboard.

Everything is real except the camera and the detector. A fake camera hands
out blank frames (and moves a fake clock on by 0.1 s per frame, as if it ran
at 10 fps). A fake detector "sees" an airplane, then an empty sky for longer
than the tracker waits, then a drone. The real tracker, controller, sighting
logger and web server do the rest, and the tests check what ends up in the
log and what a browser would get from the dashboard.

Needs numpy, OpenCV and onnxruntime, because brain/run.py imports them.
"""
import contextlib
import http.client
import importlib.util
import io
import json
import socket
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

NEEDED = ("numpy", "cv2", "onnxruntime")
if not all(importlib.util.find_spec(name) for name in NEEDED):
    raise unittest.SkipTest("needs " + ", ".join(NEEDED))

import cv2                                                  # noqa: E402
import numpy as np                                          # noqa: E402

from brain.config import Config                             # noqa: E402
from brain.controller import PanTiltController              # noqa: E402
from brain.detector import Detection                        # noqa: E402
from brain.link import NullLink                             # noqa: E402
from brain.logger import COLUMNS, Sighting, row_to_dict     # noqa: E402
from brain.run import (RecordedVideo, VideoClock, codespaces_host, dashboard_info,  # noqa: E402
                       frame_interval, main, make_dashboard, make_logger, parse_args, run_loop)
from brain.tracker import Tracker                           # noqa: E402

WIDTH, HEIGHT = 320, 240
FPS = 10
# 2.75 s before 14:00:00 local time, so the 14:00 sky check falls between frames 27 and 28,
# while the sky is empty (the airplane's lock ended at frame 25)
START = datetime(2026, 10, 7, 14, 0, 0).timestamp() - 2.75

AIRPLANE = [0.50 + 0.04 * i for i in range(10)]       # frames 0-9, best (0.86) at the end
DRONE = [0.60, 0.70, 0.93, 0.80, 0.70, 0.60, 0.60, 0.60]  # frames 30-37, best in the middle
# What the detector sees in each frame: (class, confidence), or None for an empty sky.
# 20 empty frames is more than max_missed_frames (15), so each lock ends on its own.
SCHEDULE = ([("airplane", c) for c in AIRPLANE] + [None] * 20
            + [("drone", c) for c in DRONE] + [None] * 20)
TARGET_BOX = (200.0, 60.0, 240.0, 90.0)     # up and to the right of the centre
CAR_BOX = (10.0, 200.0, 60.0, 230.0)        # a class we don't track, in every frame



def read_log(folder):
    """Every record in <folder>/varn.db as a dict, in the order it was written."""
    with contextlib.closing(sqlite3.connect(Path(folder) / "varn.db")) as conn:
        rows = conn.execute(f"SELECT {', '.join(COLUMNS)} FROM sightings ORDER BY rowid").fetchall()
    return [Sighting.from_dict(row_to_dict(row)).to_dict() for row in rows]


class FakeClock:
    def __init__(self, t=START):
        self.t = t

    def __call__(self):
        return self.t


class FakeCamera:
    """Gives `frames` blank frames, one every 0.1 s on the fake clock, then ok=False."""

    def __init__(self, frames, clock, on_frame=None):
        self.frames = frames
        self.clock = clock
        self.on_frame = on_frame    # called with the frame number before each frame
        self.count = 0

    def read(self):
        if self.count >= self.frames:
            return False, None
        self.clock.t = START + self.count / FPS
        if self.on_frame is not None:
            self.on_frame(self.count)
        self.count += 1
        return True, np.zeros((HEIGHT, WIDTH, 3), np.uint8)    # a new frame every time


class FakeDetector:
    """Frame n contains SCHEDULE[n] (if anything) plus a parked car."""

    def __init__(self, schedule=SCHEDULE):
        self.schedule = schedule
        self.count = 0

    def detect(self, frame):
        seen = self.schedule[self.count] if self.count < len(self.schedule) else None
        self.count += 1
        detections = [Detection(2, "car", 0.55, CAR_BOX)]
        if seen is not None:
            name, confidence = seen
            detections.insert(0, Detection(0, name, confidence, TARGET_BOX))
        return detections


def make_config(folder):
    cfg = Config()
    cfg.display.show = False
    cfg.model.target_classes = ["airplane", "drone"]
    cfg.logger.folder = str(Path(folder) / "logs")
    cfg.dashboard.port = 0              # any free port
    return cfg


def get(port, path):
    """-> (status, content type, body). http.client never goes through a proxy."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        return response.status, response.getheader("Content-Type"), response.read()
    finally:
        conn.close()


def get_json(port, path):
    status, content_type, body = get(port, path)
    if status != 200 or not content_type.startswith("application/json"):
        raise AssertionError(f"{path}: {status} {content_type} {body[:200]!r}")
    return json.loads(body)


class RunLoopTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.static = self.root / "static"
        self.static.mkdir()
        (self.static / "index.html").write_text("<!doctype html><title>Varn</title>")
        self.cfg = make_config(self.root)
        self.clock = FakeClock()

    def parts(self):
        """The real tracker, controller and link, set up from the config like main() does."""
        cfg = self.cfg
        tracker = Tracker(cfg.model.target_classes, cfg.tracker.max_missed_frames,
                          cfg.tracker.max_jump)
        c = cfg.control
        controller = PanTiltController(cfg.camera.hfov_deg, c.gain, c.deadband_deg,
                                       c.max_step_deg, c.pan_sign, c.tilt_sign)
        return tracker, controller, NullLink()

    def start_logger_and_dashboard(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            logger = make_logger(self.cfg, clock=self.clock)
            dashboard = make_dashboard(self.cfg, logger, NullLink(), static_dir=self.static,
                                       clock=self.clock)
        self.assertIsNotNone(dashboard)
        self.addCleanup(dashboard.stop)
        self.assertIn(f"Logging sightings to {self.root / 'logs'}", out.getvalue())
        self.assertIn(f"Dashboard: http://localhost:{dashboard.port}/", out.getvalue())
        return logger, dashboard

    def run_loop(self, camera, logger=None, dashboard=None):
        """Run the real main loop to the end of the fake video. -> (what it printed, controller)"""
        tracker, controller, link = self.parts()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            if logger is None and dashboard is None:
                # Called exactly the way it was before the logger and dashboard existed
                run_loop(camera, FakeDetector(), tracker, controller, link, self.cfg)
            else:
                run_loop(camera, FakeDetector(), tracker, controller, link, self.cfg,
                         logger=logger, dashboard=dashboard)
        return out.getvalue(), controller


class WithLoggerAndDashboardTest(RunLoopTestCase):
    def test_two_sightings_are_logged_and_shown_on_the_dashboard(self):
        logger, dashboard = self.start_logger_and_dashboard()
        port = dashboard.port
        during_drone = {}

        def look_at_the_dashboard(n):
            if n == 34:     # four frames into the drone lock
                during_drone["state"] = get_json(port, "/api/state")
                during_drone["sightings"] = get_json(port, "/api/sightings?kind=sighting")

        camera = FakeCamera(len(SCHEDULE), self.clock, on_frame=look_at_the_dashboard)
        printed, _ = self.run_loop(camera, logger, dashboard)

        # The terminal tells the story: lock, lost, logged, twice. Sky checks stay quiet.
        lines = [line for line in printed.splitlines()
                 if line.startswith(("LOCK", "LOST", "LOGGED"))]
        self.assertEqual(lines, ["LOCK airplane (0.50)", "LOST target",
                                 "LOGGED airplane 0.9s peak 0.86",
                                 "LOCK drone (0.60)", "LOST target",
                                 "LOGGED drone 0.7s peak 0.93"])

        # While the drone was locked, the dashboard showed it live...
        state = during_drone["state"]
        self.assertTrue(state["online"])
        live = state["live"]
        self.assertTrue(live["locked"])
        self.assertEqual(live["target"]["class_name"], "drone")
        self.assertEqual(live["target"]["category"], "drone")
        self.assertEqual(live["target"]["box"], [0.625, 0.25, 0.75, 0.375])   # 0..1 of the frame
        self.assertEqual(live["frame_size"], [WIDTH, HEIGHT])
        self.assertEqual(live["link"], "none")
        car = next(d for d in live["detections"] if d["class_name"] == "car")
        self.assertEqual((car["category"], car["tracked_class"], car["is_target"]),
                         ("other", False, False))
        self.assertEqual(state["current"]["category"], "drone")
        self.assertEqual(state["current"]["frames"], 4)
        # ...and the airplane was already in the log
        self.assertEqual([item["category"] for item in during_drone["sightings"]["items"]],
                         ["aircraft"])

        # Afterwards: two sightings, newest first, with the right categories
        sightings = get_json(port, "/api/sightings?kind=sighting&hours=24")
        self.assertFalse(sightings["more"])
        drone, plane = sightings["items"]
        self.assertEqual((drone["category"], drone["class_name"]), ("drone", "drone"))
        self.assertEqual((plane["category"], plane["class_name"]), ("aircraft", "airplane"))
        self.assertEqual((plane["duration_s"], plane["confidence"], plane["frames"]),
                         (0.9, 0.86, 10))
        self.assertEqual((drone["duration_s"], drone["confidence"], drone["frames"]),
                         (0.7, 0.93, 8))
        self.assertAlmostEqual(plane["start"], START, places=3)
        self.assertAlmostEqual(drone["start"], START + 3.0, places=3)

        # The 14:00 sky check, logged while nothing was tracked
        checks = get_json(port, "/api/sightings?kind=check")["items"]
        self.assertEqual([(c["category"], c["class_name"]) for c in checks], [("clear", "")])
        self.assertAlmostEqual(checks[0]["start"], START + 2.8, places=3)

        stats = get_json(port, "/api/stats?hours=24")
        self.assertEqual((stats["total"], stats["drone"], stats["aircraft"], stats["other"]),
                         (2, 1, 1, 0))
        self.assertEqual(sum(b["drone"] + b["aircraft"] for b in stats["buckets"]), 2)

        state = get_json(port, "/api/state")
        self.assertTrue(state["online"])
        self.assertFalse(state["live"]["locked"])
        self.assertIsNone(state["live"]["target"])
        self.assertIsNone(state["current"])
        self.assertEqual(state["node"]["name"], "NODE-01")
        self.assertEqual(state["node"]["watch_ratio"], 1.0)
        self.assertEqual(state["node"]["target_classes"], ["airplane", "drone"])
        self.assertEqual(get_json(port, "/api/config")["config"]["logger"]["heartbeat_min"], 60)

        # Real JPEG snapshots, saved by the logger and served by the dashboard
        for item in (drone, plane):
            status, content_type, body = get(port, f"/snapshots/{item['snapshot']}")
            self.assertEqual((status, content_type), (200, "image/jpeg"))
            picture = cv2.imdecode(np.frombuffer(body, np.uint8), cv2.IMREAD_COLOR)
            self.assertEqual(picture.shape, (HEIGHT, WIDTH, 3))
        status, content_type, body = get(port, "/snapshot.jpg")
        self.assertEqual((status, content_type), (200, "image/jpeg"))
        self.assertTrue(body.startswith(b"\xff\xd8"))
        csv_rows = get(port, "/api/sightings.csv?kind=sighting")[2].decode().splitlines()
        self.assertEqual(len(csv_rows), 3)
        self.assertTrue(csv_rows[1].startswith(f"{drone['id']},sighting,drone,drone,"))

        # And the same three records are on disk, in the database
        self.assertTrue((self.root / "logs" / "varn.db").is_file())
        records = read_log(self.root / "logs")
        self.assertEqual([r["category"] for r in records], ["aircraft", "clear", "drone"])

    def test_pictures_are_taken_before_the_overlay_draws_on_the_frame(self):
        self.cfg.display.show = True
        logger, dashboard = self.start_logger_and_dashboard()
        camera = FakeCamera(len(SCHEDULE), self.clock)
        # No real window in a test: pretend to show it, and pretend no key was pressed
        with mock.patch("brain.run.cv2.imshow") as imshow, \
                mock.patch("brain.run.cv2.waitKey", return_value=-1):
            self.run_loop(camera, logger, dashboard)
        self.assertEqual(imshow.call_count, len(SCHEDULE))
        drawn = imshow.call_args[0][1]
        self.assertGreater(drawn.max(), 0)                 # the preview did get the overlay...

        _, live_picture = dashboard.latest_picture()
        self.assertEqual(live_picture.max(), 0)            # ...but the live picture didn't
        for item in logger.recent(kind="sighting")[0]:     # ...and neither did the snapshots
            snapshot = cv2.imread(str(logger.snapshot_path(item["snapshot"])))
            self.assertLess(snapshot.max(), 8)             # (JPEG may wobble a tiny bit)

    def test_q_in_the_preview_window_stops_the_loop(self):
        self.cfg.display.show = True
        camera = FakeCamera(len(SCHEDULE), self.clock)
        with mock.patch("brain.run.cv2.imshow"), \
                mock.patch("brain.run.cv2.waitKey", return_value=ord("q")):
            self.run_loop(camera)
        self.assertEqual(camera.count, 1)


class WithoutLoggerAndDashboardTest(RunLoopTestCase):
    def test_run_loop_still_works_with_neither(self):
        camera = FakeCamera(len(SCHEDULE), self.clock)
        printed, controller = self.run_loop(camera)
        self.assertEqual(camera.count, len(SCHEDULE))
        lines = [line for line in printed.splitlines() if line.startswith(("LOCK", "LOST"))]
        self.assertEqual(lines, ["LOCK airplane (0.50)", "LOST target",
                                 "LOCK drone (0.60)", "LOST target"])
        self.assertNotIn("LOGGED", printed)
        self.assertNotEqual((controller.pan, controller.tilt), controller.home)  # it did aim
        self.assertFalse((self.root / "logs").exists())

    def test_turned_off_in_the_config_means_none(self):
        self.cfg.logger.enabled = False
        self.cfg.dashboard.enabled = False
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertIsNone(make_logger(self.cfg))
            self.assertIsNone(make_dashboard(self.cfg, None, NullLink()))
        self.assertEqual(out.getvalue(), "")

    def test_a_taken_port_means_a_warning_and_no_dashboard(self):
        with socket.socket() as blocker:
            blocker.bind(("127.0.0.1", 0))
            blocker.listen()
            self.cfg.dashboard.port = blocker.getsockname()[1]
            with contextlib.redirect_stdout(io.StringIO()) as out:
                dashboard = make_dashboard(self.cfg, None, NullLink(), static_dir=self.static)
        self.assertIsNone(dashboard)
        self.assertIn("WARN the dashboard can't start", out.getvalue())
        self.assertIn("Tracking carries on without the dashboard", out.getvalue())
        # ...and tracking carries on, still logging
        with contextlib.redirect_stdout(io.StringIO()):
            logger = make_logger(self.cfg, clock=self.clock)
        printed, _ = self.run_loop(FakeCamera(len(SCHEDULE), self.clock), logger, dashboard)
        self.assertEqual(printed.count("LOGGED"), 2)


class CodespacesTest(unittest.TestCase):
    IN_CODESPACE = {"CODESPACES": "true", "CODESPACE_NAME": "brave-fox-abc123",
                    "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": "app.github.dev"}

    def test_the_address_is_built_from_the_codespaces_settings(self):
        self.assertEqual(codespaces_host(8080, self.IN_CODESPACE), "brave-fox-abc123-8080.app.github.dev")
        env = {"CODESPACES": "true", "CODESPACE_NAME": "x"}          # no domain given: the usual one
        self.assertEqual(codespaces_host(9000, env), "x-9000.app.github.dev")

    def test_outside_a_codespace_there_is_no_address(self):
        self.assertIsNone(codespaces_host(8080, {}))
        self.assertIsNone(codespaces_host(8080, {"CODESPACE_NAME": "x"}))             # not flagged as one
        self.assertIsNone(codespaces_host(8080, {"CODESPACES": "true"}))              # no name
        self.assertIsNone(codespaces_host(8080, {"CODESPACES": "false", "CODESPACE_NAME": "x"}))

    def test_make_dashboard_allows_only_this_codespace_and_tells_you_the_address(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        static = Path(tmp.name)
        (static / "index.html").write_text("<title>Varn</title>")
        cfg = Config()
        cfg.dashboard.port = 0
        cfg.dashboard.allowed_hosts = ["my.trusted.example"]
        with mock.patch.dict("os.environ", self.IN_CODESPACE, clear=False), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            dashboard = make_dashboard(cfg, None, NullLink(), static_dir=static)
        self.addCleanup(dashboard.stop)
        self.assertEqual(dashboard.allowed_hosts,
                         {"my.trusted.example", "brave-fox-abc123-0.app.github.dev"})
        self.assertIn("https://brave-fox-abc123-0.app.github.dev/", out.getvalue())

    def test_no_codespace_no_extra_names(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cfg = Config()
        cfg.dashboard.port = 0
        with mock.patch.dict("os.environ", {}, clear=True), contextlib.redirect_stdout(io.StringIO()) as out:
            dashboard = make_dashboard(cfg, None, NullLink(), static_dir=Path(tmp.name))
        self.addCleanup(dashboard.stop)
        self.assertEqual(dashboard.allowed_hosts, frozenset())
        self.assertNotIn("Codespaces", out.getvalue())


class LoopingVideoTest(RunLoopTestCase):
    class ShortVideo:
        """Five frames, and it can be rewound twice (then it stays at the end)."""

        def __init__(self):
            self.position = 0
            self.rewinds = 0
            self.rewound_with = []

        def read(self):
            if self.position >= 5:
                return False, None
            self.position += 1
            return True, np.zeros((HEIGHT, WIDTH, 3), np.uint8)

        def set(self, prop, value):
            self.rewound_with.append((prop, value))
            if self.rewinds < 2:
                self.rewinds += 1
                self.position = 0

    def test_loop_starts_the_video_again_and_still_stops_when_it_cannot(self):
        self.cfg.camera.loop = True
        video = self.ShortVideo()
        tracker, controller, link = self.parts()
        detector = FakeDetector(schedule=[None] * 100)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            run_loop(video, detector, tracker, controller, link, self.cfg)
        self.assertEqual(detector.count, 15)                       # 5 frames x (1 play + 2 replays)
        self.assertEqual(video.rewound_with[0], (cv2.CAP_PROP_POS_FRAMES, 0))
        self.assertIn("Camera gave no frame", out.getvalue())      # the third rewind did nothing

    def test_without_loop_the_video_just_ends(self):
        video = self.ShortVideo()
        tracker, controller, link = self.parts()
        detector = FakeDetector(schedule=[None] * 100)
        with contextlib.redirect_stdout(io.StringIO()):
            run_loop(video, detector, tracker, controller, link, self.cfg)
        self.assertEqual((detector.count, video.rewound_with), (5, []))


class CommandLineTest(unittest.TestCase):
    def test_loop_flag(self):
        self.assertTrue(parse_args(["--loop"]).loop)
        self.assertFalse(parse_args([]).loop)

    def test_dashboard_flags(self):
        args = parse_args(["--port", "9000", "--no-dashboard"])
        self.assertEqual((args.port, args.no_dashboard), (9000, True))
        args = parse_args([])
        self.assertEqual((args.port, args.no_dashboard), (None, False))
        for bad in ("0", "70000", "http", "-1"):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                parse_args(["--port", bad])

    def test_dashboard_info_shows_short_paths_only(self):
        cfg = Config()
        cfg.model.path = str(Path(__file__).resolve().parent.parent / "brain" / "models" / "x.onnx")
        cfg.logger.folder = str(Path(tempfile.gettempdir()) / "somewhere" / "varn-logs")
        cfg.camera.source = str(Path(tempfile.gettempdir()) / "videos" / "planes.mp4")
        info = dashboard_info(cfg, NullLink())
        self.assertEqual(info["model"], "x.onnx")
        self.assertEqual(info["camera"], "planes.mp4")
        self.assertEqual(info["link"], "none")
        self.assertEqual(info["target_classes"], ["airplane", "bird"])
        config = info["config"]
        self.assertEqual(config["model"]["path"], "brain/models/x.onnx")
        self.assertEqual(config["logger"]["folder"], "varn-logs")
        self.assertEqual(config["camera"]["source"], "planes.mp4")
        self.assertEqual(set(config), {"camera", "model", "tracker", "control", "link",
                                       "display", "logger", "dashboard"})
        self.assertTrue(Path(cfg.logger.folder).is_absolute())   # the real settings are untouched
        cfg.camera.source = 0
        self.assertEqual(dashboard_info(cfg, NullLink())["camera"], "0")

    def test_dashboard_info_never_shows_a_network_cameras_password(self):
        cfg = Config()
        expected = {
            "rtsp://admin:hunter2@192.168.1.50:554": "rtsp://192.168.1.50:554",
            "rtsp://admin:hunter2@192.168.1.50/live": "rtsp://192.168.1.50",
            "http://192.168.1.50/video.cgi?user=admin&pwd=hunter2": "http://192.168.1.50",
            "RTSP://admin:hunter2@[FE80::1]:8554/stream1": "rtsp://[fe80::1]:8554",
            "rtsp://admin:hunter2@cam.local:99999/": "rtsp://cam.local",    # not a real port
            "rtsp://admin:hunter2@[::1": "network stream",                  # too garbled to read
            "rtspsrc location=rtsp://admin:hunter2@192.168.1.50/ ! appsink": "network stream",
            "C:/videos/planes.mp4": "planes.mp4",       # a Windows drive letter is not an address
        }
        for source, shown in expected.items():
            with self.subTest(source=source):
                cfg.camera.source = source
                info = dashboard_info(cfg, NullLink())
                self.assertEqual(info["camera"], shown)
                self.assertEqual(info["config"]["camera"]["source"], shown)
                everything = json.dumps(info)       # all that /api/state and /api/config show
                self.assertNotIn("hunter2", everything)
                self.assertNotIn("admin", everything)
                self.assertEqual(cfg.camera.source, source)     # the real setting is untouched


RECORDED = datetime(2026, 10, 11, 14, 3, 27, tzinfo=timezone(timedelta(hours=-4)))


class StartTimeFlagTest(unittest.TestCase):
    def parse(self, text):
        return parse_args(["--start-time", text]).start_time

    def test_no_flag_means_no_start_time(self):
        self.assertIsNone(parse_args([]).start_time)

    def test_an_offset_pins_down_the_exact_moment(self):
        self.assertEqual(self.parse("2026-10-11T14:03:27-04:00"), RECORDED.timestamp())
        self.assertEqual(self.parse("2026-10-11T18:03:27Z"), RECORDED.timestamp())     # same moment
        self.assertEqual(self.parse("2026-10-11T18:03:27+00:00"), RECORDED.timestamp())
        self.assertEqual(self.parse("2026-10-11 14:03:27.500-04:00"), RECORDED.timestamp() + 0.5)

    def test_a_time_without_an_offset_is_refused_because_the_hour_could_be_wrong(self):
        for naive in ("2026-10-11T14:03:27", "2026-10-11 14:03:27", "2026-10-11"):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()) as err:
                self.parse(naive)
            self.assertIn("UTC offset", err.getvalue())

    def test_text_that_is_not_a_time_is_refused(self):
        for bad in ("", "noon", "14:03", "2026-13-45T00:00:00Z"):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                self.parse(bad)


class FakeCapture:
    """The bits of cv2.VideoCapture that RecordedVideo uses: `frames` frames, then ok=False."""

    def __init__(self, frames, fps):
        self.frames, self.fps = frames, fps
        self.released = False
        self.set_calls = []

    def get(self, prop):
        return self.fps if prop == cv2.CAP_PROP_FPS else 0.0

    def read(self):
        if self.frames == 0:
            return False, None
        self.frames -= 1
        return True, np.zeros((HEIGHT, WIDTH, 3), np.uint8)

    def set(self, prop, value):
        self.set_calls.append((prop, value))
        return True

    def release(self):
        self.released = True


class RecordedVideoTest(unittest.TestCase):
    def test_the_first_frame_is_at_the_start_time_and_each_one_after_is_one_interval_later(self):
        clock = VideoClock(wall=lambda: 5.0, start=1000.0)
        video = RecordedVideo(FakeCapture(frames=4, fps=10), clock)
        seen = []
        while video.read()[0]:
            seen.append(clock())
        self.assertEqual(len(seen), 4)
        for got, want in zip(seen, (1000.0, 1000.1, 1000.2, 1000.3)):
            self.assertAlmostEqual(got, want)

    def test_the_end_of_the_video_does_not_move_the_clock(self):
        clock = VideoClock(start=1000.0)
        video = RecordedVideo(FakeCapture(frames=1, fps=10), clock)
        video.read()
        self.assertEqual(video.read(), (False, None))
        self.assertEqual(clock(), 1000.0)

    def test_the_frame_rate_comes_from_the_video_with_a_fallback_for_nonsense(self):
        self.assertAlmostEqual(frame_interval(FakeCapture(1, fps=30)), 1 / 30)
        for unknown in (0.0, float("nan"), 0.5, 1000.0):
            self.assertAlmostEqual(frame_interval(FakeCapture(1, fps=unknown)), 1 / 25)

    def test_rewind_and_release_go_to_the_real_video(self):
        capture = FakeCapture(frames=1, fps=10)
        video = RecordedVideo(capture, VideoClock(start=0.0))
        video.set(cv2.CAP_PROP_POS_FRAMES, 0)
        video.release()
        self.assertEqual(capture.set_calls, [(cv2.CAP_PROP_POS_FRAMES, 0)])
        self.assertTrue(capture.released)


class AlwaysAPlane:
    """Stands in for brain.detector.Detector: sees one airplane in the middle of every frame."""
    class_names = ["airplane", "bird"]

    def __init__(self, model_path, min_confidence, iou_threshold):
        pass

    def detect(self, frame):
        height, width = frame.shape[:2]
        x, y = width / 2, height / 2
        return [Detection(0, "airplane", 0.9, (x - 8, y - 8, x + 8, y + 8))]


class MainTest(unittest.TestCase):
    """main() itself, on a folder of PNG frames (OpenCV reads those like a video)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "fake.onnx").write_bytes(b"")     # main() checks the model file exists
        for n in range(5):
            cv2.imwrite(str(self.root / f"frame{n:03d}.png"), np.zeros((64, 64, 3), np.uint8))
        (self.root / "config.toml").write_text(
            '[model]\npath = "fake.onnx"\ntarget_classes = ["airplane"]\n'
            '[logger]\nfolder = "logs"\nmin_duration_s = 0\nheartbeat_min = 0\n'
            '[dashboard]\nport = 0\n')

    def main(self, *flags):
        """Run main() on the PNG frames with the fake detector. Returns what it printed."""
        argv = ["--config", str(self.root / "config.toml"), "--headless",
                "--source", str(self.root / "frame%03d.png"), *flags]
        with mock.patch("brain.run.Detector", AlwaysAPlane), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            main(argv)
        return out.getvalue()

    def logged(self):
        return read_log(self.root / "logs")

    def test_main_logs_the_sighting_still_going_on_when_the_video_ends(self):
        printed = self.main()
        self.assertIn(f"Logging sightings to {self.root / 'logs'}", printed)
        self.assertIn("Dashboard: http://localhost:", printed)
        self.assertIn("LOCK airplane (0.90)", printed)
        # The lock never ended, so main() logged it on the way out
        self.assertRegex(printed, r"LOGGED airplane \d+\.\ds peak 0\.90")
        self.assertEqual([(r["category"], r["frames"]) for r in self.logged()], [("aircraft", 5)])
        # ...and stopped the dashboard: its server thread is gone
        self.assertNotIn("dashboard", [thread.name for thread in threading.enumerate()])

    def test_start_time_stamps_the_sighting_with_the_recording_time_not_today(self):
        interval = frame_interval(cv2.VideoCapture(str(self.root / "frame%03d.png")))
        printed = self.main("--start-time", RECORDED.isoformat())
        self.assertIn("Recording started 2026-10-11 18:03:27 UTC", printed)
        (record,) = self.logged()
        self.assertAlmostEqual(record["start"], RECORDED.timestamp(), places=2)   # first frame
        self.assertAlmostEqual(record["end"], RECORDED.timestamp() + 4 * interval, places=2)
        self.assertAlmostEqual(record["duration_s"], 4 * interval, delta=0.05)    # (logged to 0.1 s)

    def test_without_start_time_the_sighting_is_stamped_with_the_time_it_was_processed(self):
        before = datetime.now().timestamp()
        self.main()
        (record,) = self.logged()
        self.assertGreaterEqual(record["start"], before - 1)

    def test_start_time_needs_a_video_file_and_no_loop(self):
        argv = ["--config", str(self.root / "config.toml"), "--headless",
                "--start-time", RECORDED.isoformat()]
        for extra, words in ((["--source", "0"], "video file"),
                             (["--source", str(self.root / "frame%03d.png"), "--loop"], "--loop")):
            with self.assertRaises(SystemExit) as stopped:
                main(argv + extra)
            self.assertIn(words, str(stopped.exception))
        self.assertFalse((self.root / "logs").exists())     # refused before anything started

    def test_no_dashboard_flag(self):
        printed = self.main("--no-dashboard")
        self.assertNotIn("Dashboard:", printed)
        self.assertEqual(len(self.logged()), 1)     # still logging


if __name__ == "__main__":
    unittest.main()
