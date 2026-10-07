"""The live dashboard: a small web server inside the brain, for your browser.

Open http://localhost:8080/ while the brain runs and you see what the camera
sees, the box around whatever it is tracking, and the sighting log. It is all
served from this computer: no internet, no cloud, no account.

What the browser can ask for (GET only: this server never changes anything):

    /                     the page itself (brain/dashboard/index.html)
    /assets/<file>        its CSS, JavaScript, fonts and icons (from brain/dashboard/)
    /api/state            what the camera sees right now, plus node status
    /api/stats            sighting counts per hour, from the logger
    /api/sightings        the sighting log, newest first, one page at a time
    /api/sightings.csv    the same log as a spreadsheet file (e.g. to compare with ADS-B)
    /api/config           the brain's settings, read-only
    /snapshots/<id>.jpg   the photo saved with a sighting
    /snapshot.jpg         one still picture from the live camera
    /stream.mjpg          the live camera as "MJPEG": an endless series of JPEG
                          pictures. Browsers show it in a plain <img>, no video player.

How it fits into the brain:
- The main loop calls publish() once per frame. publish() has to be quick, so
  it only copies a few numbers and, now and then, a shrunk COPY of the frame.
- The web server answers each request on its own thread, so a slow browser
  can never slow down tracking. Turning pictures into JPEGs happens on those
  threads too, never in the main loop.
- Data shared between the threads sits behind one lock. A Condition (a lock
  that threads can wait on) wakes the stream threads when a new picture
  arrives, so they sleep in between instead of checking over and over.

Safety: by default only this computer can open the page (host 127.0.0.1).
With host = "0.0.0.0" anyone on your Wi-Fi can, and there is no password.
Files only ever come from brain/dashboard/ and the snapshots folder: names
with "..", hidden files and odd characters are refused. And the page must be
opened by an address like localhost, 192.168.1.20 or raspberrypi.local, not
by a web site's name: see host_allowed() for the trick that this blocks.
Other web sites can't put the camera or the snapshots on their pages either:
see fetch_allowed().

OpenCV is only imported to make pictures, so without it everything except the
live picture still works (and the tests run without it).
"""
import csv
import io
import ipaddress
import json
import math
import numbers
import os
import re
import select
import socket
import socketserver
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qsl, unquote

MAX_VIEWERS = 4                 # live streams at once (each costs JPEG work on this computer)
MAX_DETECTIONS = 20             # detections per frame sent to the page
ONLINE_WITHIN_S = 3.0           # "online" = a frame arrived at least this recently
GAP_S = 1.0                     # a pause between frames longer than this = "wasn't watching"
STILL_EVERY_S = 1.0             # with no stream viewers, keep a fresh still about this often
STREAM_WAIT_S = 2.0             # stream threads wake at least this often to check for shutdown
STREAM_QUALITY = 75             # JPEG quality of the live picture (snapshots use 85)
MAX_STATS_HOURS = 168           # /api/stats looks back at most a week
MAX_SIGHTINGS_HOURS = 87600     # /api/sightings: 10 years, just to keep the numbers sane
MAX_LIMIT = 200                 # sightings per page
CSV_LIMIT = 10000               # rows in one CSV export
MAX_QUERY_FIELDS = 20           # "?a=1&b=2..." pairs accepted in one request

CATEGORIES = ("drone", "aircraft", "other", "clear")
KINDS = ("sighting", "check")
DRONE_CLASSES = ("drone",)                                  # used when there's no logger
AIRCRAFT_CLASSES = ("airplane", "aircraft", "helicopter")

# The only file types /assets/ serves. Anything else is a 404.
ASSET_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".woff2": "font/woff2",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".txt": "text/plain; charset=utf-8",
}
# One folder or file name in an asset path: plain characters, and no dot at the
# start (so no "..", no "." and no hidden files like ".env").
ASSET_PART = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*")
SNAPSHOT_NAME = re.compile(r"[0-9A-Za-z_-]+\.jpg")
SIGHTING_ID = re.compile(r"[0-9A-Za-z_-]{1,64}")
WHOLE_NUMBER = re.compile(r"[+-]?[0-9]{1,9}")
HOST_NAME = re.compile(r"[a-z0-9_-]+(\.[a-z0-9_-]+)*")
# Name endings that only exist inside a home network: nobody can buy them, so
# no web site out on the internet can be called this. (See host_allowed.)
HOME_NETWORK_ENDINGS = (".local", ".localhost", ".lan", ".home", ".internal",
                        ".home.arpa", ".localdomain")

