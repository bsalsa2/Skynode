"""Turn "where the target is in the picture" into pan/tilt servo angles.

Proportional control: every frame, measure how many degrees the target is
off-center, then move `gain` of that distance.

Why not jump the whole way (gain = 1)? The image always lags behind the
servos: exposure, inference and servo travel all take time. A full jump
overshoots and the view swings back and forth. A gain of 0.3-0.5 homes in
smoothly.

Why no I or D terms, as in PID? The servo holds whatever angle it was last
sent, so adding a correction every frame already accumulates like the "I"
term would. Plain P is enough to follow an aircraft without drifting behind.
"""
import math


class PanTiltController:
    def __init__(self, hfov_deg=70.0, gain=0.35, deadband_deg=0.5, max_step_deg=8.0,
                 pan_sign=-1, tilt_sign=1, home=(90.0, 45.0)):
        self.hfov_deg = hfov_deg            # camera's horizontal field of view
        self.gain = gain
        self.deadband_deg = deadband_deg    # errors smaller than this are ignored (no jitter)
        self.max_step_deg = max_step_deg    # biggest correction in one frame
        self.pan_sign = pan_sign            # +1 or -1, depends on how the servos are mounted
        self.tilt_sign = tilt_sign
        self.pan_limits = (0.0, 180.0)      # replaced by the Pico's LIM values if it reports them
        self.tilt_limits = (0.0, 180.0)
        self.home = home
        self.pan, self.tilt = home          # the angles we've told the Pico to go to

    def offset_deg(self, point, frame_size):
        """How far `point` is from the image center, in degrees: (right +, up +)."""
        x, y = point
        width, height = frame_size
        # Pinhole camera model: the lens's focal length measured in pixels.
        # Pixels are square, so the same number works vertically.
        focal = (width / 2) / math.tan(math.radians(self.hfov_deg) / 2)
        right = math.degrees(math.atan((x - width / 2) / focal))
        up = math.degrees(math.atan((height / 2 - y) / focal))
        return right, up

    def update(self, point, frame_size):
        """Nudge the angles toward a target at `point` (pixels). Returns (pan, tilt)."""
        right, up = self.offset_deg(point, frame_size)
        self.pan = clamp(self.pan + self.pan_sign * self.correction(right), *self.pan_limits)
        self.tilt = clamp(self.tilt + self.tilt_sign * self.correction(up), *self.tilt_limits)
        return self.pan, self.tilt

    def correction(self, error_deg):
        if abs(error_deg) < self.deadband_deg:
            return 0.0
        return clamp(self.gain * error_deg, -self.max_step_deg, self.max_step_deg)

    def go_home(self):
        self.pan, self.tilt = self.home
        return self.pan, self.tilt

    def apply_pico_settings(self, settings):
        """Use the Pico's own angle limits and home, from its CFG reply (a dict).

        Without this, the brain could ask for 150 deg while the Pico is limited
        to 100. The brain's number would drift away from reality, and coming
        back would take many frames of "unwinding".
        """
        pan, tilt = settings["pan"], settings["tilt"]
        self.pan_limits = (pan["min_deg"], pan["max_deg"])
        self.tilt_limits = (tilt["min_deg"], tilt["max_deg"])
        self.home = (pan["home"], tilt["home"])
        self.pan = clamp(self.pan, *self.pan_limits)
        self.tilt = clamp(self.tilt, *self.tilt_limits)

    def command(self):
        """The current angles as a Pico protocol line, e.g. 'P92.5 T47.0'."""
        return f"P{self.pan:.1f} T{self.tilt:.1f}"


def clamp(value, low, high):
    return min(max(value, low), high)
