"""Draw detections, the locked target, and a status bar onto a frame for the preview window."""
import cv2

# OpenCV colors are (blue, green, red)
GRAY = (160, 160, 160)       # detections we don't track
YELLOW = (0, 215, 255)       # target-class detections we're not locked onto
GREEN = (0, 220, 0)          # the locked target
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
FONT = cv2.FONT_HERSHEY_SIMPLEX


def draw_overlay(frame, detections, target, target_classes, controller, fps, link_text):
    height, width = frame.shape[:2]
    center = (width // 2, height // 2)
    cv2.drawMarker(frame, center, GRAY, cv2.MARKER_CROSS, 24, 1)

    for d in detections:
        if d is target:
            color, thickness = GREEN, 3
        elif d.class_name in target_classes:
            color, thickness = YELLOW, 1
        else:
            color, thickness = GRAY, 1
        x1, y1, x2, y2 = (int(v) for v in d.box)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
        text_outlined(frame, f"{d.class_name} {d.confidence:.2f}", (x1, max(y1 - 6, 14)), color)

    if target is not None:
        cv2.line(frame, center, tuple(int(v) for v in target.center), GREEN, 1)

    state = "LOCKED" if target is not None else "searching"
    status = (f"{fps:4.1f} fps | pan {controller.pan:5.1f}  tilt {controller.tilt:5.1f} | "
              f"{state} | link: {link_text}")
    text_outlined(frame, status, (10, height - 12), WHITE)


def text_outlined(frame, text, origin, color):
    """Text with a black outline, readable on bright sky and dark ground alike."""
    cv2.putText(frame, text, origin, FONT, 0.5, BLACK, 3, cv2.LINE_AA)
    cv2.putText(frame, text, origin, FONT, 0.5, color, 1, cv2.LINE_AA)