CSV_COLUMNS = ("id", "kind", "category", "class_name", "start_iso", "end_iso", "duration_s",
               "confidence", "pan", "tilt", "frames", "snapshot")

# What a browser closing the tab (or a stuck connection timing out) looks like
HANG_UPS = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError)


class Dashboard:
    """The brain's web server. start() it, publish() every frame, stop() at the end.

        dashboard = Dashboard(logger, port=8080, info={...})
        print("Dashboard:", dashboard.start())
        every frame:  dashboard.publish(frame, detections, target, ...)
        at the end:   dashboard.stop()
    """

    def __init__(self, logger, host="127.0.0.1", port=8080, node_name="NODE-01",
                 location="", stream_fps=12.0, stream_width=960, info=None,
                 static_dir=None, clock=time.time, encode_jpeg=None, shrink=None):
        self.logger = logger                # a SightingLogger, or None (the log then looks empty)
        self.host = host
        self.port = port                    # 0 = any free port; start() fills in the real one
        self.node_name = str(node_name)
        self.location = str(location)
        # Seconds between live-stream pictures (stream_fps is capped below at 0.1 per second)
        self.stream_interval = 1.0 / max(finite(stream_fps, 12.0), 0.1)
        self.stream_width = max(16, int(stream_width))
        self.info = dict(info or {})        # model, camera, link, config: Nodes/Settings tabs
        self.static_dir = Path(static_dir) if static_dir else Path(__file__).with_name("dashboard")
        self.clock = clock
        self.encode_jpeg = encode_jpeg if encode_jpeg is not None else default_encode_jpeg
        self.shrink = shrink if shrink is not None else default_shrink
        self.stream_wait_s = STREAM_WAIT_S
        self.poll_interval = 0.2            # how fast the server loop notices stop()
        self.started_at = clock()
        self.url = None                     # set by start()
        self.picture_problem = None         # why there's no live picture (e.g. no OpenCV), or None

        self._lock = threading.Lock()       # guards everything below
        self._new_picture = threading.Condition(self._lock)    # notified when _image changes
        self._live = None                   # the latest live state (a dict) for /api/state
        self._last_publish = None           # clock time of the latest publish()
        self._gaps = 0.0                    # total of the pauses between frames longer than GAP_S
        self._image = None                  # latest shrunk frame: our own copy, never the caller's
        self._image_seq = 0                 # goes up by one with every new _image
        self._next_image_at = None          # when the next _image is due (main loop only)
        self._jpeg_seq, self._jpeg = 0, None    # _image as JPEG, made once, shared by all viewers
        # Only one thread turns a picture into a JPEG at a time; the others wait
        # for it and share its result. A lock of its own, so publish() (which
        # takes _lock) never has to wait for an encoder.
        self._encode_lock = threading.Lock()
        self._viewers = set()               # connections currently watching /stream.mjpg
        self._stopping = threading.Event()
        self._warned = set()
        self._server = None
        self._thread = None

    # ---- Starting and stopping -----------------------------------------------------

    def start(self):
        """Open the port and serve in the background. Returns the address to open.

        Raises OSError if the port can't be used (for example, another program has it).
        """
        if self._server is not None:
            return self.url
        self._stopping.clear()
        server = _Server((self.host, self.port), _Handler)
        server.dashboard = self
        self._server = server
        self.port = server.server_address[1]
        self._thread = threading.Thread(target=server.serve_forever, args=(self.poll_interval,),
                                        name="dashboard", daemon=True)
        self._thread.start()
        everywhere = ("127.0.0.1", "0.0.0.0", "", "localhost")
        shown = "localhost" if self.host in everywhere else self.host
        self.url = f"http://{shown}:{self.port}/"
        return self.url

    def stop(self):
        """Stop serving and free the port. Open live streams get hung up. Safe to call twice."""
        server, self._server = self._server, None
        if server is None:
            return
        with self._new_picture:
            self._stopping.set()
            self._new_picture.notify_all()      # wake the stream threads so they can leave
            viewers = list(self._viewers)
        server.shutdown()                       # the serve_forever() loop ends
        server.server_close()                   # the port is free again
        # A stream thread could be stuck sending to a browser that stopped
        # reading. Cutting its connection makes that send fail right away.
        for connection in viewers:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self._thread.join(timeout=2)
        with self._new_picture:
            self._new_picture.wait_for(lambda: not self._viewers, timeout=2)

    @property
    def stopping(self):
        return self._stopping.is_set()

    @property
    def viewers(self):
        """How many browsers are watching the live stream right now."""
        with self._lock:
            return len(self._viewers)

    # ---- Main loop side ------------------------------------------------------------

    def publish(self, frame, detections, target, target_classes, pan, tilt, fps, link_text):
        """Share this frame with the web page. Call once per frame, BEFORE drawing on `frame`.

        Quick on purpose: a few numbers, plus now and then a shrunk COPY of the
        frame for the live picture. Never raises: the dashboard must never stop
        the tracking.
        """
        try:
            now = self.clock()
            live = self._live_state(frame, detections, target, target_classes,
                                    pan, tilt, fps, link_text, now)
            with self._lock:
                if self._last_publish is not None and now - self._last_publish > GAP_S:
                    self._gaps += now - self._last_publish     # the node wasn't watching then
                self._last_publish = now
                self._live = live
                watched = bool(self._viewers)
            if frame is not None and self._picture_due(now, watched):
                self._store_picture(frame)
        except Exception as error:
            self.warn_once("publish", f"WARN the dashboard skipped a frame: {error!r}")

    def categorize(self, class_name):
        """A model class's category: drone, aircraft or other. The logger decides, if there's one."""
        if self.logger is not None:
            return self.logger.categorize(class_name)
        name = str(class_name).lower()
        if name in DRONE_CLASSES:
            return "drone"
        if name in AIRCRAFT_CLASSES:
            return "aircraft"
        return "other"

    def _live_state(self, frame, detections, target, target_classes, pan, tilt, fps,
                    link_text, now):
        """What the camera sees right now, as JSON-ready data. Boxes are 0..1 of the frame."""
        width, height = frame_size(frame)
        tracked = {str(name) for name in (target_classes or ())}
        detections = list(detections or ())
        if len(detections) > MAX_DETECTIONS:
            # Keep the locked target, then the most confident of the rest
            detections.sort(key=lambda d: (d is target, finite(d.confidence)), reverse=True)
            detections = detections[:MAX_DETECTIONS]

        items = []
        for d in detections:
            item = self._describe(d, width, height)
            item["tracked_class"] = item["class_name"] in tracked
            item["is_target"] = d is target
            items.append(item)

        return {
            "fps": round(finite(fps), 1),
            "pan": round(finite(pan), 1),
            "tilt": round(finite(tilt), 1),
            "link": str(link_text or ""),
            "locked": target is not None,
            "target": None if target is None else self._describe(target, width, height),
            "detections": items,
            "frame_size": [width, height],
            "frame_time": round(now, 3),
        }

    def _describe(self, detection, width, height):
        name = str(detection.class_name)
        return {"class_name": name, "category": self.categorize(name),
                "confidence": round(finite(detection.confidence), 2),
                "box": normalised_box(detection.box, width, height)}

    def _picture_due(self, now, watched):
        """Time for a new live picture? stream_fps while someone watches, else about 1 a second.

        Pictures follow a timetable: each one is due `every` seconds after the
        previous one was DUE, not after it was made. Frames only come when the
        camera sends them, so most pictures are made a little late. Counting
        from "made" would add that lateness every time: a 20 fps camera with
        stream_fps = 12 would only give 10 pictures a second (every other frame).
        """
        every = self.stream_interval if watched else max(self.stream_interval, STILL_EVERY_S)
        due = self._next_image_at
        if due is not None and now < due <= now + every:
            return False                    # not yet
        # Start the timetable again from now if this is the first picture, if we
        # fell more than one picture behind (the camera paused: no burst of
        # pictures to catch up), or if the next one is due further off than it
        # could be (the clock jumped back, or a viewer just arrived and the slow
        # once-a-second timetable gives way to stream_fps).
        if due is None or abs(now - due) > every:
            due = now
        self._next_image_at = due + every
        return True

    def _store_picture(self, frame):
        """Keep a shrunk copy of the frame and wake the stream threads (they make the JPEG)."""
        try:
            image = self.shrink(frame, self.stream_width)
            if image is frame:
                image = frame.copy()    # must be our own: the main loop draws on `frame` next
        except Exception as error:      # e.g. no OpenCV: everything else keeps working
            self.picture_problem = f"Can't make the live picture: {error}"
            self.warn_once("shrink", f"WARN {self.picture_problem}")
            return
        with self._new_picture:
            self._image = image
            self._image_seq += 1
            self._new_picture.notify_all()

    # ---- Web server side (any thread) ----------------------------------------------

    def state(self):
        """Everything /api/state answers."""
        now = self.clock()
        with self._lock:
            live, last = self._live, self._last_publish
        return {"now": round(now, 3),
                "online": last is not None and now - last <= ONLINE_WITHIN_S,
                "node": self.node_info(now),
                "live": live,
                "current": self.logger.current() if self.logger is not None else None}

    def node_info(self, now):
        """Name, uptime, how much of that time the camera was watching, model, camera, link."""
        with self._lock:
            live, last, gaps = self._live, self._last_publish, self._gaps
        uptime = max(now - self.started_at, 0.0)
        if last is not None and now - last > GAP_S:
            gaps += now - last      # a pause still going on (e.g. a stuck camera) counts too
        if last is None or uptime <= 0:
            watch_ratio = 1.0
        else:
            watch_ratio = min(max(1.0 - gaps / uptime, 0.0), 1.0)
        info = self.info
        return {"name": self.node_name, "location": self.location,
                "started_at": round(self.started_at, 3), "uptime_s": round(uptime, 1),
                "watch_ratio": round(watch_ratio, 4),
                "model": str(info.get("model", "")),
                "target_classes": info.get("target_classes", []),
                "camera": str(info.get("camera", "")),
                "link": str(info.get("link") or (live or {}).get("link", ""))}

    def stats(self, hours):
        if self.logger is None:
            return empty_stats(self.clock(), hours)
        return self.logger.stats(hours=hours)

    def recent(self, limit, before=None, category=None, kind=None, since=None):
        """(records, more) from the logger, newest first. No logger: an empty log."""
        if self.logger is None:
            return [], False
        items, more = self.logger.recent(limit=limit, before=before, category=category,
                                         kind=kind, since=since)
        return list(items), bool(more)

    def snapshot_file(self, name):
        """Path of a sighting's photo, or None. Only plain names like 20261007-140217-001.jpg."""
        if self.logger is None or name is None or not SNAPSHOT_NAME.fullmatch(name):
            return None
        return self.logger.snapshot_path(name)

    def asset(self, rest):
        """(path, content type) of the file /assets/<rest> names, or None if it isn't allowed.

        `rest` comes straight from the address bar, so it is checked before it
        touches the disk: decoded once ("%2e" -> "."), then every part must be a
        plain name (no "..", no hidden files, no "\\" or ":" tricks), the file
        type must be on the list, and the real location (after following any
        shortcuts/symlinks) must still be inside the dashboard folder.
        """
        name = decode_path(rest)
        if name is None:
            return None
        parts = name.split("/")
        if not all(ASSET_PART.fullmatch(part) for part in parts):
            return None
        content_type = ASSET_TYPES.get(PurePosixPath(parts[-1]).suffix)
        if content_type is None:
            return None
        root = self.static_dir.resolve()
        path = root.joinpath(*parts).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            return None
        return path, content_type

    def add_viewer(self, connection):
        """Count a new stream viewer. False if there are MAX_VIEWERS already (or we're stopping)."""
        with self._lock:
            if self._stopping.is_set() or len(self._viewers) >= MAX_VIEWERS:
                return False
            self._viewers.add(connection)
            return True

    def remove_viewer(self, connection):
        with self._new_picture:
            self._viewers.discard(connection)
            self._new_picture.notify_all()      # stop() may be waiting for the last one to leave

    def latest_picture(self):
        """(number, image) of the newest live picture; image is None before the first one."""
        with self._lock:
            return self._image_seq, self._image

    def wait_for_picture(self, after):
        """Sleep until there's a picture newer than number `after`, a shutdown, or a timeout.

        Returns (number, image), with image None if nothing new came.
        """
        with self._new_picture:
            self._new_picture.wait_for(
                lambda: self._image_seq != after or self._stopping.is_set(), self.stream_wait_s)
            if self._image_seq == after:
                return after, None
            return self._image_seq, self._image

    def jpeg(self, seq, image):
        """JPEG bytes of picture number `seq`, or None if it can't be encoded.

        Encoded once and shared, so four viewers don't cost four times the work.
        A new picture wakes all the stream threads at the same moment, and they
        all ask for it at once. The first one through _encode_lock makes the
        JPEG; the others wait for it there, then find it ready-made.
        """
        with self._encode_lock:
            with self._lock:
                if self._jpeg_seq == seq and self._jpeg is not None:
                    return self._jpeg
            try:
                data = bytes(self.encode_jpeg(image))   # the slow part: outside _lock
            except Exception as error:
                self.picture_problem = f"Can't encode the live picture: {error}"
                self.warn_once("encode", f"WARN {self.picture_problem}")
                return None
            self.picture_problem = None
            with self._lock:
                if seq > self._jpeg_seq:
                    self._jpeg_seq, self._jpeg = seq, data
            return data

    def warn_once(self, topic, message):
        """Print a warning once per topic, so one problem doesn't flood the terminal."""
        with self._lock:
            if topic in self._warned:
                return
            self._warned.add(topic)
        print(message)


