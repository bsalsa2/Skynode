# main.py — Skynode Pico firmware. MicroPython runs this file at power-up.
#
# The loop, 50 times a second:
#   1. USB serial: read whatever characters have arrived (never waits);
#      each time a full line is in, run it and print the reply, if any
#   2. Wi-Fi (if set up): run every waiting UDP packet, reply to its sender
#   3. step both servos toward their targets
#
# To stop it, press Stop (or Ctrl+C) in Thonny.

import select
import sys
import time

from pantilt import PanTilt, default_config, load_config

TICK_MS = 20        # 50 Hz, the same rate the servos get pulses, so faster gains nothing
MAX_LINE = 64       # longest USB line we keep; anything beyond is dropped

try:
    rig = PanTilt(load_config())
except Exception as err:            # e.g. a hand-edited config.json with bad values
    print("WARN bad config.json, using defaults:", err)
    rig = PanTilt(default_config())

# Wi-Fi is optional, and whatever goes wrong with it, USB must keep working.
wifi = None
try:
    from wifi import start_wifi
    wifi = start_wifi()             # None if there's no wifi_secrets.py on the Pico
except Exception as err:
    print("WARN Wi-Fi off:", err)

# poll() answers "is input waiting?" without blocking, so servos keep moving
# smoothly even while no commands are arriving.
usb = select.poll()
usb.register(sys.stdin, select.POLLIN)

line = ""
last = time.ticks_ms()
print("READY skynode-pico")

while True:
    # 1: USB serial, one character at a time
    while usb.poll(0):
        char = sys.stdin.read(1)
        if char == "\n" or char == "\r":
            reply = rig.handle(line)
            if reply:
                print(reply)
            line = ""
        elif len(line) < MAX_LINE:
            line += char

    # 2: Wi-Fi, one datagram at a time (each can hold several lines)
    if wifi:
        packet = wifi.receive()
        while packet:
            text, sender = packet
            for wifi_line in text.split("\n"):
                reply = rig.handle(wifi_line)
                if reply:
                    wifi.reply(reply, sender)
            packet = wifi.receive()
        news = wifi.service()
        if news:
            print(news)

    # 3: step the servos. ticks_diff() copes with the ms counter wrapping around.
    now = time.ticks_ms()
    rig.update(time.ticks_diff(now, last) / 1000)
    last = now
    time.sleep_ms(TICK_MS)
