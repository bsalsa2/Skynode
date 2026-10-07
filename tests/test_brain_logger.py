"""Tests for brain/logger.py (no extra packages needed: no OpenCV, no numpy).

Images are faked: a "frame" is a tiny object with a .shape, "shrinking" and
"JPEG encoding" just record what they were given. Time is faked too: every
test sets the clock (or passes `now`) itself, and runs in a fixed timezone
where the computer allows it (time.tzset, i.e. not on Windows).
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from brain.logger import Sighting, SightingLogger, default_encode_jpeg, default_shrink

REPO = Path(__file__).resolve().parent.parent
HAS_TZSET = hasattr(time, "tzset")
HAS_CV2 = all(importlib.util.find_spec(name) for name in ("cv2", "numpy"))
SPEC_KEYS = ["id", "kind", "category", "class_name", "start", "end", "duration_s",
             "confidence", "pan", "tilt", "box", "frames", "snapshot"]


def local(*parts):
    """Unix time of a local wall-clock time, e.g. local(2026, 10, 7, 14, 2, 17)."""
    return datetime(*parts).timestamp()


def utc(*parts):
    return datetime(*parts, tzinfo=timezone.utc).timestamp()


def use_timezone(test, tz):
    """Run the rest of `test` in timezone `tz`, a POSIX TZ string (needs no timezone database)."""
    if not HAS_TZSET:
        test.skipTest("needs time.tzset (Linux or macOS)")
    old = os.environ.get("TZ")
    os.environ["TZ"] = tz
    time.tzset()

    def restore():
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()
    test.addCleanup(restore)


class FakeFrame:
    """Stands in for a camera image: the logger only reads .shape (height, width, channels)."""

    def __init__(self, width=1000, height=500, label="frame"):
        self.shape = (height, width, 3)
        self.label = label


def fake_shrink(frame, max_w):
    return ("shrunk", frame.label, max_w)


def fake_encode(image):
    return f"JPEG {image!r}".encode()


class FakeClock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def det(name="airplane", confidence=0.8, box=(100, 50, 200, 150)):
    """A stand-in detection: the logger only needs class_name, confidence and box (pixels)."""
    return SimpleNamespace(class_name=name, confidence=confidence, box=box)


def log_sighting(log, start, duration=1.0, name="airplane", confidence=0.8):
    """A complete lock: seen at `start` and `start + duration`, then the tracker gives up."""
    log.update(det(name, confidence), True, FakeFrame(), 90.0, 45.0, now=start)
    log.update(det(name, confidence), True, FakeFrame(), 90.0, 45.0, now=start + duration)
    return log.update(None, False, FakeFrame(), 90.0, 45.0, now=start + duration + 0.25)


def record(record_id, start, kind="sighting", category="aircraft"):
    check = kind == "check"
    return Sighting(id=record_id, kind=kind, category="clear" if check else category,
                    class_name="" if check else category, start=start, end=start, duration_s=0.0,
                    confidence=0.0 if check else 0.5, pan=90.0, tilt=45.0, box=None,
                    frames=0 if check else 1, snapshot=None)


def ids(records):
    return [r["id"] for r in records]


class LoggerTestCase(unittest.TestCase):
    # Nepal is UTC+5:45: a timezone where mixing up UTC and local time can't go unnoticed
    TIMEZONE = "NPT-5:45"

    def setUp(self):
        if HAS_TZSET:
            use_timezone(self, self.TIMEZONE)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name) / "logs"
        self.clock = FakeClock(local(2026, 10, 7, 12, 0, 0))

    def make(self, folder=None, **settings):
        options = dict(clock=self.clock, encode_jpeg=fake_encode, shrink=fake_shrink,
                       heartbeat_min=0)
        options.update(settings)
        return SightingLogger(folder or self.folder, **options)

    def write_records(self, records, folder=None):
        """Write records into the daily files, as an earlier run would have."""
        folder = folder or self.folder
        folder.mkdir(parents=True, exist_ok=True)
        for r in records:
            day = datetime.fromtimestamp(r.start).strftime("%Y-%m-%d")
            with open(folder / f"sightings-{day}.jsonl", "a") as f:
                f.write(json.dumps(r.to_dict()) + "\n")

    def quietly(self, make_logger):
        """Build a logger that prints a warning, and return (logger, what it printed)."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            log = make_logger()
        return log, out.getvalue()