class _Server(ThreadingHTTPServer):
    """http.server's threaded server, with a few settings changed."""
    daemon_threads = True                   # request threads never keep the brain from exiting
    allow_reuse_address = os.name != "nt"   # on Windows this would let two programs share a port
    dashboard = None

    def server_bind(self):
        # Skip http.server's look-up of this computer's network name: on a Pi
        # without DNS it can stall start-up for seconds, and nothing uses it.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]

    def handle_error(self, request, client_address):
        """Something failed outside our request code. Stay quiet about browsers hanging up."""
        error = sys.exc_info()[1]
        if not isinstance(error, HANG_UPS):
            self.dashboard.warn_once("server", f"WARN dashboard web server: {error!r}")


class BadRequest(Exception):
    """A query parameter the server can't use. Becomes a 400 answer with this message."""


class _Handler(BaseHTTPRequestHandler):
    """Answers one browser request. http.server makes a new one per request, on its own thread."""
    timeout = 10        # seconds a silent or stuck browser may hold on to its connection

    def setup(self):
        super().setup()
        self.dashboard = self.server.dashboard
        self.answer_started = False     # True once a status line may have gone out

    def version_string(self):
        return "Skynode"

    def log_message(self, format, *args):
        pass            # stay quiet: the terminal is for tracking messages

    # http.server calls do_GET for GET, do_POST for POST, and so on. This
    # dashboard only reads, so every other verb gets "405 Method Not Allowed".
    def __getattr__(self, name):
        if name.startswith("do_"):
            return self.refuse_method
        raise AttributeError(name)

    def refuse_method(self):
        self.close_connection = True    # we never read request bodies: don't reuse the connection
        self.send_json(405, {"error": "The dashboard is read-only: it only answers GET."},
                       headers=[("Allow", "GET")])

    def do_GET(self):
        path, query = split_target(self.path)
        host = self.headers.get("Host")
        if not host_allowed(host):
            port = self.dashboard.port
            self.dashboard.warn_once("host", f"WARN the dashboard refused a page that asked for it "
                                             f"as {host!r}. Open it by IP address or "
                                             f"http://localhost:{port}/ instead.")
            self.close_connection = True
            self.send_json(403, {"error": "Open the dashboard by this computer's address, like "
                                          f"http://localhost:{port}/ or http://192.168.1.20:{port}/, "
                                          "not by a web site's name."})
            return
        # Checked here, before any route runs, so a refused request never takes
        # one of the MAX_VIEWERS stream places or makes a JPEG.
        if not fetch_allowed(path, self.headers.get("Sec-Fetch-Site"),
                             self.headers.get("Sec-Fetch-Mode"),
                             self.headers.get("Sec-Fetch-Dest")):
            self.dashboard.warn_once("cross-site", "WARN the dashboard refused a request from "
                                                   "another web site's page. Only its own page "
                                                   "may show the camera and the log.")
            self.send_json(403, {"error": "Only the dashboard's own page can load this, "
                                          "not other web sites."})
            return
        try:
            route = self.ROUTES.get(path)
            if route is not None:
                route(self, query)
            elif path.startswith("/assets/"):
                self.get_asset(path[len("/assets/"):])
            elif path.startswith("/snapshots/"):
                self.get_snapshot_file(path[len("/snapshots/"):])
            else:
                self.send_json(404, {"error": "Not found."})
        except BadRequest as error:
            self.send_json(400, {"error": str(error)})
        except HANG_UPS:
            pass                # the browser went away mid-answer: nothing to do
        except Exception as error:
            # Warn once per route ("/api/stats", "assets", ...), not once per file name
            dynamic = path.startswith(("/assets/", "/snapshots/"))
            topic = path.split("/")[1] if dynamic else path
            self.dashboard.warn_once(f"route {topic}",
                                     f"WARN dashboard error on {path}: {error!r}")
            if not self.answer_started:
                try:
                    self.send_json(500, {"error": "Something went wrong in the brain's "
                                                  "web server."})
                except OSError:
                    pass

    # ---- Pages and files -----------------------------------------------------------

    def get_index(self, query):
        self.send_file(self.dashboard.static_dir / "index.html", "text/html; charset=utf-8")

    def get_asset(self, rest):
        found = self.dashboard.asset(rest)
        if found is None:
            self.send_json(404, {"error": "Not found."})
        else:
            self.send_file(*found)

    def get_snapshot_file(self, rest):
        path = self.dashboard.snapshot_file(decode_path(rest))
        if path is None:
            self.send_json(404, {"error": "No such snapshot."})
        else:
            # Snapshots never change once written, so the browser may keep them a day
            self.send_file(Path(path), "image/jpeg", cache="max-age=86400")

    def send_file(self, path, content_type, cache="no-store"):
        try:
            body = path.read_bytes()
        except OSError:         # missing, a folder, or just deleted
            self.send_json(404, {"error": "Not found."})
            return
        self.send(200, body, content_type, cache=cache)

    # ---- The API -------------------------------------------------------------------

    def get_state(self, query):
        self.send_json(200, self.dashboard.state())

    def get_config(self, query):
        dash = self.dashboard
        self.send_json(200, {"node": dash.node_info(dash.clock()),
                             "config": dash.info.get("config", {})})

    def get_stats(self, query):
        params = read_query(query)
        hours = whole_number(params, "hours", 24, 1, MAX_STATS_HOURS)
        self.send_json(200, self.dashboard.stats(hours))

    def get_sightings(self, query):
        params = read_query(query)
        limit = whole_number(params, "limit", 50, 1, MAX_LIMIT)
        before = params.get("before")
        if before is not None and not SIGHTING_ID.fullmatch(before):
            raise BadRequest("before must be a sighting id, like 20261007-140217-001.")
        filters = read_filters(params, self.dashboard.clock())
        items, more = self.dashboard.recent(limit, before=before, **filters)
        self.send_json(200, {"items": items, "more": more})

    def get_sightings_csv(self, query):
        filters = read_filters(read_query(query), self.dashboard.clock())
        items, _ = self.dashboard.recent(CSV_LIMIT, **filters)
        self.send(200, sightings_csv(items), "text/csv; charset=utf-8", headers=[
            ("Content-Disposition", 'attachment; filename="skynode-sightings.csv"')])

    # ---- The live picture ----------------------------------------------------------

    def get_still(self, query):
        dash = self.dashboard
        seq, image = dash.latest_picture()
        jpeg = dash.jpeg(seq, image) if image is not None else None
        if jpeg is None:
            self.send_json(503, {"error": dash.picture_problem or "No camera picture yet."})
        else:
            self.send(200, jpeg, "image/jpeg")

    def get_stream(self, query):
        """MJPEG: one HTTP answer that never ends, carrying a new JPEG each time there is one.

        Each picture is a "part" that starts with the --frame boundary line and
        its own small header. The browser swaps in each picture as it arrives.
        """
        dash = self.dashboard
        if not dash.add_viewer(self.connection):
            self.send_json(503, {"error": f"The live stream is busy ({MAX_VIEWERS} viewers at "
                                          "most). Try again in a moment."})
            return
        try:
            seq, image = dash.latest_picture()
            jpeg = dash.jpeg(seq, image) if image is not None else None
            if jpeg is None and dash.picture_problem:
                self.send_json(503, {"error": dash.picture_problem})
                return
            self.answer_started = True
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")    # see send()
            self.end_headers()
            while not dash.stopping:
                if jpeg is not None:
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                     b"Content-Length: %d\r\n\r\n" % len(jpeg) + jpeg + b"\r\n")
                seq, image = dash.wait_for_picture(seq)     # sleeps; no busy loop
                if image is None:       # nothing new for a while: is anyone still there?
                    jpeg = None
                    if self.client_gone():
                        return
                    continue
                jpeg = dash.jpeg(seq, image)
                if jpeg is None:
                    return              # can't encode: hang up, the page falls back to stills
        except OSError:
            pass                        # the browser closed the tab, or stop() cut the connection
        finally:
            dash.remove_viewer(self.connection)

    def client_gone(self):
        """True if the browser hung up. A closed connection reads as "ready, but empty"."""
        try:
            ready, _, _ = select.select([self.connection], [], [], 0)
            return bool(ready) and self.connection.recv(1, socket.MSG_PEEK) == b""
        except (OSError, ValueError):
            return True

    ROUTES = {
        "/": get_index,
        "/api/state": get_state,
        "/api/stats": get_stats,
        "/api/sightings": get_sightings,
        "/api/sightings.csv": get_sightings_csv,
        "/api/config": get_config,
        "/snapshot.jpg": get_still,
        "/stream.mjpg": get_stream,
    }

    # ---- Sending answers -----------------------------------------------------------

    def send(self, status, body, content_type, cache="no-store", headers=()):
        """Send a complete answer: status line, headers, then the body."""
        self.answer_started = True
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        # "Only pages from this same address may use this." The browser enforces
        # it too (even for a copy it kept in its cache), on top of fetch_allowed().
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":      # an answer to HEAD has headers only
            self.wfile.write(body)

    def send_json(self, status, data, headers=()):
        self.send(status, to_json(data), "application/json; charset=utf-8", headers=headers)

    def send_error(self, code, message=None, explain=None):
        """http.server's own errors (a garbled request, an address far too long...) as JSON too."""
        self.close_connection = True
        if not self.answer_started:
            self.send_json(code, {"error": message or self.responses.get(code, ("Error",))[0]})


