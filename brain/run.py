"""Skynode brain: webcam -> YOLO (ONNX) -> tracker -> controller -> Pico.

Run from the repo root:
    python -m brain.run                        # settings from brain/config.toml
    python -m brain.run --link wifi            # override the link type
    python -m brain.run --source planes.mp4    # a video file instead of the webcam
    python -m brain.run --port 8081            # the dashboard on another port
    python -m brain.run --no-dashboard         # no web dashboard this time

While it runs, open the live dashboard in a browser: http://localhost:8080/
Every sighting is logged to logs/ (see [logger] in brain/config.toml).

Quit with q or Esc in the preview window, or Ctrl+C in the terminal.
"""
import argparse
import dataclasses
import time
from pathlib import Path

import cv2

from brain.config import load_config
from brain.controller import PanTiltController
from brain.dashboard import Dashboard
from brain.detector import Detector
from brain.link import NullLink, open_link, read_pico_state
from brain.logger import SightingLogger
from brain.overlay import draw_overlay
from brain.tracker import Tracker

DEFAULT_CONFIG = Path(__file__).with_name("config.toml")
REPO = Path(__file__).resolve().parent.parent


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Skynode brain: detect, track, point the camera.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="settings file (default: brain/config.toml)")
    parser.add_argument("--link", choices=["wifi", "usb", "none"], help="override [link] type")
    parser.add_argument("--source", help="webcam number or video file (overrides [camera] source)")
    parser.add_argument("--model", help="path to an .onnx model (overrides [model] path)")
    parser.add_argument("--headless", action="store_true", help="no preview window")
    parser.add_argument("--port", type=port_number,
                        help="dashboard port (overrides [dashboard] port, normally 8080)")
    parser.add_argument("--no-dashboard", action="store_true",
                        help="don't start the live web dashboard")
    return parser.parse_args(argv)


def port_number(text):
    """--port must be a whole number from 1 to 65535 (that's all the ports there are)."""
    try:
        port = int(text)
    except ValueError:
        port = 0
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"{text!r} isn't a port number (1-65535)")
    return port


def main(argv=None):
    args = parse_args(argv)
    cfg = load_config(args.config)
    if args.link:
        cfg.link.type = args.link
    if args.source is not None:
        cfg.camera.source = int(args.source) if args.source.isdigit() else args.source
    if args.model:
        cfg.model.path = args.model
    if args.headless:
        cfg.display.show = False
    if args.port is not None:
        cfg.dashboard.port = args.port
    if args.no_dashboard:
        cfg.dashboard.enabled = False

    if not Path(cfg.model.path).exists():
        raise SystemExit(f"Model not found: {cfg.model.path}\n"
                         "Export one first: see 'Get a model' in brain/README.md.")
    detector = Detector(cfg.model.path, cfg.model.min_confidence, cfg.model.iou_threshold)
    check_target_classes(cfg.model.target_classes, detector.class_names)
    print(f"Model: {cfg.model.path} (tracking {', '.join(cfg.model.target_classes)})")

    tracker = Tracker(cfg.model.target_classes, cfg.tracker.max_missed_frames, cfg.tracker.max_jump)
    c = cfg.control
    controller = PanTiltController(cfg.camera.hfov_deg, c.gain, c.deadband_deg, c.max_step_deg,
                                   c.pan_sign, c.tilt_sign)

    link = open_link(cfg.link.type, cfg.link.serial_port, cfg.link.wifi_host, cfg.link.wifi_port)
    print(f"Link: {link.description}")
    sync_with_pico(link, controller)

    logger = make_logger(cfg)
    camera = open_camera(cfg.camera)
    dashboard = make_dashboard(cfg, logger, link)
    try:
        run_loop(camera, detector, tracker, controller, link, cfg, logger=logger,
                 dashboard=dashboard)
    except KeyboardInterrupt:
        pass
    finally:
        camera.release()
        link.close()
        if logger is not None:
            report(logger.close())      # a sighting still going on gets logged too
        if dashboard is not None:
            dashboard.stop()
        if cfg.display.show:
            cv2.destroyAllWindows()     # (headless OpenCV has no windows, and errors here)