class LifecycleTest(LoggerTestCase):
    def test_lock_is_logged_once_with_its_best_moment(self):
        log = self.make()
        t0 = local(2026, 10, 7, 14, 2, 17)
        frames = [FakeFrame(label=f"f{i}") for i in range(5)]      # 1000 x 500 pixels
        self.assertIsNone(log.update(det("airplane", 0.5, (100, 50, 200, 150)), True,
                                     frames[0], 90.0, 45.0, now=t0))
        self.assertEqual(log.current(), {"category": "aircraft", "class_name": "airplane",
                                         "start": t0, "confidence": 0.5, "frames": 1})
        self.assertIsNone(log.update(det("airplane", 0.91234, (500, 100, 600, 250)), True,
                                     frames[1], 92.54, 47.04, now=t0 + 1.5))
        self.assertIsNone(log.update(det("airplane", 0.7, (510, 100, 610, 250)), True,
                                     frames[2], 95.0, 48.0, now=t0 + 4.2))
        self.assertIsNone(log.update(None, True, frames[3], 95.0, 48.0, now=t0 + 4.5))  # a miss
        self.assertEqual(log.current()["frames"], 3)
        self.assertEqual(log.current()["confidence"], 0.91)
        self.assertEqual(log.recent(), ([], False))             # nothing logged while open

        logged = log.update(None, False, frames[4], 95.0, 48.0, now=t0 + 5.0)   # lock dropped
        expected = {"id": "20261007-140217-001", "kind": "sighting", "category": "aircraft",
                    "class_name": "airplane", "start": t0, "end": round(t0 + 4.2, 3),
                    "duration_s": 4.2, "confidence": 0.91, "pan": 92.5, "tilt": 47.0,
                    "box": [0.5, 0.2, 0.6, 0.5], "frames": 3,
                    "snapshot": "20261007-140217-001.jpg"}
        self.assertEqual(logged.to_dict(), expected)
        self.assertEqual(list(logged.to_dict()), SPEC_KEYS)
        self.assertIsNone(log.current())
        self.assertEqual(log.recent(), ([expected], False))

        snapshot = self.folder / "snapshots" / "20261007-140217-001.jpg"
        self.assertEqual(snapshot.read_bytes(), fake_encode(("shrunk", "f1", 640)))  # best frame
        lines = (self.folder / "sightings-2026-10-07.jsonl").read_text().splitlines()
        self.assertEqual([json.loads(line) for line in lines], [expected])

    def test_class_is_the_one_at_the_best_frame(self):
        log = self.make()
        t = local(2026, 10, 7, 14, 0, 0)
        log.update(det("bird", 0.4), True, FakeFrame(), 0, 0, now=t)
        log.update(det("airplane", 0.8), True, FakeFrame(), 0, 0, now=t + 1)
        log.update(det("bird", 0.8), True, FakeFrame(), 0, 0, now=t + 2)    # equal is not better
        logged = log.update(None, False, None, 0, 0, now=t + 3)
        self.assertEqual((logged.class_name, logged.category, logged.confidence),
                         ("airplane", "aircraft", 0.8))
        self.assertEqual(logged.end, t + 2)                     # last frame it was seen

    def test_frame_is_only_shrunk_on_a_new_best(self):
        shrunk = []

        def counting_shrink(frame, max_w):
            shrunk.append(frame.label)
            return fake_shrink(frame, max_w)
        log = self.make(shrink=counting_shrink)
        t = local(2026, 10, 7, 14, 0, 0)
        for i, confidence in enumerate([0.5, 0.4, 0.6, 0.6, 0.3]):
            log.update(det("airplane", confidence), True, FakeFrame(label=f"f{i}"), 0, 0, now=t + i)
        logged = log.update(None, False, None, 0, 0, now=t + 9)
        self.assertEqual(shrunk, ["f0", "f2"])
        snapshot = self.folder / "snapshots" / logged.snapshot
        self.assertEqual(snapshot.read_bytes(), fake_encode(("shrunk", "f2", 640)))

    def test_short_locks_are_not_logged(self):
        log = self.make(min_duration_s=0.5)
        t = local(2026, 10, 7, 14, 0, 0)
        log.update(det(), True, FakeFrame(), 0, 0, now=t)
        log.update(det(), True, FakeFrame(), 0, 0, now=t + 0.25)
        self.assertIsNone(log.update(None, False, FakeFrame(), 0, 0, now=t + 0.5))
        self.assertFalse(self.folder.exists())                  # folders appear on first write
        self.assertEqual(log.recent(), ([], False))

        log.update(det(), True, FakeFrame(), 0, 0, now=t + 10)
        log.update(det(), True, FakeFrame(), 0, 0, now=t + 10.5)    # exactly the minimum
        logged = log.update(None, False, FakeFrame(), 0, 0, now=t + 11)
        self.assertEqual(logged.duration_s, 0.5)

    def test_one_frame_lock_counts_when_minimum_is_zero(self):
        log = self.make(min_duration_s=0)
        t = local(2026, 10, 7, 14, 0, 0)
        log.update(det(), True, FakeFrame(), 0, 0, now=t)
        logged = log.update(None, False, FakeFrame(), 0, 0, now=t + 1)
        self.assertEqual((logged.frames, logged.duration_s), (1, 0.0))

    def test_close_flushes_the_open_lock(self):
        log = self.make()
        t = local(2026, 10, 7, 14, 0, 0)
        self.assertIsNone(log.close(now=t))                     # nothing open
        log.update(det(), True, FakeFrame(), 10.0, 20.0, now=t)
        log.update(det(), True, FakeFrame(), 10.0, 20.0, now=t + 2)
        logged = log.close(now=t + 3)
        self.assertEqual((logged.duration_s, logged.end), (2.0, t + 2))
        self.assertIsNone(log.current())
        self.assertEqual(ids(log.recent()[0]), [logged.id])
        self.assertTrue((self.folder / "sightings-2026-10-07.jsonl").exists())
        self.assertIsNone(log.close(now=t + 4))                 # already closed

        log.update(det(), True, FakeFrame(), 0, 0, now=t + 10)  # too short to keep
        self.clock.t = t + 10.1
        self.assertIsNone(log.close())                          # now comes from the clock
        self.assertIsNone(log.current())
        self.assertEqual(len(log.recent()[0]), 1)

    def test_junk_numbers_never_reach_the_json(self):
        log = self.make(min_duration_s=0)
        t = local(2026, 10, 7, 14, 0, 0)
        target = det("airplane", float("nan"), (float("nan"), -5, 2000, 600))
        log.update(target, True, FakeFrame(), None, float("inf"), now=t)
        logged = log.update(None, False, None, 0, 0, now=t + 1)
        self.assertEqual((logged.confidence, logged.pan, logged.tilt), (0.0, 0.0, 0.0))
        self.assertEqual(logged.box, [0.0, 0.0, 1.0, 1.0])     # clamped into the frame

        def refuse(constant):
            raise ValueError(constant)
        line = (self.folder / "sightings-2026-10-07.jsonl").read_text()
        json.loads(line, parse_constant=refuse)                 # no NaN or Infinity in the file

    def test_lock_and_drop_in_the_same_call(self):
        # The real tracker never does this, but the logger shouldn't get confused
        log = self.make(min_duration_s=0)
        t = local(2026, 10, 7, 14, 0, 0)
        log.update(det(), True, FakeFrame(), 0, 0, now=t)
        logged = log.update(det(), False, FakeFrame(), 0, 0, now=t + 1)
        self.assertEqual((logged.frames, logged.duration_s), (2, 1.0))
        self.assertIsNone(log.current())