# ---- Reading requests ------------------------------------------------------------------

def split_target(target):
    """'/api/stats?hours=24' -> ('/api/stats', 'hours=24'). Drops any '#...' part."""
    path, _, query = target.split("#", 1)[0].partition("?")
    return path, query


def host_allowed(host):
    """May a browser that asked for us by this name (its Host header) see the dashboard?

    The trick this stops is called DNS rebinding. A web page you visit on
    some-site.example can quietly point the name some-site.example at
    127.0.0.1 (or at this Pi's address). Its scripts then talk to THIS server
    while the browser thinks they're still talking to some-site.example, so
    they could read the camera and the log. The browser does tell us which
    name it used, though, and a web site's name always ends in a real domain
    (.com, .org, ...). So we only answer to:
      - IP addresses: 127.0.0.1, 192.168.1.20, [::1]
      - names without a dot, like this computer's own name: raspberrypi
      - home-network names nobody can own on the internet: raspberrypi.local
    No Host at all is fine too: browsers always send one, so that's a script.
    """
    if host is None:
        return True
    host = host.strip().lower()
    if host.startswith("["):                    # IPv6 address, e.g. [::1]:8080
        name = host[1:host.find("]")] if "]" in host else ""
    else:
        name = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    name = name.removesuffix(".")               # "localhost." means the same as "localhost"
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        pass
    if not HOST_NAME.fullmatch(name):
        return False
    return "." not in name or name.endswith(HOME_NETWORK_ENDINGS)