def run_loop(camera, detector, tracker, controller, link, cfg, logger=None, dashboard=None):
    last_seen = time.monotonic()        # when we last had a target
    last_command = None
    fps = 0.0
    previous = time.monotonic()

    while True:
        ok, frame = camera.read()
        if not ok:
            print("Camera gave no frame (end of the video, or camera unplugged). Stopping.")
            return
        height, width = frame.shape[:2]

        # 1. Sense
        detections = detector.detect(frame)

        # 2. Track
        was_locked = tracker.locked
        target = tracker.update(detections, width)
        if target is not None and not was_locked:
            print(f"LOCK {target.class_name} ({target.confidence:.2f})")
        elif was_locked and not tracker.locked:
            print("LOST target")

        # 3. Control
        now = time.monotonic()
        if target is not None:
            last_seen = now
            controller.update(target.center, (width, height))
        elif now - last_seen > cfg.control.home_after_s:
            controller.go_home()

        # 4. Actuate: only send when the angles actually changed
        command = controller.command()
        if command != last_command:
            link.send(command)
            last_command = command

        # Frames per second, smoothed so the number doesn't flicker
        fps = 0.9 * fps + 0.1 / max(now - previous, 1e-6)
        previous = now

        # 5. Log and share. This has to happen BEFORE the overlay draws on the
        #    frame, so snapshots and the live view show the sky, not our boxes.
        if logger is not None:
            report(logger.update(target, tracker.locked, frame, controller.pan, controller.tilt))
        if dashboard is not None:
            dashboard.publish(frame, detections, target, tracker.target_classes,
                              controller.pan, controller.tilt, fps, link.description)

        if cfg.display.show:
            draw_overlay(frame, detections, target, tracker.target_classes,
                         controller, fps, link.description)
            cv2.imshow("Skynode", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):   # 27 = Esc
                return


def report(logged):
    """Print one line for a sighting the logger just saved (nothing if it saved none)."""
    if logged is not None:
        print(f"LOGGED {logged.class_name} {logged.duration_s:.1f}s "
              f"peak {logged.confidence:.2f}")


def make_logger(cfg, **options):
    """The sighting logger, or None if [logger] enabled = false.

    `options` go straight to SightingLogger (the tests use them for a fake clock).
    """
    settings = cfg.logger
    if not settings.enabled:
        return None
    logger = SightingLogger(settings.folder, settings.drone_classes, settings.aircraft_classes,
                            settings.min_duration_s, settings.snapshots, settings.heartbeat_min,
                            **options)
    print(f"Logging sightings to {logger.folder}")
    return logger


def make_dashboard(cfg, logger, link, **options):
    """Start the live dashboard. Returns it, or None if it's turned off or couldn't start.

    A dashboard that can't start (most often: another program already uses
    the port) is NOT a reason to stop tracking, so this only warns.
    `options` go straight to Dashboard (the tests use them for a temp folder).
    """
    settings = cfg.dashboard
    if not settings.enabled:
        return None
    dashboard = Dashboard(logger, settings.host, settings.port, settings.node_name,
                          settings.location, settings.stream_fps, settings.stream_width,
                          info=dashboard_info(cfg, link), **options)
    try:
        url = dashboard.start()
    except (OSError, OverflowError) as error:     # port taken, or not a usable address
        print(f"WARN the dashboard can't start on {settings.host}:{settings.port}: {error}\n"
              "     If another program (or a second brain) has that port, try --port 8081.\n"
              "     Tracking carries on without the dashboard.")
        return None
    print(f"Dashboard: {url}")
    if settings.host not in ("127.0.0.1", "localhost", "::1"):
        print("     Other devices on your network can open it too, and there's no password.")
    return dashboard


def dashboard_info(cfg, link):
    """What the dashboard's Nodes and Settings tabs show about this brain."""
    source = cfg.camera.source
    camera = str(source) if isinstance(source, int) else Path(source).name
    config = dataclasses.asdict(cfg)
    # Short paths only: anyone who can open the page sees these, and a full
    # path like C:\Users\<your name>\... says more than it needs to.
    config["camera"]["source"] = source if isinstance(source, int) else camera
    config["model"]["path"] = shown_path(cfg.model.path)
    config["logger"]["folder"] = shown_path(cfg.logger.folder)
    return {"model": Path(cfg.model.path).name,
            "target_classes": list(cfg.model.target_classes),
            "camera": camera,
            "link": link.description,
            "config": config}


def shown_path(path):
    """A path as the dashboard shows it: from the repo folder if it's inside, else just the name."""
    path = Path(path).resolve()
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.name


def check_target_classes(wanted, available):
    if not available:
        print("WARN this model has no class names stored; its classes are called class0, class1, ...")
        return
    missing = [name for name in wanted if name not in available]
    if missing:
        raise SystemExit(f"Target class(es) {missing} aren't in this model.\n"
                         f"It knows: {', '.join(available)}")


def sync_with_pico(link, controller):
    """Start from the Pico's real limits, home and position, not from guesses."""
    settings, position = read_pico_state(link)
    if settings:
        controller.apply_pico_settings(settings)
    if position:
        controller.pan, controller.tilt = position
        print(f"Pico at pan {position[0]:.1f}, tilt {position[1]:.1f}")
    elif not isinstance(link, NullLink):
        print("WARN the Pico didn't answer. Is main.py running on it? Sending commands anyway.")


def open_camera(camera_cfg):
    capture = cv2.VideoCapture(camera_cfg.source)
    if not capture.isOpened():
        raise SystemExit(f"Can't open camera/video {camera_cfg.source!r}. Is another app "
                         "using the webcam? For a second camera, try source = 1.")
    if isinstance(camera_cfg.source, int):
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, camera_cfg.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_cfg.height)
    return capture


if __name__ == "__main__":
    main()
