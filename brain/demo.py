"""Skynode demo: detection, the sighting logger and the dashboard, on a folder of test videos.

Run from the repo root:
    python -m brain.demo ~/skynode-videos --model models/skynode-v2.onnx --classes drone,aircraft
    python -m brain.demo ~/skynode-videos --model m.onnx --fast          # don't wait for real time
    python -m brain.demo ~/skynode-videos --model m.onnx --loop          # play the folder forever

Then open the dashboard: http://localhost:8080/

This is the same code as `python -m brain.run` (the same detector, tracker,
logger and dashboard). Only the camera is different: your videos, one after
another, in file-name order. Nothing is turned on that isn't real:

  * It is labelled DEMO on the dashboard, because it isn't a live camera.
  * There is no Pico, so the pan and tilt are simulated from where the target
    is in the picture (see PanTiltController.simulate_aim).
  * It logs to logs/demo/, apart from your real logs, and starts that log
    afresh every time, so every number on the dashboard comes from this run.
  * Time in the demo is the videos' own time: it moves forward one frame
    interval for every frame read. So a 4-second clip is a 4-second sighting
    (and the logger's half-second blink filter works) even with --fast, which
    skips the waiting. Once the last video ends, time follows the real clock
    again, so the dashboard shows the feed as stopped, like a real node would.

Your videos are never copied or changed. Keep them OUTSIDE the repo folder (or
in a folder git ignores, like demo_videos/), so they can't be committed by
accident. The demo refuses a folder inside the repo that git doesn't ignore.
"""
import argparse
import shutil
import subprocess
import time
from pathlib import Path

import cv2

from brain.config import load_config
from brain.controller import PanTiltController
from brain.detector import Detector
from brain.link import NullLink
from brain.run import (DEFAULT_CONFIG, REPO, check_target_classes, make_dashboard, make_logger,
                       port_number, report, run_loop)
from brain.tracker import Tracker