def fetch_allowed(path, site, mode, dest):
    """May a browser have `path`, given who asked for it (its Sec-Fetch-... headers)?

    host_allowed() can't stop this one: any web page you visit can contain
    <img src="http://localhost:8080/stream.mjpg">, and the browser then asks
    for it by the right name. That page can't SEE the picture, but it could
    take all MAX_VIEWERS stream places (so you can't watch your own camera),
    keep this computer busy making JPEGs, or find out which snapshots exist
    (an <img> that loads versus one that fails).

    Modern browsers say who is asking, in the Sec-Fetch-Site header:
      same-origin    the dashboard's own page: its fetches, its <img src="/stream.mjpg">
      none           you: an address you typed, or a bookmark
      same-site, cross-site   a page from somewhere else
    Other pages get nothing, with one exception: a plain link from elsewhere
    to the front page (mode "navigate", dest "document") still opens it.
    No Sec-Fetch-Site at all is fine: older browsers and scripts don't send it.
    """
    if site is None:
        return True
    if site.strip().lower() in ("same-origin", "none"):
        return True
    return (path == "/" and str(mode).strip().lower() == "navigate"
            and str(dest).strip().lower() == "document")


def decode_path(text):
    """Undo the %-escapes in part of an address ('%2e' -> '.'), once. None if not valid UTF-8."""
    try:
        return unquote(text, errors="strict")
    except UnicodeDecodeError:
        return None