class CategoryTest(LoggerTestCase):
    def test_default_lists_ignore_case(self):
        log = self.make()
        self.assertEqual(log.categorize("drone"), "drone")
        self.assertEqual(log.categorize("Drone"), "drone")
        self.assertEqual(log.categorize("AIRPLANE"), "aircraft")
        self.assertEqual(log.categorize("Helicopter"), "aircraft")
        self.assertEqual(log.categorize("aircraft"), "aircraft")
        self.assertEqual(log.categorize("bird"), "other")
        self.assertEqual(log.categorize(""), "other")

    def test_custom_lists(self):
        log = self.make(drone_classes=["Quadcopter"], aircraft_classes=["glider"])
        self.assertEqual(log.categorize("QUADCOPTER"), "drone")
        self.assertEqual(log.categorize("Glider"), "aircraft")
        self.assertEqual(log.categorize("drone"), "other")
        self.assertEqual(log.categorize("airplane"), "other")

    def test_logged_sightings_carry_their_category(self):
        log = self.make(min_duration_s=0)
        t = local(2026, 10, 7, 14, 0, 0)
        self.assertEqual(log_sighting(log, t, name="Drone").category, "drone")
        self.assertEqual(log_sighting(log, t + 10, name="bird").category, "other")


class SnapshotTest(LoggerTestCase):
    def test_snapshots_off(self):
        def no_shrink(frame, max_w):
            raise AssertionError("shouldn't shrink with snapshots off")
        log = self.make(min_duration_s=0, snapshots=False, shrink=no_shrink)
        logged = log_sighting(log, local(2026, 10, 7, 14, 0, 0))
        self.assertIsNone(logged.snapshot)
        self.assertIsNotNone(logged.box)                        # the box is still useful
        self.assertFalse((self.folder / "snapshots").exists())

    def test_no_frame_means_no_box_and_no_snapshot(self):
        log = self.make(min_duration_s=0)
        t = local(2026, 10, 7, 14, 0, 0)
        log.update(det(), True, None, 0, 0, now=t)
        logged = log.update(None, False, None, 0, 0, now=t + 1)
        self.assertIsNone(logged.box)
        self.assertIsNone(logged.snapshot)

    def test_failed_snapshot_still_logs_the_sighting(self):
        def broken_encoder(image):
            raise RuntimeError("no OpenCV here")
        log = self.make(min_duration_s=0, encode_jpeg=broken_encoder)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            first = log_sighting(log, local(2026, 10, 7, 14, 0, 0))
            second = log_sighting(log, local(2026, 10, 7, 14, 5, 0))
        self.assertEqual((first.snapshot, second.snapshot), (None, None))
        self.assertEqual(len(log.recent()[0]), 2)
        self.assertEqual(out.getvalue().count("WARN"), 1)      # said once, not every time
        self.assertEqual(list(self.folder.glob("snapshots/*")), [])

    def test_failed_shrink_still_logs_the_sighting(self):
        def broken_shrink(frame, max_w):
            raise ImportError("No module named 'cv2'")
        log = self.make(min_duration_s=0, shrink=broken_shrink)
        with contextlib.redirect_stdout(io.StringIO()):
            logged = log_sighting(log, local(2026, 10, 7, 14, 0, 0))
        self.assertIsNone(logged.snapshot)
        self.assertIsNotNone(logged.box)

    def test_snapshot_path_only_accepts_plain_existing_names(self):
        log = self.make(min_duration_s=0)
        logged = log_sighting(log, local(2026, 10, 7, 14, 0, 0))
        self.assertEqual(log.snapshot_path(logged.snapshot),
                         self.folder / "snapshots" / logged.snapshot)
        (self.folder / "secret.jpg").write_bytes(b"not for the web")
        (self.folder / "snapshots" / "folder.jpg").mkdir()
        for bad in ["../secret.jpg", "..%2Fsecret.jpg", "..\\secret.jpg", "/etc/passwd",
                    str(self.folder / "secret.jpg"), "snapshots/x.jpg", "..jpg", ".jpg",
                    "x.png", "x.JPG", "a b.jpg", logged.snapshot + "\n", "", None, 42,
                    "missing.jpg", "folder.jpg"]:
            self.assertIsNone(log.snapshot_path(bad), bad)


