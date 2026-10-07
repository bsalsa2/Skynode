"""Tests for brain/demo.py: the demo on a folder of test videos.

The videos are made here (a few tiny frames each), and the detector is a
stand-in that sees a bright square. Everything else is the real thing: the
tracker, the logger, the SQLite log and the dashboard.
Needs numpy, OpenCV and onnxruntime, because brain/run.py imports them.
"""
import contextlib
import importlib.util
import io
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

NEEDED = ("numpy", "cv2", "onnxruntime")
if not all(importlib.util.find_spec(name) for name in NEEDED):
    raise unittest.SkipTest("needs " + ", ".join(NEEDED))

import cv2                                                  # noqa: E402
import numpy as np                                          # noqa: E402

from brain import demo                                      # noqa: E402
from brain.detector import Detection                        # noqa: E402
from brain.logger import COLUMNS, Sighting, row_to_dict     # noqa: E402

WIDTH, HEIGHT = 64, 48
SQUARE_X = 48       # centre of the bright square: right of the middle (32)


def make_video(path, frames=12, target=range(3, 10), fps=10):
    """A tiny MJPG video. The frames in `target` have a bright square in them."""
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (WIDTH, HEIGHT))
    for n in range(frames):
        frame = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
        if n in target:
            frame[HEIGHT // 2 - 6:HEIGHT // 2 + 6, SQUARE_X - 6:SQUARE_X + 6] = 255
        writer.write(frame)
    writer.release()


class SquareDetector:
    """Stands in for brain.detector.Detector: sees an airplane wherever the bright square is."""
    class_names = ["airplane", "bird"]

    def __init__(self, model_path, min_confidence, iou_threshold):
        pass

    def detect(self, frame):
        mask = frame[:, :, 0] > 200
        if mask.sum() < 20:
            return []
        ys, xs = np.nonzero(mask)
        return [Detection(0, "airplane", 0.9,
                          (xs.min(), ys.min(), xs.max(), ys.max()))]


def read_log(folder):
    with contextlib.closing(sqlite3.connect(Path(folder) / "skynode.db")) as conn:
        rows = conn.execute(f"SELECT {', '.join(COLUMNS)} FROM sightings ORDER BY rowid").fetchall()
    return [Sighting.from_dict(row_to_dict(row)).to_dict() for row in rows]


class FindVideosTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)

    def test_videos_in_file_name_order_and_nothing_else(self):
        for name in ["b.mp4", "A.MOV", "c.avi", "d.webm", "e.mkv", "f.m4v",
                     "notes.txt", "photo.jpg", "movie", ".hidden.mp4"]:
            (self.folder / name).write_bytes(b"x")
        (self.folder / "sub").mkdir()
        (self.folder / "sub" / "deep.mp4").write_bytes(b"x")        # sub-folders aren't searched
        (self.folder / "folder.mp4").mkdir()                        # a folder named like a video
        names = [path.name for path in demo.find_videos(self.folder)]
        self.assertEqual(names, ["A.MOV", "b.mp4", "c.avi", "d.webm", "e.mkv", "f.m4v"])

    def test_not_a_folder_and_no_videos_say_so(self):
        with self.assertRaises(SystemExit) as raised:
            demo.find_videos(self.folder / "missing")
        self.assertIn("isn't a folder", str(raised.exception))
        (self.folder / "notes.txt").write_text("hi")
        with self.assertRaises(SystemExit) as raised:
            demo.find_videos(self.folder)
        self.assertIn("No videos", str(raised.exception))