def read_query(query):
    """'hours=24&kind=check' -> {"hours": "24", "kind": "check"}. An empty value = not given."""
    try:
        pairs = parse_qsl(query, keep_blank_values=True, max_num_fields=MAX_QUERY_FIELDS)
    except ValueError:
        raise BadRequest("Too many query parameters.") from None
    params = {}
    for name, value in pairs:
        if name in params:
            raise BadRequest(f"Give {name} only once.")
        params[name] = value
    return {name: value for name, value in params.items() if value != ""}


def whole_number(params, name, default, lowest, highest):
    """params[name] as a whole number, pulled into lowest..highest. Not a number -> BadRequest."""
    text = params.get(name)
    if text is None:
        return default
    if not WHOLE_NUMBER.fullmatch(text):
        raise BadRequest(f"{name} must be a whole number.")
    return min(max(int(text), lowest), highest)


def one_of(params, name, allowed):
    value = params.get(name)
    if value is not None and value not in allowed:
        raise BadRequest(f"{name} must be one of: {', '.join(allowed)}.")
    return value


def read_filters(params, now):
    """The category / kind / hours filters that /api/sightings and the CSV export share."""
    hours = whole_number(params, "hours", None, 1, MAX_SIGHTINGS_HOURS)
    return {"category": one_of(params, "category", CATEGORIES),
            "kind": one_of(params, "kind", KINDS),
            "since": None if hours is None else now - hours * 3600}


