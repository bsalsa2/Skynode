# wifi_secrets_example.py — copy to the Pico as wifi_secrets.py, then fill it in.
#
# wifi_secrets.py is gitignored, so your password never ends up on GitHub.
# If there's no wifi_secrets.py on the Pico, the firmware uses USB serial only.

SSID = "your-network-name"      # must be 2.4 GHz: the Pico W has no 5 GHz radio
PASSWORD = "your-password"

# Optional two-letter country code, e.g. "US", "GB", "DE", so the radio uses the
# Wi-Fi channels that are legal where you are. None = worldwide-safe default
# (channels 1-11; set this if your router uses channel 12 or 13).
COUNTRY = None
