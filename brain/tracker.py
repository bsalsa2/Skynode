"""Pick ONE target out of each frame's detections, and stay locked onto it.

- Only detections whose class is in `target_classes` count.
- Not locked yet: take the most confident candidate.
- Locked: take the candidate nearest to where the target was last seen, so
  the camera doesn't hop to a different plane that happens to score higher.
- If the target isn't seen for more than `max_missed_frames` frames in a row
  (it flew behind a tree, or the detector blinked), drop the lock.

Works with anything that has .class_name, .confidence and .center, so it
doesn't depend on which detector produced the detections.
"""
import math


class Tracker:
    def __init__(self, target_classes, max_missed_frames=15, max_jump=0.25):
        self.target_classes = set(target_classes)
        self.max_missed_frames = max_missed_frames
        self.max_jump = max_jump     # max move between frames, as a fraction of frame width
        self.target = None           # last sighting of the locked target (None = not locked)
        self.missed = 0              # frames in a row without seeing it

    @property
    def locked(self):
        return self.target is not None

    def update(self, detections, frame_width):
        """Feed one frame's detections. Returns this frame's target, or None."""
        candidates = [d for d in detections if d.class_name in self.target_classes]

        if self.target is None:
            choice = max(candidates, key=lambda d: d.confidence, default=None)
        else:
            choice = min(candidates, key=lambda d: distance(d, self.target), default=None)
            if choice is not None and distance(choice, self.target) > self.max_jump * frame_width:
                choice = None        # too far away to be the same object

        if choice is not None:
            self.target = choice
            self.missed = 0
            return choice

        if self.target is not None:
            self.missed += 1
            if self.missed > self.max_missed_frames:
                self.target = None   # lost it; the next frame starts fresh
        return None


def distance(a, b):
    """Pixel distance between the centers of two detections."""
    (ax, ay), (bx, by) = a.center, b.center
    return math.hypot(ax - bx, ay - by)