# ---- Writing answers -------------------------------------------------------------------

def to_json(data):
    """data -> UTF-8 JSON bytes. NaN and Infinity aren't valid JSON, so they become null."""
    return json.dumps(json_safe(data), allow_nan=False).encode("utf-8")


def json_safe(value):
    """A copy of `value` that JSON can always hold: non-finite numbers -> None, tuples -> lists,
    anything unusual (like a file path) -> text."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        value = float(value)
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [json_safe(item) for item in value]
    return str(value)


def sightings_csv(items):
    """Sighting records -> CSV bytes, one row per record, with local ISO 8601 times."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for item in items:
        if not isinstance(item, dict):
            continue
        writer.writerow([
            csv_text(item.get("id")), csv_text(item.get("kind")), csv_text(item.get("category")),
            csv_text(item.get("class_name")), iso_time(item.get("start")),
            iso_time(item.get("end")), csv_number(item.get("duration_s")),
            csv_number(item.get("confidence")), csv_number(item.get("pan")),
            csv_number(item.get("tilt")), csv_number(item.get("frames")),
            csv_text(item.get("snapshot")),
        ])
    return out.getvalue().encode("utf-8", errors="replace")


def csv_text(value):
    """Text for a CSV cell. Spreadsheet apps run a cell starting with = + - or @ as a formula,
    so such text gets a ' in front."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def csv_number(value):
    return str(value) if is_number(value) else ""


def iso_time(t):
    """Unix time -> local time in ISO 8601 with its UTC offset, e.g. 2026-10-07T14:02:17+02:00."""
    if not is_number(t):
        return ""
    try:
        return datetime.fromtimestamp(t, timezone.utc).astimezone().isoformat(timespec="seconds")
    except (OverflowError, OSError, ValueError):
        return ""


def empty_stats(now, hours):
    """What /api/stats answers when there's no logger: all zeros, `hours` empty hour buckets."""
    return {"hours": hours, "now": now, "total": 0, "drone": 0, "aircraft": 0, "other": 0,
            "previous_total": None,
            "last": {"drone": None, "aircraft": None, "other": None},
            "buckets": [{"start": start, "aircraft": 0, "drone": 0, "other": 0}
                        for start in hour_starts(now, hours)]}


