# main.py — Skynode Pico firmware. MicroPython runs this file at power-up.
#
# The loop, 50 times a second:
#   1. read whatever characters the brain has sent over USB serial (never waits)
#   2. each time a full line arrives, run it and print the reply, if any
#   3. step both servos toward their targets
#
# To stop it, press Stop (or Ctrl+C) in Thonny.

import select
import sys
import time

from pantilt import PanTilt, default_config, load_config

TICK_MS = 20        # 50 Hz, the same rate the servos get pulses, so faster gains nothing
MAX_LINE = 64       # longest line we keep; anything beyond is dropped

try:
    rig = PanTilt(load_config())
except Exception as err:            # e.g. a hand-edited config.json with bad values
    print("WARN bad config.json, using defaults:", err)
    rig = PanTilt(default_config())

# poll() answers "is input waiting?" without blocking, so servos keep moving
# smoothly even while no commands are arriving.
serial_in = select.poll()
serial_in.register(sys.stdin, select.POLLIN)

line = ""
last = time.ticks_ms()
print("READY skynode-pico")

while True:
    # 1 + 2: drain the input, one character at a time
    while serial_in.poll(0):
        char = sys.stdin.read(1)
        if char == "\n" or char == "\r":
            reply = rig.handle(line)
            if reply:
                print(reply)
            line = ""
        elif len(line) < MAX_LINE:
            line += char

    # 3: step the servos. ticks_diff() copes with the ms counter wrapping around.
    now = time.ticks_ms()
    rig.update(time.ticks_diff(now, last) / 1000)
    last = now
    time.sleep_ms(TICK_MS)
