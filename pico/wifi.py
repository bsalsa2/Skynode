# wifi.py — optional Wi-Fi link for the Pico W / WH.
#
# Joins your Wi-Fi network and listens on UDP port 5005 for the same text
# commands as USB serial. Replies go back to whoever sent the command.
#
# Why UDP rather than TCP: the brain streams "latest position wins" moves.
# If a packet is lost, the next one arrives a few ms later and replaces it,
# so TCP's resending (and the stalls it causes) would only get in the way.
#
# Wi-Fi is optional. Without wifi_secrets.py on the Pico, start_wifi()
# returns None and the firmware runs on USB serial alone.

import network
import socket
import time

PORT = 5005
HOSTNAME = "skynode"      # most networks also let you reach the Pico as skynode.local
MAX_PACKET = 256          # bytes per datagram, plenty for a few command lines
RETRY_MS = 15000          # while disconnected, try to rejoin this often


def start_wifi():
    """Start Wi-Fi with the details in wifi_secrets.py, or return None if that file is missing."""
    try:
        import wifi_secrets
    except ImportError:
        return None
    return WifiLink(wifi_secrets.SSID, wifi_secrets.PASSWORD,
                    getattr(wifi_secrets, "COUNTRY", None))


class WifiLink:
    def __init__(self, ssid, password, country=None):
        if country:
            import rp2
            rp2.country(country)            # use this country's legal Wi-Fi channels
        network.hostname(HOSTNAME)
        self.ssid = ssid
        self.password = password
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.wlan.config(pm=0xA11140)       # power saving off: it adds 100+ ms of lag
        self.wlan.connect(ssid, password)   # returns at once; joining happens in the background
        self.last_attempt = time.ticks_ms()
        self.connected = False

        # One UDP socket for the whole run. Binding to 0.0.0.0 ("any address")
        # works before we have an IP address, and keeps working after a reconnect.
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", PORT))
        self.sock.setblocking(False)

    def service(self):
        """Call every loop tick. Returns a status line to print when something changes."""
        is_up = self.wlan.isconnected()
        if is_up != self.connected:
            self.connected = is_up
            if is_up:
                return f"WIFI up {self.ip_address()} port {PORT}"
            return "WIFI down"

        if not is_up and time.ticks_diff(time.ticks_ms(), self.last_attempt) > RETRY_MS:
            self.last_attempt = time.ticks_ms()
            status = self.wlan.status()
            if status == network.STAT_CONNECTING:
                return None                 # still joining, give it more time
            self.wlan.connect(self.ssid, self.password)
            return f"WIFI retry (last status {status})"
        return None

    def ip_address(self):
        try:
            return self.wlan.ipconfig("addr4")[0]     # MicroPython 1.24 and newer
        except AttributeError:
            return self.wlan.ifconfig()[0]            # older firmware

    def receive(self):
        """Return (text, sender) for one waiting datagram, or None if nothing is waiting."""
        try:
            data, sender = self.sock.recvfrom(MAX_PACKET)
            return data.decode(), sender
        except (OSError, ValueError):       # OSError: nothing waiting; ValueError: not text
            return None

    def reply(self, text, sender):
        try:
            self.sock.sendto((text + "\n").encode(), sender)
        except OSError:
            pass                            # Wi-Fi dropped mid-reply; the brain will ask again