VIDEO_SUFFIXES = {".mp4", ".m4v", ".mov", ".avi", ".mkv", ".webm"}
DEMO_LOGS = REPO / "logs" / "demo"      # inside logs/, which git ignores
DEFAULT_FPS = 25.0                      # for videos that don't say how fast they play
CUT_SECONDS = 1.0                       # demo time that passes between one video and the next


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run detection, the logger and the dashboard on a folder of test videos.")
    parser.add_argument("folder", type=Path, help="a folder with your test videos (not inside the repo)")
    parser.add_argument("--model", help="path to an .onnx model (default: [model] path in config.toml)")
    parser.add_argument("--classes",
                        help="comma-separated classes to track, like drone,aircraft "
                             "(default: [model] target_classes in config.toml)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="settings file (default: brain/config.toml)")
    parser.add_argument("--port", type=port_number, help="dashboard port (default: [dashboard] port)")
    parser.add_argument("--loop", action="store_true", help="play the whole folder again and again")
    parser.add_argument("--fast", action="store_true",
                        help="don't wait for each video's own speed: go as fast as detection can")
    parser.add_argument("--show", action="store_true", help="also open the OpenCV preview window")
    parser.add_argument("--keep-logs", action="store_true",
                        help="keep the previous demo's sightings instead of starting afresh")
    parser.add_argument("--exit-when-done", action="store_true",
                        help="quit after one pass instead of keeping the dashboard open")
    return parser.parse_args(argv)


def find_videos(folder):
    """The video files directly inside `folder`, in file-name order. Exits with a plain message if none."""
    folder = Path(folder).expanduser()
    if not folder.is_dir():
        raise SystemExit(f"{folder} isn't a folder. Give the folder that holds your test videos.")
    videos = sorted((path for path in folder.iterdir()
                     if path.is_file() and not path.name.startswith(".")
                     and path.suffix.lower() in VIDEO_SUFFIXES),
                    key=lambda path: path.name.lower())
    if not videos:
        raise SystemExit(f"No videos in {folder} (looked for {', '.join(sorted(VIDEO_SUFFIXES))}; "
                         "sub-folders aren't searched).")
    return videos


def refuse_unignored_repo_folder(folder):
    """Stop if the videos sit inside the repo where git would pick them up.

    A folder outside the repo is fine, and so is one that .gitignore covers.
    """
    folder = Path(folder).expanduser().resolve()
    try:
        folder.relative_to(REPO)
    except ValueError:
        return                          # outside the repo: git never sees it
    try:
        result = subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", "--", str(folder)],
                                capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return                          # no git here, so nothing can be committed either
    if result.returncode == 1:          # 0 = ignored, 1 = NOT ignored, anything else = couldn't ask
        raise SystemExit(
            f"{folder} is inside the repo and git does NOT ignore it, so these videos could be\n"
            "committed by accident. Move them outside the repo (for example ~/skynode-videos),\n"
            "or into demo_videos/ (which git ignores), and run the demo again.")


class VideoClock:
    """The demo's clock, for the logger and the dashboard. Call it for the time.

    It starts at the real time, then moves forward only when the videos do
    (advance(), once per frame), until run_free() lets it follow the real
    clock again.
    """

    def __init__(self, wall=time.time):
        self._wall = wall
        self.t = wall()
        self._free_since = None         # the real time at which run_free() was called

    def __call__(self):
        if self._free_since is None:
            return self.t
        return self.t + (self._wall() - self._free_since)

    def advance(self, seconds):
        if self._free_since is None:
            self.t += seconds

    def run_free(self):
        if self._free_since is None:
            self._free_since = self._wall()


class VideoFile:
    """One video file with the camera interface run_loop() uses: read() and release().

    realtime=True hands out frames at the video's own speed, so the demo looks
    like a live camera. realtime=False goes as fast as the detector can keep up.
    Either way every frame read moves `demo_clock` (a VideoClock) on by one
    frame interval, so durations are the video's, not the computer's.
    """

    def __init__(self, path, realtime=True, demo_clock=None, clock=time.monotonic, sleep=time.sleep):
        self.capture = cv2.VideoCapture(str(path))
        if not self.capture.isOpened():
            raise OSError(f"can't open {path}")
        fps = self.capture.get(cv2.CAP_PROP_FPS)
        self.interval = 1.0 / (fps if fps and 1.0 <= fps <= 240.0 else DEFAULT_FPS)
        self.realtime = realtime
        self.demo_clock = demo_clock
        self._clock, self._sleep = clock, sleep
        self._due = None                # when the next frame should be handed out

    def read(self):
        if self.realtime:
            now = self._clock()
            if self._due is None:
                self._due = now
            if self._due > now:
                self._sleep(self._due - now)
                now = self._due
            # Running late? Don't rush to catch up in a burst: keep the spacing from here.
            self._due = max(self._due, now) + self.interval
        ok, frame = self.capture.read()
        if ok and self.demo_clock is not None:
            self.demo_clock.advance(self.interval)
        return ok, frame

    def release(self):
        self.capture.release()


def start_afresh(folder):
    """Remove the previous demo's database and snapshots (only those, and only in the demo folder)."""
    folder = Path(folder)
    for name in ("skynode.db", "skynode.db-journal", "skynode.db-wal", "skynode.db-shm"):
        (folder / name).unlink(missing_ok=True)
    shutil.rmtree(folder / "snapshots", ignore_errors=True)


def play(videos, detector, cfg, link, logger, dashboard, clock, realtime=True):
    """Run every video through the real brain loop, one after another."""
    for number, path in enumerate(videos, 1):
        print(f"Video {number}/{len(videos)}: {path.name}")
        clock.advance(CUT_SECONDS)      # a moment between clips, so one never runs into the next
        try:
            camera = VideoFile(path, realtime=realtime, demo_clock=clock)
        except OSError as error:
            print(f"WARN skipping this one: {error}")
            continue
        c = cfg.control
        tracker = Tracker(cfg.model.target_classes, cfg.tracker.max_missed_frames, cfg.tracker.max_jump)
        controller = PanTiltController(cfg.camera.hfov_deg, c.gain, c.deadband_deg, c.max_step_deg,
                                       c.pan_sign, c.tilt_sign)
        try:
            run_loop(camera, detector, tracker, controller, link, cfg, logger=logger,
                     dashboard=dashboard)
        finally:
            camera.release()
            if logger is not None:
                report(logger.close())  # a sighting still going on at the end of a clip is logged


def main(argv=None):
    args = parse_args(argv)
    refuse_unignored_repo_folder(args.folder)
    videos = find_videos(args.folder)

    cfg = load_config(args.config)
    if args.model:
        cfg.model.path = args.model
    if args.classes:
        cfg.model.target_classes = [name.strip() for name in args.classes.split(",") if name.strip()]
    if not Path(cfg.model.path).exists():
        raise SystemExit(f"Model not found: {cfg.model.path}\n"
                         "Give one with --model, for example --model models/skynode-v2.onnx")
    cfg.link.type = "none"                      # no Pico: the pan and tilt are simulated
    cfg.camera.source = str(videos[0])          # (the dashboard shows just the file name)
    cfg.display.show = args.show
    cfg.logger.enabled = True
    cfg.logger.folder = str(DEMO_LOGS)
    cfg.dashboard.enabled = True
    cfg.dashboard.node_name = "DEMO"
    cfg.dashboard.location = "TEST VIDEOS"
    if args.port is not None:
        cfg.dashboard.port = args.port

    detector = Detector(cfg.model.path, cfg.model.min_confidence, cfg.model.iou_threshold)
    check_target_classes(cfg.model.target_classes, detector.class_names)
    print(f"Model: {cfg.model.path} (tracking {', '.join(cfg.model.target_classes)})")
    print(f"DEMO: {len(videos)} video(s) from {Path(args.folder).expanduser()}. "
          "Not a live camera; pan/tilt are simulated.")

    if not args.keep_logs:
        start_afresh(DEMO_LOGS)
    link = NullLink()
    clock = VideoClock()
    logger = make_logger(cfg, clock=clock)
    dashboard = make_dashboard(cfg, logger, link, clock=clock)
    try:
        while True:
            play(videos, detector, cfg, link, logger, dashboard, clock, realtime=not args.fast)
            if not args.loop:
                break
        clock.run_free()                # the videos are over: time follows the real clock again
        total = logger.stats()["total"]
        print(f"Demo finished: {total} sighting(s) logged to {logger.folder}")
        if not args.exit_when_done:
            print("The dashboard stays open. Press Ctrl+C to quit.")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        report(logger.close())
        if dashboard is not None:
            dashboard.stop()
        if cfg.display.show:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