def hour_starts(now, hours):
    """Start times of the last `hours` local clock hours, oldest first; the last contains `now`.

    Steps back an hour at a time through the local clock (with the real UTC
    offset at each moment), so it stays right in UTC+5:30 and on daylight-saving days.
    """
    def hour_start(t):
        local = datetime.fromtimestamp(t, timezone.utc).astimezone()
        return local.replace(minute=0, second=0, microsecond=0).timestamp()

    starts = [hour_start(now)]
    while len(starts) < hours:
        starts.append(hour_start(starts[-1] - 1))   # one second earlier = the hour before
    return starts[::-1]


# ---- Small helpers ---------------------------------------------------------------------

def is_number(value):
    """True for a finite int or float (not True/False, not NaN or Infinity)."""
    return (isinstance(value, numbers.Real) and not isinstance(value, bool)
            and math.isfinite(value))


def finite(value, default=0.0):
    """value as a plain float, or `default` if it's missing, NaN or infinite (not valid JSON)."""
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return value if math.isfinite(value) else default


def frame_size(frame):
    """(width, height) of a frame, or (0, 0) if there isn't one."""
    shape = getattr(frame, "shape", None)
    if shape is None or len(shape) < 2:
        return 0, 0
    return int(shape[1]), int(shape[0])


def normalised_box(box, width, height):
    """Pixel box (x1, y1, x2, y2) -> fractions of the frame (0..1), so any frame size works."""
    if box is None or width <= 0 or height <= 0:
        return None
    x1, y1, x2, y2 = (finite(v) for v in box)
    return [round(min(max(value / size, 0.0), 1.0), 4)
            for value, size in ((x1, width), (y1, height), (x2, width), (y2, height))]


def default_encode_jpeg(image):
    """Image -> JPEG bytes, with OpenCV (imported here so the rest works without it)."""
    import cv2
    ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, STREAM_QUALITY])
    if not ok:
        raise ValueError("OpenCV couldn't encode the picture as JPEG")
    return data.tobytes()


def default_shrink(frame, max_width):
    """A copy of the frame, scaled down to at most max_width pixels wide (never up)."""
    height, width = frame.shape[:2]
    if width <= max_width:
        return frame.copy()
    import cv2
    size = (max_width, max(1, round(height * max_width / width)))    # OpenCV wants (width, height)
    return cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