class FileTest(LoggerTestCase):
    def test_new_logger_reloads_the_files_and_skips_damaged_lines(self):
        log = self.make(min_duration_s=0)
        plane = log_sighting(log, local(2026, 10, 7, 14, 0, 0), name="airplane")
        drone = log_sighting(log, local(2026, 10, 7, 14, 10, 0), name="drone")
        good = drone.to_dict()
        damaged = [
            "not json at all",
            "[1, 2, 3]",
            json.dumps({k: v for k, v in good.items() if k != "frames"}),    # missing a field
            json.dumps({**good, "id": "nan-1", "confidence": float("nan")}),
            json.dumps({**good, "id": "kind-1", "kind": "party"}),
            json.dumps({**good, "id": "../evil"}),
            json.dumps({**good, "id": "snap-1", "snapshot": "../../etc/passwd"}),
            json.dumps({**good, "id": "bool-1", "frames": True}),
            json.dumps({**good, "id": "huge-1", "start": 10 ** 400}),
            json.dumps(plane.to_dict()),                                       # same id again
        ]
        with open(self.folder / "sightings-2026-10-07.jsonl", "a") as f:
            f.write("\n".join(["", "   "] + damaged) + "\n")             # blank lines are fine
        # Files that must not even be read: too old, and not named like ours
        (self.folder / "sightings-2026-09-01.jsonl").write_text("garbage\n")
        (self.folder / "sightings-notes.jsonl").write_text("garbage\n")

        self.clock.t = local(2026, 10, 7, 15, 0, 0)
        again, printed = self.quietly(lambda: self.make())
        self.assertEqual(again.skipped_lines, len(damaged))
        self.assertIn(f"skipped {len(damaged)} damaged line(s)", printed)
        self.assertEqual(again.recent(), ([drone.to_dict(), plane.to_dict()], False))
        self.assertEqual(again.history_start, plane.start)       # earlier than its own start
        self.assertEqual(again.started_at, self.clock.t)

        # keep_hours limits what's loaded, even from today's file
        self.clock.t = local(2026, 10, 7, 15, 5, 0)
        short, _ = self.quietly(lambda: self.make(keep_hours=1))
        self.assertEqual(ids(short.recent()[0]), [drone.id])
        self.assertEqual(short.history_start, drone.start)

    def test_line_cut_short_by_a_crash_loses_only_itself(self):
        t = local(2026, 10, 7, 14, 0, 0)
        log_sighting(self.make(min_duration_s=0), t)
        with open(self.folder / "sightings-2026-10-07.jsonl", "a") as f:
            f.write('{"id": "20261007-1')                      # power cut mid-write
        second, _ = self.quietly(lambda: self.make(min_duration_s=0))
        log_sighting(second, t + 600)
        third, _ = self.quietly(lambda: self.make())
        self.assertEqual(len(third.recent()[0]), 2)
        self.assertEqual(third.skipped_lines, 1)

    def test_ids_stay_unique_across_runs(self):
        t = local(2026, 10, 7, 14, 2, 17)
        # A snapshot left over from a run whose log line is gone: never overwrite it
        (self.folder / "snapshots").mkdir(parents=True)
        (self.folder / "snapshots" / "20261007-140217-001.jpg").write_bytes(b"old")
        first = log_sighting(self.make(min_duration_s=0), t, duration=0.25)
        self.assertEqual(first.id, "20261007-140217-002")
        self.assertEqual((self.folder / "snapshots" / "20261007-140217-001.jpg").read_bytes(),
                         b"old")

        second_run = self.make(min_duration_s=0)                # counter starts again at 1
        second = log_sighting(second_run, t + 0.5, duration=0.25)   # same second as `first`
        self.assertEqual(second.id, "20261007-140217-003")      # 001 and 002 are taken
        third = log_sighting(second_run, t + 60)
        self.assertEqual(third.id, "20261007-140317-004")       # the counter keeps counting
        self.assertEqual(len(list(self.folder.glob("snapshots/*.jpg"))), 4)

    def test_sightings_around_midnight(self):
        log = self.make(min_duration_s=0)
        start = local(2026, 10, 7, 23, 59, 59) + 0.5
        log.update(det(), True, FakeFrame(), 0, 0, now=start)
        log.update(det(), True, FakeFrame(), 0, 0, now=start + 2)       # into the next day
        late = log.update(None, False, FakeFrame(), 0, 0, now=start + 3)
        early = log_sighting(log, local(2026, 10, 8, 0, 5, 0))
        self.assertEqual((late.id, early.id), ("20261007-235959-001", "20261008-000500-002"))

        def ids_in(day):
            path = self.folder / f"sightings-{day}.jsonl"
            return [json.loads(line)["id"] for line in path.read_text().splitlines()]
        self.assertEqual(ids_in("2026-10-07"), [late.id])        # filed by the day it started
        self.assertEqual(ids_in("2026-10-08"), [early.id])

        self.clock.t = local(2026, 10, 8, 1, 0, 0)
        again = self.make()
        self.assertEqual(ids(again.recent()[0]), [early.id, late.id])
        buckets = again.stats(now=local(2026, 10, 8, 0, 30, 0), hours=2)["buckets"]
        self.assertEqual([(b["start"], b["aircraft"]) for b in buckets],
                         [(local(2026, 10, 7, 23, 0, 0), 1), (local(2026, 10, 8, 0, 0, 0), 1)])

    def test_old_records_are_forgotten_but_stay_on_disk(self):
        t = local(2026, 10, 7, 10, 0, 0)
        self.clock.t = t
        log = self.make(min_duration_s=0, keep_hours=1)
        first = log_sighting(log, t)
        second = log_sighting(log, t + 2 * 3600)              # logging this prunes the first
        self.assertEqual(ids(log.recent()[0]), [second.id])
        self.assertAlmostEqual(log.history_start, second.end + 0.25 - 3600)
        lines = (self.folder / "sightings-2026-10-07.jsonl").read_text().splitlines()
        self.assertEqual([json.loads(line)["id"] for line in lines], [first.id, second.id])

    def test_nothing_is_written_until_something_happens(self):
        log = self.make()
        self.assertFalse(self.folder.exists())
        self.assertIsNone(log.current())
        self.assertEqual(log.recent(), ([], False))
        self.assertEqual(log.stats()["total"], 0)
        self.assertEqual(log.history_start, log.started_at)


