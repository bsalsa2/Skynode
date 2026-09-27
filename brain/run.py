"""Skynode brain: webcam -> YOLO (ONNX) -> tracker -> controller -> Pico.

Run from the repo root:
    python -m brain.run                        # settings from brain/config.toml
    python -m brain.run --link wifi            # override the link type
    python -m brain.run --source planes.mp4    # a video file instead of the webcam

Quit with q or Esc in the preview window, or Ctrl+C in the terminal.
"""
import argparse
import time
from pathlib import Path

import cv2

from brain.config import load_config
from brain.controller import PanTiltController
from brain.detector import Detector
from brain.link import NullLink, open_link, read_pico_state
from brain.overlay import draw_overlay
from brain.tracker import Tracker

DEFAULT_CONFIG = Path(__file__).with_name("config.toml")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Skynode brain: detect, track, point the camera.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="settings file (default: brain/config.toml)")
    parser.add_argument("--link", choices=["wifi", "usb", "none"], help="override [link] type")
    parser.add_argument("--source", help="webcam number or video file (overrides [camera] source)")
    parser.add_argument("--model", help="path to an .onnx model (overrides [model] path)")
    parser.add_argument("--headless", action="store_true", help="no preview window")
    return parser.parse_args(argv)


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

    camera = open_camera(cfg.camera)
    try:
        run_loop(camera, detector, tracker, controller, link, cfg)
    except KeyboardInterrupt:
        pass
    finally:
        camera.release()
        link.close()
        cv2.destroyAllWindows()


def run_loop(camera, detector, tracker, controller, link, cfg):
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

        if cfg.display.show:
            draw_overlay(frame, detections, target, tracker.target_classes,
                         controller, fps, link.description)
            cv2.imshow("Skynode", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):   # 27 = Esc
                return


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
