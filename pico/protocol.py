# protocol.py — parse one line of the Skynode serial protocol.
#
# The brain talks to the Pico with short plain-text lines, one command per line:
#
#   P90 T45              move pan to 90 deg and tilt to 45 deg (either order, either alone)
#   HOME  (or H)         move both axes to their home angles
#   SPEED 120            max servo speed in deg/s
#   ?     (or STATUS)    report current angles
#   CFG                  report current settings as JSON
#   CAL P 500 2400       calibrate pan: pulse widths (us) for 0 and 180 deg
#   LIM T 0 90           limit tilt to 0..90 deg
#   RAW P 1500           send pan an exact pulse width (calibration only)
#   OFF                  stop pulses, servos go limp (next move wakes them)
#   SAVE                 store settings in config.json on the Pico
#
# Commands are case-insensitive. parse() only checks SYNTAX; whether a value
# is sensible (e.g. min < max) is checked by the servo code.
#
# This file has no hardware imports, so it runs unchanged on a laptop too.

import math

# Letter used on the wire -> axis name used in code.
AXES = {"P": "pan", "PAN": "pan", "T": "tilt", "TILT": "tilt"}

# Commands that take no arguments: word on the wire -> command name.
SIMPLE = {
    "?": "status", "STATUS": "status",
    "H": "home", "HOME": "home",
    "CFG": "config",
    "OFF": "off",
    "SAVE": "save",
}


def parse(line):
    """Turn one line of text into (name, args).

    Returns None for a blank line. Raises ValueError (with a short message
    meant to be sent back to the brain) if the line is malformed.
    """
    words = line.strip().upper().split()
    if not words:
        return None
    first = words[0]

    if first in SIMPLE:
        expect_count(words, 1, first)
        return (SIMPLE[first], ())

    if first == "SPEED":
        expect_count(words, 2, "SPEED <deg/s>")
        return ("speed", (number(words[1]),))

    if first in ("CAL", "LIM"):
        usage = "CAL <P|T> <min_us> <max_us>" if first == "CAL" else "LIM <P|T> <min_deg> <max_deg>"
        expect_count(words, 4, usage)
        return (first.lower(), (axis(words[1]), number(words[2]), number(words[3])))

    if first == "RAW":
        expect_count(words, 3, "RAW <P|T> <us>")
        return ("raw", (axis(words[1]), number(words[2])))

    # Anything else must be a move: one or more tokens like P90 or T45.5
    targets = {}
    for word in words:
        name = AXES.get(word[0])
        if name is None or len(word) < 2:
            raise ValueError("unknown command " + word)
        targets[name] = number(word[1:])
    return ("move", targets)


def expect_count(words, count, usage):
    if len(words) != count:
        raise ValueError("usage: " + usage)


def axis(word):
    if word not in AXES:
        raise ValueError("axis must be P or T, got " + word)
    return AXES[word]


def number(text):
    """Parse a finite number ('90', '45.5', '-3'). Rejects 'nan' and 'inf'."""
    try:
        value = float(text)
    except ValueError:
        raise ValueError("bad number " + text)
    if not math.isfinite(value):
        raise ValueError("bad number " + text)
    return value