class RecentTest(LoggerTestCase):
    def setUp(self):
        super().setUp()
        base = local(2026, 10, 7, 10, 0, 0)
        kinds = [("sighting", "aircraft"), ("sighting", "drone"), ("check", "clear"),
                 ("sighting", "aircraft"), ("sighting", "other"), ("check", "clear"),
                 ("sighting", "aircraft")]
        self.records = [record(f"r{i}", base + i * 60, kind, category)
                        for i, (kind, category) in enumerate(kinds, start=1)]
        self.write_records(self.records)
        self.clock.t = local(2026, 10, 7, 12, 0, 0)
        self.log = self.make()

    def test_newest_first(self):
        items, more = self.log.recent()
        self.assertEqual(ids(items), ["r7", "r6", "r5", "r4", "r3", "r2", "r1"])
        self.assertFalse(more)
        self.assertEqual(items[0], self.records[-1].to_dict())

    def test_pages_with_before(self):
        self.assertEqual(self.recent_ids(limit=3), (["r7", "r6", "r5"], True))
        self.assertEqual(self.recent_ids(limit=3, before="r5"), (["r4", "r3", "r2"], True))
        self.assertEqual(self.recent_ids(limit=3, before="r2"), (["r1"], False))
        self.assertEqual(self.recent_ids(limit=3, before="r1"), ([], False))
        self.assertEqual(self.recent_ids(limit=7), (["r7", "r6", "r5", "r4", "r3", "r2", "r1"],
                                                    False))
        self.assertEqual(self.recent_ids(before="no-such-id"), ([], False))

    def test_filters(self):
        self.assertEqual(self.recent_ids(category="aircraft"), (["r7", "r4", "r1"], False))
        self.assertEqual(self.recent_ids(category="aircraft", limit=2), (["r7", "r4"], True))
        self.assertEqual(self.recent_ids(category="aircraft", limit=2, before="r4"),
                         (["r1"], False))
        self.assertEqual(self.recent_ids(category="aircraft", limit=1, before="r6"),
                         (["r4"], True))
        self.assertEqual(self.recent_ids(category="drone"), (["r2"], False))
        self.assertEqual(self.recent_ids(category="clear"), (["r6", "r3"], False))
        self.assertEqual(self.recent_ids(kind="check"), (["r6", "r3"], False))
        self.assertEqual(self.recent_ids(kind="sighting", limit=4), (["r7", "r5", "r4", "r2"],
                                                                     True))
        self.assertEqual(self.recent_ids(kind="check", category="aircraft"), ([], False))

    def test_since(self):
        since = self.records[4].start                          # r5's start counts
        self.assertEqual(self.recent_ids(since=since), (["r7", "r6", "r5"], False))
        self.assertEqual(self.recent_ids(since=since, limit=2), (["r7", "r6"], True))
        self.assertEqual(self.recent_ids(since=since, limit=3), (["r7", "r6", "r5"], False))
        self.assertEqual(self.recent_ids(since=since, category="drone"), ([], False))

    def test_new_records_join_in_time_order(self):
        logged = log_sighting(self.log, local(2026, 10, 7, 11, 0, 0))
        self.assertEqual(self.recent_ids(limit=2), ([logged.id, "r7"], True))

    def recent_ids(self, **options):
        items, more = self.log.recent(**options)
        return ids(items), more


