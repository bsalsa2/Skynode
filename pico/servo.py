# servo.py — driver for one hobby servo (SG90 or similar) on a Raspberry Pi Pico.
#
# How a hobby servo is controlled:
#   Every 20 ms (50 times a second) the Pico sends a short HIGH pulse.
#   The pulse WIDTH sets the angle: roughly 500 us = 0 deg, 2400 us = 180 deg.
#   Every servo is slightly different, so the two end widths (min_us, max_us)
#   are calibratable instead of hard-coded.
#
# Smooth motion:
#   We never jump straight to a new angle. set_target() only records where we
#   WANT to go; update() is called every loop tick and moves the servo a small
#   step toward the target, capped at `speed` degrees per second. This keeps
#   camera motion smooth and avoids big current spikes on the 5 V rail.

from machine import Pin, PWM

FRAME_HZ = 50                  # standard servo frame rate: one pulse every 20 ms
PULSE_MIN_US = 400             # hard safety bounds for any hobby servo pulse;
PULSE_MAX_US = 2600            # calibration values must fall inside these


class Servo:
    def __init__(self, pin, min_us=500, max_us=2400, min_deg=0, max_deg=180, start_deg=90):
        check_pulse_range(min_us, max_us)
        check_angle_range(min_deg, max_deg)
        self.pin = pin
        self.min_us = min_us          # pulse width that points the horn at 0 deg
        self.max_us = max_us          # pulse width that points the horn at 180 deg
        self.min_deg = min_deg        # software angle limits (protect the bracket/cables)
        self.max_deg = max_deg
        self.angle = self.clamp(start_deg)   # where we are right now
        self.target = self.angle             # where we are heading
        self.active = True                   # False = no pulses, servo goes limp

        self.pwm = PWM(Pin(pin))
        self.pwm.freq(FRAME_HZ)
        self.write_us(self.angle_to_us(self.angle))

    # ---- conversions -------------------------------------------------------

    def clamp(self, deg):
        """Force an angle inside this servo's limits."""
        return min(max(deg, self.min_deg), self.max_deg)

    def angle_to_us(self, deg):
        """Map 0..180 deg linearly onto min_us..max_us."""
        return self.min_us + (self.max_us - self.min_us) * deg / 180

    # ---- commands ----------------------------------------------------------

    def set_target(self, deg):
        """Ask the servo to move to `deg`. Out-of-range values are clamped, not rejected."""
        self.target = self.clamp(deg)
        if not self.active:
            # Wake up from relax(): start pulsing again at the last known angle.
            self.active = True
            self.write_us(self.angle_to_us(self.angle))

    def calibrate(self, min_us, max_us):
        """Set the pulse widths for 0 and 180 deg, and apply them right away."""
        check_pulse_range(min_us, max_us)
        self.min_us = min_us
        self.max_us = max_us
        if self.active:
            self.write_us(self.angle_to_us(self.angle))

    def set_limits(self, min_deg, max_deg):
        """Set the allowed angle range. If the servo is outside it, update() will ease it back in."""
        check_angle_range(min_deg, max_deg)
        self.min_deg = min_deg
        self.max_deg = max_deg
        self.target = self.clamp(self.target)

    def relax(self):
        """Stop sending pulses. The servo stops holding and can be turned by hand."""
        self.pwm.duty_ns(0)
        self.active = False

    def write_us(self, us):
        """Send a raw pulse width in microseconds (the hardware takes nanoseconds)."""
        self.pwm.duty_ns(int(us * 1000))

    def raw_us(self, us):
        """Calibration helper: send an exact pulse width, bypassing angles and limits."""
        if not PULSE_MIN_US <= us <= PULSE_MAX_US:
            raise ValueError(f"pulse must be {PULSE_MIN_US}-{PULSE_MAX_US} us")
        self.active = True
        self.write_us(us)

    # ---- motion ------------------------------------------------------------

    def update(self, dt, speed):
        """Step toward the target. Call every loop tick.

        dt    -- seconds since the last call
        speed -- maximum speed in degrees per second
        """
        if not self.active or self.angle == self.target:
            return
        max_step = speed * dt
        error = self.target - self.angle
        if abs(error) <= max_step:
            self.angle = self.target          # close enough: land exactly on target
        elif error > 0:
            self.angle += max_step
        else:
            self.angle -= max_step
        self.write_us(self.angle_to_us(self.angle))


def check_pulse_range(min_us, max_us):
    if not PULSE_MIN_US <= min_us < max_us <= PULSE_MAX_US:
        raise ValueError(f"need {PULSE_MIN_US} <= min_us < max_us <= {PULSE_MAX_US}")


def check_angle_range(min_deg, max_deg):
    if not 0 <= min_deg < max_deg <= 180:
        raise ValueError("need 0 <= min_deg < max_deg <= 180")
