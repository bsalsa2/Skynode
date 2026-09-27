"""Stand-ins for MicroPython's `machine` module, so pico/ code runs on a laptop.

Importing this module (do it before importing any pico/ code):
  1. registers a fake `machine` module with Pin and PWM in sys.modules
  2. puts pico/ on sys.path, so tests can `import servo`, `import protocol`, ...

The fake PWM just remembers the last frequency and duty it was given, so
tests can check exactly what pulse the real hardware would have sent.
"""
import os
import sys
import types


class Pin:
    def __init__(self, id, mode=None):
        self.id = id


class PWM:
    def __init__(self, pin):
        self.pin = pin
        self.frequency = None
        self.duty = None        # last value passed to duty_ns(), in nanoseconds

    def freq(self, hz):
        self.frequency = hz

    def duty_ns(self, ns):
        self.duty = ns


machine = types.ModuleType("machine")
machine.Pin = Pin
machine.PWM = PWM
sys.modules["machine"] = machine

PICO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pico")
if PICO_DIR not in sys.path:
    sys.path.insert(0, PICO_DIR)