class StatsTest(LoggerTestCase):
    def test_counts_last_previous_and_buckets(self):
        now = local(2026, 10, 7, 14, 20, 0)
        spans_the_hour = record("a1", local(2026, 10, 7, 13, 59, 59))
        spans_the_hour.end = local(2026, 10, 7, 14, 0, 30)
        self.write_records([
            record("c0", local(2026, 10, 5, 12, 0, 0), "check"),  # logs reach back 2 days
            record("p1", local(2026, 10, 5, 20, 0, 0)),            # previous window
            record("p2", now - 24 * 3600),                         # exactly 24 h ago: previous
            record("a0", local(2026, 10, 6, 14, 30, 0)),           # in the 24 h, before 1st hour
            record("o1", local(2026, 10, 6, 15, 0, 0), category="other"),   # first hour
            spans_the_hour,                                        # counts at its start: 13:00
            record("d1", local(2026, 10, 7, 14, 0, 0), category="drone"),   # 14:00 sharp
            record("k1", local(2026, 10, 7, 13, 0, 0), "check"),   # checks never count
            record("a2", now - 60),
            record("d2", now, category="drone"),                   # now itself counts
            record("f1", now + 60),                                # in the future: not yet
        ])
        self.clock.t = now
        stats = self.make().stats(hours=24)
        self.assertEqual(set(stats), {"hours", "now", "total", "drone", "aircraft", "other",
                                      "previous_total", "last", "buckets"})
        self.assertEqual((stats["hours"], stats["now"]), (24, now))
        self.assertEqual((stats["total"], stats["aircraft"], stats["drone"], stats["other"]),
                         (6, 3, 2, 1))
        self.assertEqual(stats["previous_total"], 2)
        self.assertEqual(stats["last"], {"drone": now, "aircraft": now - 60,
                                         "other": local(2026, 10, 6, 15, 0, 0)})

        buckets = stats["buckets"]
        self.assertEqual(len(buckets), 24)
        self.assertEqual(buckets[0]["start"], local(2026, 10, 6, 15, 0, 0))
        self.assertEqual(buckets[-1]["start"], local(2026, 10, 7, 14, 0, 0))   # current hour
        self.assertTrue(buckets[-1]["start"] <= now < buckets[-1]["start"] + 3600)
        for earlier, later in zip(buckets, buckets[1:]):
            self.assertEqual(later["start"] - earlier["start"], 3600)
        for b in buckets:
            self.assertEqual(datetime.fromtimestamp(b["start"]).strftime("%M:%S"), "00:00")
            self.assertEqual(set(b), {"start", "aircraft", "drone", "other"})
        counted = {i: (b["aircraft"], b["drone"], b["other"])
                   for i, b in enumerate(buckets) if b["aircraft"] or b["drone"] or b["other"]}
        self.assertEqual(counted, {0: (0, 0, 1), 22: (1, 0, 0), 23: (1, 2, 0)})

        one_hour = self.make().stats(hours=1)
        self.assertEqual(len(one_hour["buckets"]), 1)
        self.assertEqual((one_hour["total"], one_hour["aircraft"], one_hour["drone"]), (4, 2, 2))
        self.assertEqual(one_hour["previous_total"], 0)         # only a check in 12:20-13:20

    def test_previous_total_is_none_until_the_logs_cover_it(self):
        start = local(2026, 10, 7, 8, 0, 0)
        self.clock.t = start
        log = self.make()
        self.assertIsNone(log.stats(now=start + 48 * 3600 - 1)["previous_total"])
        self.assertEqual(log.stats(now=start + 48 * 3600)["previous_total"], 0)
        self.assertIsNone(log.stats(now=start + 3600, hours=1)["previous_total"])
        self.assertEqual(log.stats(now=start + 7200, hours=1)["previous_total"], 0)

    def test_live_sightings_count(self):
        log = self.make(min_duration_s=0)
        t = local(2026, 10, 7, 14, 0, 0)
        log_sighting(log, t, name="drone")
        stats = log.stats(now=t + 10)
        self.assertEqual((stats["total"], stats["drone"], stats["last"]["drone"]), (1, 1, t))
        self.assertEqual(stats["buckets"][-1]["drone"], 1)
        self.assertIsNone(stats["last"]["aircraft"])

    def test_hours_are_local_clock_hours_half_an_hour_off_utc(self):
        use_timezone(self, "IST-5:30")                          # India, UTC+5:30
        now = utc(2026, 10, 7, 8, 50, 0)                        # 14:20 in India
        self.clock.t = now
        starts = [b["start"] for b in self.make().stats(hours=3)["buckets"]]
        self.assertEqual(starts, [utc(2026, 10, 7, 6, 30, 0), utc(2026, 10, 7, 7, 30, 0),
                                  utc(2026, 10, 7, 8, 30, 0)])  # 12:00, 13:00, 14:00 local

    def test_autumn_daylight_saving_hour_appears_twice(self):
        use_timezone(self, "EST5EDT,M3.2.0,M11.1.0")            # US Eastern
        # 1 Nov 2026: at 02:00 EDT the clocks go back to 01:00 EST
        self.write_records([record("edt", utc(2026, 11, 1, 5, 30, 0)),    # 01:30 EDT
                            record("est", utc(2026, 11, 1, 6, 30, 0))])   # 01:30 EST
        now = utc(2026, 11, 1, 8, 30, 0)                        # 03:30 EST
        self.clock.t = now
        buckets = self.make().stats(hours=5)["buckets"]
        self.assertEqual([b["start"] for b in buckets],
                         [utc(2026, 11, 1, h, 0, 0) for h in (4, 5, 6, 7, 8)])
        self.assertEqual([datetime.fromtimestamp(b["start"]).hour for b in buckets],
                         [0, 1, 1, 2, 3])
        self.assertEqual([b["aircraft"] for b in buckets], [0, 1, 1, 0, 0])

    def test_spring_daylight_saving_hour_is_skipped(self):
        use_timezone(self, "EST5EDT,M3.2.0,M11.1.0")
        # 8 Mar 2026: at 02:00 EST the clocks jump to 03:00 EDT
        now = utc(2026, 3, 8, 8, 30, 0)                         # 04:30 EDT
        self.clock.t = now
        buckets = self.make().stats(hours=4)["buckets"]
        self.assertEqual([b["start"] for b in buckets],
                         [utc(2026, 3, 8, h, 0, 0) for h in (5, 6, 7, 8)])
        self.assertEqual([datetime.fromtimestamp(b["start"]).hour for b in buckets],
                         [0, 1, 3, 4])