class RepoSafetyTest(unittest.TestCase):
    def setUp(self):
        if shutil.which("git") is None:
            self.skipTest("needs git")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name).resolve() / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        (self.repo / ".gitignore").write_text("/demo_videos/\n")
        patcher = mock.patch.object(demo, "REPO", self.repo)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_folder_outside_the_repo_is_fine(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            demo.refuse_unignored_repo_folder(elsewhere)

    def test_an_ignored_folder_inside_the_repo_is_fine(self):
        (self.repo / "demo_videos").mkdir()
        demo.refuse_unignored_repo_folder(self.repo / "demo_videos")

    def test_a_folder_inside_the_repo_that_git_would_pick_up_is_refused(self):
        (self.repo / "clips").mkdir()
        with self.assertRaises(SystemExit) as raised:
            demo.refuse_unignored_repo_folder(self.repo / "clips")
        self.assertIn("does NOT ignore", str(raised.exception))
        self.assertIn("outside the repo", str(raised.exception))

    def test_the_repo_folder_itself_is_refused_too(self):
        with self.assertRaises(SystemExit):
            demo.refuse_unignored_repo_folder(self.repo)

    def test_without_git_it_does_not_get_in_the_way(self):
        (self.repo / "clips").mkdir()
        with mock.patch("brain.demo.subprocess.run", side_effect=FileNotFoundError("git")):
            demo.refuse_unignored_repo_folder(self.repo / "clips")


class VideoClockTest(unittest.TestCase):
    def test_it_only_moves_when_the_videos_do(self):
        wall = [1000.0]
        clock = demo.VideoClock(wall=lambda: wall[0])
        self.assertEqual(clock(), 1000.0)
        wall[0] += 50                       # real time passes, demo time doesn't
        self.assertEqual(clock(), 1000.0)
        clock.advance(0.04)
        clock.advance(0.04)
        self.assertAlmostEqual(clock(), 1000.08)

    def test_after_run_free_it_follows_the_real_clock_again(self):
        wall = [1000.0]
        clock = demo.VideoClock(wall=lambda: wall[0])
        clock.advance(10)
        clock.run_free()
        self.assertEqual(clock(), 1010.0)
        wall[0] += 7
        self.assertEqual(clock(), 1017.0)
        clock.advance(100)                  # videos are over: ignored
        clock.run_free()                    # and asking twice changes nothing
        self.assertEqual(clock(), 1017.0)


class VideoFileTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "clip.avi"
        make_video(self.path, frames=6, fps=10)

    def test_real_time_waits_between_frames(self):
        now, slept = [100.0], []

        def sleep(seconds):
            slept.append(seconds)
            now[0] += seconds
        video = demo.VideoFile(self.path, realtime=True, clock=lambda: now[0], sleep=sleep)
        reads = [video.read()[0] for _ in range(4)]
        video.release()
        self.assertEqual(reads, [True] * 4)
        self.assertEqual(len(slept), 3)                     # the first frame comes straight away
        for seconds in slept:
            self.assertAlmostEqual(seconds, 0.1, places=3)  # 10 frames per second

    def test_running_late_does_not_burst_to_catch_up(self):
        now, slept = [0.0], []

        def sleep(seconds):
            slept.append(seconds)
            now[0] += seconds
        video = demo.VideoFile(self.path, realtime=True, clock=lambda: now[0], sleep=sleep)
        video.read()
        now[0] += 5.0                       # a very slow frame: 5 seconds behind
        video.read()
        self.assertEqual(slept, [])         # nothing to wait for: we're late
        for _ in range(3):
            video.read()
        # Not a burst of instant frames to catch up: the usual spacing resumes right away
        self.assertEqual(len(slept), 3)
        for seconds in slept:
            self.assertAlmostEqual(seconds, 0.1, places=3)

    def test_every_frame_read_moves_the_demo_clock_by_one_interval(self):
        wall = [1000.0]
        clock = demo.VideoClock(wall=lambda: wall[0])
        video = demo.VideoFile(self.path, realtime=False, demo_clock=clock)
        frames = 0
        while video.read()[0]:
            frames += 1
        video.read()                        # past the end: no frame, so no time
        self.assertEqual(frames, 6)
        self.assertAlmostEqual(clock(), 1000.0 + 6 * 0.1)

    def test_fast_never_waits(self):
        slept = []
        video = demo.VideoFile(self.path, realtime=False, sleep=slept.append)
        while video.read()[0]:
            pass
        self.assertEqual(slept, [])

    def test_a_file_that_is_not_a_video_raises(self):
        junk = self.path.with_name("junk.mp4")
        junk.write_bytes(b"not a video")
        with self.assertRaises(OSError):
            demo.VideoFile(junk)


class DemoRunTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.videos = self.root / "videos"
        self.videos.mkdir()
        make_video(self.videos / "a_first.avi")
        make_video(self.videos / "b_second.avi")
        (self.root / "fake.onnx").write_bytes(b"")
        (self.root / "config.toml").write_text(
            '[model]\npath = "fake.onnx"\ntarget_classes = ["airplane"]\n'
            '[logger]\nheartbeat_min = 0\n'      # the normal half-second blink filter stays ON
            '[dashboard]\nport = 0\n')
        self.logs = self.root / "logs" / "demo"
        for patcher in (mock.patch.object(demo, "DEMO_LOGS", self.logs),
                        mock.patch("brain.demo.Detector", SquareDetector)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def demo(self, *flags, folder=None):
        argv = [str(folder or self.videos), "--config", str(self.root / "config.toml"),
                "--fast", "--exit-when-done", *flags]
        with contextlib.redirect_stdout(io.StringIO()) as out:
            demo.main(argv)
        return out.getvalue()

    def test_every_video_is_played_and_logged_by_the_real_pipeline(self):
        printed = self.demo()
        self.assertIn("Video 1/2: a_first.avi", printed)
        self.assertIn("Video 2/2: b_second.avi", printed)
        self.assertIn("Model: ", printed)
        self.assertIn("Not a live camera; pan/tilt are simulated.", printed)
        self.assertIn("Demo finished: 2 sighting(s) logged", printed)

        records = read_log(self.logs)
        self.assertEqual([(r["kind"], r["category"], r["class_name"]) for r in records],
                         [("sighting", "aircraft", "airplane")] * 2)    # one per video
        self.assertTrue(all(r["frames"] >= 5 for r in records))
        # Timed by the video (7 frames seen at 10 fps = 0.6 s), not by how fast the computer
        # went. At --fast that's a few milliseconds, which the 0.5 s blink filter would drop.
        self.assertTrue(all(abs(r["duration_s"] - 0.6) < 0.15 for r in records),
                        [r["duration_s"] for r in records])
        self.assertLess(records[0]["end"], records[1]["start"])     # the clips don't run together
        self.assertTrue(all(r["snapshot"] for r in records))
        self.assertEqual(len(list((self.logs / "snapshots").glob("*.jpg"))), 2)
        self.assertNotIn("dashboard", [t.name for t in threading.enumerate()])    # stopped again

    def test_pan_and_tilt_are_simulated_from_where_the_target_is_and_do_not_drift(self):
        self.demo()
        records = read_log(self.logs)
        # The square is right of the middle, so (with the default pan_sign of -1)
        # the camera would have panned below home (90), and by the same amount every time.
        pans = [r["pan"] for r in records]
        self.assertTrue(all(60 < pan < 90 for pan in pans), pans)
        self.assertEqual(pans[0], pans[1])
        self.assertTrue(all(0.0 < r["tilt"] < 180.0 for r in records))      # not wound up to a limit

    def test_the_previous_demo_is_cleared_unless_asked_to_keep_it(self):
        self.demo()
        first_ids = [r["id"] for r in read_log(self.logs)]
        self.demo("--keep-logs")
        kept = [r["id"] for r in read_log(self.logs)]
        self.assertEqual(kept[:2], first_ids)
        self.assertEqual(len(kept), 4)
        self.demo()
        self.assertEqual(len(read_log(self.logs)), 2)       # afresh again

    def test_real_logs_are_never_touched(self):
        real = self.root / "logs"
        (real / "snapshots").mkdir(parents=True, exist_ok=True)
        (real / "skynode.db").write_bytes(b"the user's real log")
        (real / "snapshots" / "real.jpg").write_bytes(b"x")
        self.demo()
        self.assertEqual((real / "skynode.db").read_bytes(), b"the user's real log")
        self.assertTrue((real / "snapshots" / "real.jpg").exists())

    def test_the_videos_are_left_alone(self):
        before = {p.name: p.read_bytes() for p in self.videos.iterdir()}
        self.demo()
        self.assertEqual({p.name: p.read_bytes() for p in self.videos.iterdir()}, before)

    def test_missing_model_and_wrong_classes_say_what_to_do(self):
        with self.assertRaises(SystemExit) as raised:
            self.demo("--model", str(self.root / "nope.onnx"))
        self.assertIn("--model", str(raised.exception))
        with self.assertRaises(SystemExit) as raised:
            self.demo("--classes", "drone")
        self.assertIn("aren't in this model", str(raised.exception))

    def test_a_video_that_will_not_open_is_skipped_not_fatal(self):
        (self.videos / "c_broken.mp4").write_bytes(b"not a video")
        printed = self.demo()
        self.assertIn("WARN skipping this one", printed)
        self.assertIn("Demo finished: 2 sighting(s)", printed)


if __name__ == "__main__":
    unittest.main()
