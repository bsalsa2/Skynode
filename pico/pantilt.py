# pantilt.py — two servos (pan + tilt) working together as one camera mount.
#
# This is the layer between the text protocol and the servos:
#   - builds both servos from a settings dict
#   - runs parsed commands and produces the reply text
#   - loads/saves settings in config.json on the Pico's flash, so a
#     calibration survives power cycles

import json

from protocol import parse
from servo import Servo

CONFIG_PATH = "config.json"
SPEED_MAX = 600     # deg/s. An SG90 tops out around 0.1 s per 60 deg.

# Used until you calibrate and SAVE. Pan servo on GP0, tilt servo on GP1.
DEFAULTS = {
    "speed": 120,   # deg/s
    "pan":  {"pin": 0, "min_us": 500, "max_us": 2400, "min_deg": 0, "max_deg": 180, "home": 90},
    "tilt": {"pin": 1, "min_us": 500, "max_us": 2400, "min_deg": 0, "max_deg": 180, "home": 45},
}


class PanTilt:
    def __init__(self, config, config_path=CONFIG_PATH):
        self.config_path = config_path
        self.speed = check_speed(config["speed"])
        self.home = {}
        self.servos = {}
        for axis in ("pan", "tilt"):
            c = config[axis]
            self.home[axis] = c["home"]
            self.servos[axis] = Servo(c["pin"], c["min_us"], c["max_us"],
                                      c["min_deg"], c["max_deg"], start_deg=c["home"])

    def update(self, dt):
        """Advance both servos. Call every loop tick with seconds since the last tick."""
        for servo in self.servos.values():
            servo.update(dt, self.speed)

    def handle(self, line):
        """Run one line of text. Returns the reply to print, or None for no reply.

        Moves are silent on purpose: the brain can stream them many times a
        second without having to read an acknowledgement for each one.
        """
        try:
            parsed = parse(line)
            if parsed is None:
                return None
            name, args = parsed
            return self.run(name, args)
        except ValueError as err:
            return "ERR " + str(err)

    def run(self, name, args):
        if name == "move":
            for axis, deg in args.items():
                self.servos[axis].set_target(deg)
            return None
        if name == "home":
            for axis, servo in self.servos.items():
                servo.set_target(self.home[axis])
            return None
        if name == "status":
            pan = self.servos["pan"].angle
            tilt = self.servos["tilt"].angle
            return f"POS P{pan:.1f} T{tilt:.1f}"
        if name == "config":
            return "CFG " + json.dumps(self.settings())
        if name == "speed":
            self.speed = check_speed(args[0])
            return "OK"
        if name == "cal":
            axis, min_us, max_us = args
            self.servos[axis].calibrate(min_us, max_us)
            return "OK"
        if name == "lim":
            axis, min_deg, max_deg = args
            self.servos[axis].set_limits(min_deg, max_deg)
            return "OK"
        if name == "raw":
            axis, us = args
            self.servos[axis].raw_us(us)
            return "OK"
        if name == "off":
            for servo in self.servos.values():
                servo.relax()
            return "OK"
        if name == "save":
            save_config(self.settings(), self.config_path)
            return "OK saved"
        return "ERR unhandled " + name      # only if protocol.py gains a command we forgot

    def settings(self):
        """Current settings, in the same shape as DEFAULTS and config.json."""
        config = {"speed": self.speed}
        for axis, s in self.servos.items():
            config[axis] = {"pin": s.pin, "min_us": s.min_us, "max_us": s.max_us,
                            "min_deg": s.min_deg, "max_deg": s.max_deg,
                            "home": self.home[axis]}
        return config


def check_speed(speed):
    if not 1 <= speed <= SPEED_MAX:
        raise ValueError(f"speed must be 1-{SPEED_MAX} deg/s")
    return speed


def default_config():
    """A fresh copy of DEFAULTS (so changing it never changes DEFAULTS itself)."""
    return {"speed": DEFAULTS["speed"],
            "pan": dict(DEFAULTS["pan"]),
            "tilt": dict(DEFAULTS["tilt"])}


def load_config(path=CONFIG_PATH):
    """DEFAULTS, overridden by whatever was saved in config.json.

    A missing or unreadable file just means "use the defaults".
    """
    config = default_config()
    try:
        with open(path) as f:
            saved = json.load(f)
    except (OSError, ValueError):       # no file yet, or not valid JSON
        return config
    config["speed"] = saved.get("speed", config["speed"])
    for axis in ("pan", "tilt"):
        config[axis].update(saved.get(axis, {}))
    return config


def save_config(config, path=CONFIG_PATH):
    with open(path, "w") as f:
        json.dump(config, f)