class HeartbeatTest(LoggerTestCase):
    def quiet_frame(self, log, t):
        """A frame with nothing tracked."""
        return log.update(None, False, FakeFrame(), 90.0, 45.0, now=t)

    def check_starts(self, log):
        return [c["start"] for c in log.recent(kind="check")[0]][::-1]    # oldest first

    def test_crossing_the_hour_logs_one_check(self):
        log = self.make(heartbeat_min=60)
        self.assertIsNone(self.quiet_frame(log, local(2026, 10, 7, 13, 59, 58)))
        self.assertIsNone(self.quiet_frame(log, local(2026, 10, 7, 13, 59, 59)))
        t = local(2026, 10, 7, 14, 0, 0) + 0.05
        self.assertIsNone(self.quiet_frame(log, t))             # logged, but not returned
        self.quiet_frame(log, local(2026, 10, 7, 14, 0, 1))
        self.quiet_frame(log, local(2026, 10, 7, 14, 30, 0))
        checks, more = log.recent(kind="check")
        start = round(t, 3)
        self.assertEqual(checks, [{
            "id": "20261007-140000-001", "kind": "check", "category": "clear",
            "class_name": "", "start": start, "end": start, "duration_s": 0.0,
            "confidence": 0.0, "pan": 90.0, "tilt": 45.0, "box": None, "frames": 0,
            "snapshot": None}])
        line = (self.folder / "sightings-2026-10-07.jsonl").read_text()
        self.assertEqual(json.loads(line), checks[0])
        self.assertEqual(log.stats(now=t)["total"], 0)          # checks aren't sightings

    def test_not_on_the_first_frame(self):
        log = self.make(heartbeat_min=60)
        self.quiet_frame(log, local(2026, 10, 7, 14, 0, 0))     # starts right on the hour
        self.quiet_frame(log, local(2026, 10, 7, 14, 0, 1))
        self.quiet_frame(log, local(2026, 10, 7, 14, 59, 59))
        self.assertEqual(self.check_starts(log), [])
        self.quiet_frame(log, local(2026, 10, 7, 15, 0, 0))
        self.assertEqual(self.check_starts(log), [local(2026, 10, 7, 15, 0, 0)])

    def test_far_apart_frames_still_notice_the_boundary(self):
        log = self.make(heartbeat_min=60)
        self.quiet_frame(log, local(2026, 10, 7, 13, 59, 0))
        self.quiet_frame(log, local(2026, 10, 7, 14, 20, 0))    # 21 minutes later
        self.quiet_frame(log, local(2026, 10, 7, 17, 5, 0))     # past 15:00, 16:00 and 17:00
        self.assertEqual(self.check_starts(log), [local(2026, 10, 7, 14, 20, 0),
                                                  local(2026, 10, 7, 17, 5, 0)])

    def test_skipped_while_something_is_tracked(self):
        log = self.make(heartbeat_min=60)
        self.quiet_frame(log, local(2026, 10, 7, 13, 59, 0))
        log.update(det(), True, FakeFrame(), 0, 0, now=local(2026, 10, 7, 13, 59, 50))
        log.update(det(), True, FakeFrame(), 0, 0, now=local(2026, 10, 7, 13, 59, 55))
        log.update(None, True, FakeFrame(), 0, 0, now=local(2026, 10, 7, 14, 0, 5))  # a miss
        logged = log.update(None, False, FakeFrame(), 0, 0, now=local(2026, 10, 7, 14, 0, 20))
        self.assertEqual(logged.kind, "sighting")
        self.quiet_frame(log, local(2026, 10, 7, 14, 30, 0))
        self.assertEqual(self.check_starts(log), [])            # 14:00 was during the lock

        # A target turning up on the very frame that crosses the hour: no check either
        self.quiet_frame(log, local(2026, 10, 7, 14, 59, 59))
        log.update(det(), True, FakeFrame(), 0, 0, now=local(2026, 10, 7, 15, 0, 0))
        log.update(None, False, FakeFrame(), 0, 0, now=local(2026, 10, 7, 15, 0, 10))
        self.quiet_frame(log, local(2026, 10, 7, 15, 30, 0))
        self.assertEqual(self.check_starts(log), [])

        self.quiet_frame(log, local(2026, 10, 7, 16, 0, 0) + 0.1)
        self.assertEqual(self.check_starts(log), [round(local(2026, 10, 7, 16, 0, 0) + 0.1, 3)])

    def test_zero_turns_it_off(self):
        log = self.make(heartbeat_min=0)
        for minute in range(0, 600, 7):
            self.quiet_frame(log, local(2026, 10, 7, 8, 0, 0) + minute * 60)
        self.assertEqual(self.check_starts(log), [])
        self.assertFalse(self.folder.exists())

    def test_every_15_minutes(self):
        log = self.make(heartbeat_min=15)
        for parts in [(14, 14, 59), (14, 15, 0), (14, 29, 59), (14, 30, 0), (14, 31, 0)]:
            self.quiet_frame(log, local(2026, 10, 7, *parts))
        self.assertEqual(self.check_starts(log), [local(2026, 10, 7, 14, 15, 0),
                                                  local(2026, 10, 7, 14, 30, 0)])

    def test_midnight(self):
        log = self.make(heartbeat_min=60)
        self.quiet_frame(log, local(2026, 10, 7, 23, 59, 59))
        self.quiet_frame(log, local(2026, 10, 8, 0, 0, 0) + 0.5)
        checks = log.recent(kind="check")[0]
        self.assertEqual(ids(checks), ["20261008-000000-001"])
        self.assertTrue((self.folder / "sightings-2026-10-08.jsonl").exists())

    def test_local_hours_half_an_hour_off_utc(self):
        use_timezone(self, "IST-5:30")
        log = self.make(heartbeat_min=60)
        for t in [utc(2026, 10, 7, 7, 29, 59), utc(2026, 10, 7, 7, 30, 0),   # 13:00 in India
                  utc(2026, 10, 7, 8, 0, 0), utc(2026, 10, 7, 8, 30, 0)]:    # 13:30, 14:00
            self.quiet_frame(log, t)
        self.assertEqual(self.check_starts(log), [utc(2026, 10, 7, 7, 30, 0),
                                                  utc(2026, 10, 7, 8, 30, 0)])

    def test_daylight_saving_changes(self):
        use_timezone(self, "EST5EDT,M3.2.0,M11.1.0")
        spring = self.make(self.folder / "spring", heartbeat_min=60)
        self.quiet_frame(spring, utc(2026, 3, 8, 6, 59, 59))    # 01:59:59 EST
        self.quiet_frame(spring, utc(2026, 3, 8, 7, 0, 0))      # 03:00:00 EDT
        self.assertEqual(self.check_starts(spring), [utc(2026, 3, 8, 7, 0, 0)])

        autumn = self.make(self.folder / "autumn", heartbeat_min=60)
        self.quiet_frame(autumn, utc(2026, 11, 1, 5, 59, 59))   # 01:59:59 EDT
        self.quiet_frame(autumn, utc(2026, 11, 1, 6, 0, 0))     # 01:00:00 EST: checked already
        self.quiet_frame(autumn, utc(2026, 11, 1, 6, 59, 59))
        self.quiet_frame(autumn, utc(2026, 11, 1, 7, 0, 0))     # 02:00:00 EST
        self.assertEqual(self.check_starts(autumn), [utc(2026, 11, 1, 7, 0, 0)])


class ThreadTest(LoggerTestCase):
    def test_web_threads_can_read_while_the_main_loop_logs(self):
        log = self.make(min_duration_s=0, snapshots=False, heartbeat_min=1)
        stop = threading.Event()
        errors = []

        def reader():
            # Like a browser polling the dashboard. The short pause matters: three threads
            # spinning flat out would starve the main thread of Python's GIL for minutes.
            while not stop.wait(0.001):
                try:
                    log.recent(limit=5, category="aircraft")
                    log.stats(hours=24)
                    log.current()
                    log.snapshot_path("x.jpg")
                except Exception as error:      # noqa: BLE001  (any error fails the test)
                    errors.append(error)
                    return
        readers = [threading.Thread(target=reader) for _ in range(3)]
        for thread in readers:
            thread.start()
        t = local(2026, 10, 7, 14, 0, 15)
        for i in range(200):
            start = t + i * 30
            self.clock.t = start
            log_sighting(log, start)
            # A quiet frame 20 s later: every other one crosses a minute, so it logs a check
            log.update(None, False, None, 0, 0, now=start + 20)
        stop.set()
        for thread in readers:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(log.recent(kind="sighting", limit=1000)[0]), 200)
        self.assertGreater(len(log.recent(kind="check", limit=1000)[0]), 50)


class WithoutOpenCVTest(unittest.TestCase):
    def test_module_imports_without_opencv_or_numpy(self):
        code = ("import sys; sys.modules['cv2'] = None; sys.modules['numpy'] = None; "
                "import brain.logger")
        result = subprocess.run([sys.executable, "-c", code], cwd=REPO,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(HAS_CV2, "needs OpenCV and numpy")
class DefaultImageHelpersTest(unittest.TestCase):
    def test_shrink_and_encode(self):
        import numpy as np
        frame = np.zeros((720, 1280, 3), np.uint8)
        self.assertEqual(default_shrink(frame, 640).shape, (360, 640, 3))
        narrow = np.zeros((100, 200, 3), np.uint8)
        copy = default_shrink(narrow, 640)
        self.assertEqual(copy.shape, narrow.shape)
        self.assertFalse(np.shares_memory(copy, narrow))        # drawing on the frame is safe
        self.assertEqual(default_encode_jpeg(copy)[:2], b"\xff\xd8")   # JPEG files start so


if __name__ == "__main__":
    unittest.main()
