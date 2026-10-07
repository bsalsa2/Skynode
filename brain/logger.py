"""Remember what the camera saw: a log of sightings, for the dashboard and for you.

A *sighting* is one continuous lock: it starts on the first frame the tracker
returns a target, and ends on the first frame where the tracker has given up
(tracker.locked is False). For each sighting we keep one line of facts (when,
how long, what the model called it, how sure it was at its best moment, where
the camera was pointing) plus a small JPEG of that best moment.

Where it all goes ([logger] folder in brain/config.toml, normally logs/):

    logs/sightings-2026-10-07.jsonl          one file per local day, one record per line
    logs/snapshots/20261007-140217-001.jpg   the best frame of that sighting

JSON Lines = one JSON object per line. Each record is appended and flushed the
moment it is finished, so a crash loses nothing that was already logged, and a
line cut short by a power cut only spoils that one line.

While nothing is being tracked, a "sky check" is logged every `heartbeat_min`
minutes of the local clock (13:00, 14:00, ...). It proves the node was watching
and saw nothing, so a gap in the log means "not running", not "empty sky".

Threads: the main loop calls update() once per frame. The dashboard's web
server calls recent(), stats(), current() and snapshot_path() from its own
threads, so everything they share sits behind one lock. Slow work (JPEG
encoding, writing files) happens outside the lock.

OpenCV is only imported when a snapshot is actually made, so this module (and
its tests) work without it.
"""
import bisect
import json
import math
import os
import re
import threading
import time
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path

DRONE, AIRCRAFT, OTHER, CLEAR = "drone", "aircraft", "other", "clear"
CATEGORIES = (DRONE, AIRCRAFT, OTHER, CLEAR)
KINDS = ("sighting", "check")
SNAPSHOT_WIDTH = 640                                 # snapshots are shrunk to at most this wide
SAFE_ID = re.compile(r"[0-9A-Za-z_-]+")              # ids end up in file names and URLs
SNAPSHOT_NAME = re.compile(r"[0-9A-Za-z_-]+\.jpg")   # the only names snapshot_path() accepts


@dataclass
class Sighting:
    """One finished record: a sighting, or a sky check (kind="check")."""
    id: str                 # local start time + a counter, e.g. "20261007-140217-001"
    kind: str               # "sighting" or "check"
    category: str           # "drone", "aircraft", "other", or "clear" for checks
    class_name: str         # what the model called it, e.g. "airplane" ("" for checks)
    start: float            # unix time (seconds) of the first frame of the lock
    end: float              # unix time of the last frame the target was actually seen
    duration_s: float       # end - start, to 0.1 s
    confidence: float       # the BEST confidence during the lock, to 0.01 (0.0 for checks)
    pan: float              # where the camera pointed at that best moment, degrees
    tilt: float
    box: list | None        # [x1, y1, x2, y2] at that moment, as fractions 0..1 of the frame
    frames: int             # how many frames the target was seen in
    snapshot: str | None    # JPEG file name in <folder>/snapshots/, or None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        """Rebuild a Sighting from one line of a log file.

        Raises ValueError if anything is missing or looks wrong, so a damaged
        line gets skipped instead of confusing the dashboard later.
        """
        if not isinstance(data, dict) or not all(name in data for name in FIELD_NAMES):
            raise ValueError("not a sighting record")
        values = {name: data[name] for name in FIELD_NAMES}     # extra keys are ignored
        box, frames, snapshot = values["box"], values["frames"], values["snapshot"]
        checks = [
            isinstance(values["id"], str) and SAFE_ID.fullmatch(values["id"]),
            values["kind"] in KINDS,
            values["category"] in CATEGORIES,
            isinstance(values["class_name"], str),
            all(is_number(values[name]) for name in NUMBER_FIELDS),
            box is None or (isinstance(box, list) and len(box) == 4
                            and all(is_number(v) for v in box)),
            isinstance(frames, int) and not isinstance(frames, bool) and frames >= 0,
            snapshot is None or (isinstance(snapshot, str) and SNAPSHOT_NAME.fullmatch(snapshot)),
        ]
        if not all(checks):
            raise ValueError("a value has the wrong type")
        for name in NUMBER_FIELDS:
            values[name] = float(values[name])
        if box is not None:
            values["box"] = [float(v) for v in box]
        return cls(**values)


FIELD_NAMES = [f.name for f in fields(Sighting)]
NUMBER_FIELDS = ("start", "end", "duration_s", "confidence", "pan", "tilt")


@dataclass
class _OpenSighting:
    """A lock still in progress. It becomes a Sighting when the lock ends."""
    start: float
    end: float = 0.0
    frames: int = 0
    class_name: str = ""    # this and everything below describe the best frame so far
    confidence: float = 0.0
    pan: float = 0.0
    tilt: float = 0.0
    box: list | None = None
    image: object = None    # shrunk copy of the best frame, turned into a JPEG at the end


class SightingLogger:
    """Turns the tracker's frame-by-frame output into logged sightings.

        logger = SightingLogger("logs")
        every frame:  logged = logger.update(target, tracker.locked, frame, pan, tilt)
        at the end:   logger.close()
    """

    def __init__(self, folder, drone_classes=("drone",),
                 aircraft_classes=("airplane", "aircraft", "helicopter"),
                 min_duration_s=0.5, snapshots=True, heartbeat_min=60,
                 keep_hours=168, clock=time.time, encode_jpeg=None, shrink=None):
        self.folder = Path(folder)
        self.snapshot_folder = self.folder / "snapshots"
        self.drone_classes = {name.lower() for name in drone_classes}
        self.aircraft_classes = {name.lower() for name in aircraft_classes}
        self.min_duration_s = min_duration_s    # shorter locks are detector blinks: not logged
        self.snapshots = snapshots
        self.heartbeat_min = heartbeat_min      # 0 = no sky checks
        self.keep_hours = keep_hours            # how much history to keep in memory
        self.clock = clock
        self.encode_jpeg = encode_jpeg if encode_jpeg is not None else default_encode_jpeg
        self.shrink = shrink if shrink is not None else default_shrink

        self._lock = threading.Lock()   # guards _open, _records and history_start
        self._open = None               # the lock in progress (an _OpenSighting), or None
        self._ids = set()               # every id seen, so a new one never repeats an old one
        self._seq = 0                   # the counter at the end of each new id
        self._last_slot = None          # heartbeat slot of the previous frame (None = no frame yet)
        self._warned = set()
        self.skipped_lines = 0          # damaged lines found while loading old logs

        self.started_at = clock()
        self._records = self._load(self.started_at - keep_hours * 3600)    # oldest first
        earliest = self._records[0].start if self._records else self.started_at
        # The earliest moment the logs vouch for: before this, "no sightings" means "don't know"
        self.history_start = min(self.started_at, earliest)
        if self.skipped_lines:
            print(f"WARN skipped {self.skipped_lines} damaged line(s) in the logs in {self.folder}")

    def categorize(self, class_name):
        """Which category a model class belongs to: "drone", "aircraft" or "other"."""
        name = str(class_name).lower()
        if name in self.drone_classes:
            return DRONE
        if name in self.aircraft_classes:
            return AIRCRAFT
        return OTHER

    # ---- Main loop side --------------------------------------------------------

    def update(self, target, locked, frame, pan, tilt, now=None):
        """Feed one frame. Call it once per frame, BEFORE anything draws on `frame`.

        target: this frame's target from the tracker, or None
        locked: tracker.locked after this frame
        Returns the Sighting if one just ended and was logged, otherwise None.
        (Sky checks are logged quietly and not returned.)
        """
        now = self.clock() if now is None else now
        # A sky check is only honest if nothing was tracked going into this
        # frame and nothing is in it now.
        quiet = self._open is None and target is None and not locked
        heartbeat = self._heartbeat_due(now)

        if target is not None:
            self._see(target, frame, pan, tilt, now)
        logged = None
        if not locked and self._open is not None:
            logged = self._finish(now)
        if heartbeat and quiet:
            self._log_check(pan, tilt, now)
        return logged

    def close(self, now=None):
        """Shutting down: log the lock in progress, if any (same rules as a normal end)."""
        now = self.clock() if now is None else now
        if self._open is None:
            return None
        return self._finish(now)

    def _see(self, target, frame, pan, tilt, now):
        """The tracker returned a target: start a sighting, or add this frame to the open one."""
        confidence = finite(target.confidence)
        # Only the main loop changes self._open, so it can read it here without the lock.
        best = self._open is None or confidence > self._open.confidence
        box = image = None
        if best and frame is not None:
            height, width = frame.shape[:2]
            box = normalised_box(target.box, width, height)
            if self.snapshots:
                image = self._shrunk_copy(frame)    # done before taking the lock: it's slow-ish
        with self._lock:
            if self._open is None:
                self._open = _OpenSighting(start=now)
            sighting = self._open
            sighting.frames += 1
            sighting.end = now
            if best:                # a new best moment: remember what and where it was
                sighting.class_name = str(target.class_name)
                sighting.confidence = confidence
                sighting.pan, sighting.tilt = finite(pan), finite(tilt)
                sighting.box, sighting.image = box, image

    def _finish(self, now):
        """End the open lock and log it if it lasted long enough. Returns the Sighting or None."""
        with self._lock:
            sighting, self._open = self._open, None
        if sighting.end - sighting.start < self.min_duration_s:
            return None             # too short: most likely the detector blinking
        record = Sighting(
            id="", kind="sighting", category=self.categorize(sighting.class_name),
            class_name=sighting.class_name, start=round(sighting.start, 3),
            end=round(sighting.end, 3), duration_s=round(sighting.end - sighting.start, 1),
            confidence=round(sighting.confidence, 2), pan=round(sighting.pan, 1),
            tilt=round(sighting.tilt, 1), box=sighting.box, frames=sighting.frames, snapshot=None)
        return self._commit(record, sighting.image, now)

    def _heartbeat_due(self, now):
        """True if a heartbeat time (e.g. 13:00:00 local) passed since the previous frame.

        Compares which heartbeat "slot" of the local day this frame and the
        previous one fall in, so it notices the boundary however far apart the
        frames are, and never fires on the very first frame. Using the local
        clock's own hour and minute (not unix time) keeps it right in places
        that are 30 or 45 minutes off UTC, and on daylight-saving days (the
        hour that repeats in autumn gets no second check).
        """
        if self.heartbeat_min <= 0:
            return False
        local = datetime.fromtimestamp(now)
        slot = (local.date(), (local.hour * 60 + local.minute) // self.heartbeat_min)
        previous, self._last_slot = self._last_slot, slot
        return previous is not None and slot > previous

    def _log_check(self, pan, tilt, now):
        start = round(now, 3)
        record = Sighting(id="", kind="check", category=CLEAR, class_name="", start=start,
                          end=start, duration_s=0.0, confidence=0.0, pan=round(finite(pan), 1),
                          tilt=round(finite(tilt), 1), box=None, frames=0, snapshot=None)
        self._commit(record, None, now)

    def _commit(self, record, image, now):
        """Give the record an id, save its snapshot and log line, then show it to the dashboard."""
        record.id = self._new_id(record.start)
        if image is not None:
            record.snapshot = self._save_snapshot(record.id, image)
        self._append_line(record)
        with self._lock:
            bisect.insort(self._records, record, key=start_time)    # stays sorted by start
            self._prune(now)
        return record

    def _new_id(self, start):
        """A unique, filename-safe id: local start time + a counter, e.g. 20261007-140217-001."""
        stamp = datetime.fromtimestamp(start).strftime("%Y%m%d-%H%M%S")
        # Only the main loop makes ids, so _ids and _seq need no lock.
        while True:
            self._seq += 1
            sighting_id = f"{stamp}-{self._seq:03d}"
            # Skip ids already taken, e.g. by an earlier run in the same second
            taken = (sighting_id in self._ids
                     or (self.snapshot_folder / f"{sighting_id}.jpg").exists())
            if not taken:
                self._ids.add(sighting_id)
                return sighting_id

    def _shrunk_copy(self, frame):
        """A small copy of the frame for the snapshot (a copy: the main loop draws on the frame)."""
        try:
            return self.shrink(frame, SNAPSHOT_WIDTH)
        except Exception as error:      # e.g. no OpenCV: keep logging, just without pictures
            self._warn("snapshot", f"WARN couldn't make a snapshot ({error}). "
                                   "Sightings are still logged.")
            return None

    def _save_snapshot(self, sighting_id, image):
        """Encode the best frame to <folder>/snapshots/<id>.jpg. Returns the file name, or None."""
        try:
            data = self.encode_jpeg(image)
            self.snapshot_folder.mkdir(parents=True, exist_ok=True)
            path = self.snapshot_folder / f"{sighting_id}.jpg"
            part = path.with_suffix(".part")
            part.write_bytes(data)
            os.replace(part, path)      # appears all at once: the web server never sees half a JPEG
            return path.name
        except Exception as error:      # no OpenCV, disk full, ...: log the sighting anyway
            self._warn("snapshot", f"WARN couldn't make a snapshot ({error}). "
                                   "Sightings are still logged.")
            return None

    def _append_line(self, record):
        """Add the record to its day's .jsonl file (named by the local date of its start)."""
        path = self.folder / f"sightings-{datetime.fromtimestamp(record.start):%Y-%m-%d}.jsonl"
        line = json.dumps(record.to_dict(), allow_nan=False) + "\n"
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            if not ends_cleanly(path):
                line = "\n" + line      # a crash cut the last line short: don't glue onto it
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()               # hand it to the OS now, so a crash can't lose it
        except OSError as error:        # keep tracking even if the disk is full
            self._warn("write", f"WARN can't write the sighting log {path}: {error}")

    def _prune(self, now):
        """Forget records older than keep_hours (the files on disk keep them). Hold the lock."""
        cutoff = now - self.keep_hours * 3600
        old = bisect.bisect_left(self._records, cutoff, key=start_time)
        if old:
            del self._records[:old]
            # Memory no longer vouches for the time before the cutoff
            self.history_start = max(self.history_start, cutoff)

    def _load(self, cutoff):
        """Read back the records that started at or after `cutoff` from the daily files."""
        records = []
        # Look one extra day back, in case the computer's timezone changed since
        first_day = (datetime.fromtimestamp(cutoff) - timedelta(days=1)).date()
        for path in sorted(self.folder.glob("sightings-*.jsonl")):
            try:
                day = datetime.strptime(path.stem.removeprefix("sightings-"), "%Y-%m-%d").date()
            except ValueError:
                continue                # not one of our daily files
            if day < first_day:
                continue                # too old to matter
            try:
                lines = path.read_bytes().splitlines()
            except OSError as error:
                print(f"WARN can't read {path}: {error}")
                continue
            for line in lines:
                if not line.strip():
                    continue
                try:
                    record = Sighting.from_dict(json.loads(line))
                except (ValueError, OverflowError):     # damaged, e.g. cut short by a crash
                    self.skipped_lines += 1
                    continue
                if record.id in self._ids:              # the same id twice: keep the first
                    self.skipped_lines += 1
                    continue
                self._ids.add(record.id)
                if record.start >= cutoff:
                    records.append(record)
        records.sort(key=start_time)    # oldest first; equal starts keep their file order
        return records

    def _warn(self, topic, message):
        """Print a warning once per topic, so a full disk doesn't flood the terminal."""
        if topic not in self._warned:
            self._warned.add(topic)
            print(message)

    # ---- Web server side (any thread) --------------------------------------------

    def current(self):
        """The lock in progress as a dict, or None. Its confidence is the best so far."""
        with self._lock:
            sighting = self._open
            if sighting is None:
                return None
            return {"category": self.categorize(sighting.class_name),
                    "class_name": sighting.class_name, "start": round(sighting.start, 3),
                    "confidence": round(sighting.confidence, 2), "frames": sighting.frames}

    def recent(self, limit=50, before=None, category=None, kind=None, since=None):
        """Logged records as dicts, newest first. Returns (records, more).

        before:   an id: only records older than that one (how the next page is loaded)
        category: only "drone", "aircraft", "other" or "clear"
        kind:     only "sighting" or "check"
        since:    unix time: only records that started at or after it
        more is True if older matching records exist beyond this page.
        """
        page, more = [], False
        with self._lock:
            end = len(self._records)
            if before is not None:
                end = next((i for i, r in enumerate(self._records) if r.id == before), None)
                if end is None:
                    return [], False    # unknown id (or forgotten since): nothing to page through
            for record in reversed(self._records[:end]):
                if since is not None and record.start < since:
                    break               # sorted by start, so everything further back is older still
                if category is not None and record.category != category:
                    continue
                if kind is not None and record.kind != kind:
                    continue
                if len(page) >= limit:
                    more = True
                    break
                page.append(record)
        return [record.to_dict() for record in page], more    # records never change once logged

    def stats(self, now=None, hours=24):
        """Sighting counts for the dashboard over the last `hours` hours. Sky checks don't count.

        total and the per-category counts cover sightings that started in
        (now - hours, now]. previous_total is the same-length window just
        before, or None when the logs don't reach back that far. buckets are
        `hours` local clock hours, oldest first; the last one is the current,
        unfinished hour. A sighting counts in the hour it started in.
        """
        now = self.clock() if now is None else now
        hours = max(1, int(hours))
        window_start = now - hours * 3600
        previous_start = now - 2 * hours * 3600
        starts = hour_starts(now, hours)
        buckets = [{"start": start, AIRCRAFT: 0, DRONE: 0, OTHER: 0} for start in starts]
        counts = {DRONE: 0, AIRCRAFT: 0, OTHER: 0}
        last = {DRONE: None, AIRCRAFT: None, OTHER: None}
        previous_total = 0

        with self._lock:
            first = bisect.bisect_right(self._records, previous_start, key=start_time)
            records = self._records[first:]
            history_start = self.history_start

        for record in records:          # oldest first
            if record.kind != "sighting" or record.category not in counts or record.start > now:
                continue
            if record.start <= window_start:
                previous_total += 1
                continue
            counts[record.category] += 1
            last[record.category] = record.start
            if record.start >= starts[0]:
                buckets[bisect.bisect_right(starts, record.start) - 1][record.category] += 1

        return {"hours": hours, "now": now, "total": sum(counts.values()),
                DRONE: counts[DRONE], AIRCRAFT: counts[AIRCRAFT], OTHER: counts[OTHER],
                "previous_total": previous_total if history_start <= previous_start else None,
                "last": last, "buckets": buckets}

    def snapshot_path(self, name):
        """Path of a snapshot file, or None if the name is odd or the file doesn't exist.

        Only plain names like "20261007-140217-001.jpg" pass, so a request
        can never reach outside the snapshots folder ("../" and the like).
        """
        if not isinstance(name, str) or not SNAPSHOT_NAME.fullmatch(name):
            return None
        path = self.snapshot_folder / name
        return path if path.is_file() else None


def start_time(record):
    return record.start


def is_number(value):
    """True for a finite int or float. (Python's JSON reads NaN and Infinity; we don't want them.)"""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def finite(value, default=0.0):
    """value as a plain float, or `default` if it's missing, NaN or infinite (not valid JSON)."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def normalised_box(box, width, height):
    """Pixel box (x1, y1, x2, y2) -> fractions of the frame (0..1), so any frame size works."""
    if box is None or width <= 0 or height <= 0:
        return None
    x1, y1, x2, y2 = (finite(v) for v in box)
    return [round(min(max(value / size, 0.0), 1.0), 4)
            for value, size in ((x1, width), (y1, height), (x2, width), (y2, height))]


def ends_cleanly(path):
    """True if the file is missing, empty, or ends with a newline."""
    try:
        with open(path, "rb") as f:
            if f.seek(0, os.SEEK_END) == 0:
                return True
            f.seek(-1, os.SEEK_END)
            return f.read(1) == b"\n"
    except FileNotFoundError:
        return True


def hour_start(t):
    """Unix time at which the local clock hour containing `t` began (13:00:00 for 13:42:10).

    Goes through datetime with the real UTC offset at that moment. Simply
    rounding unix time down to a multiple of 3600 gives the start of the UTC
    hour, which is NOT the local one in India (UTC+5:30) or Nepal (UTC+5:45).
    """
    local = datetime.fromtimestamp(t, timezone.utc).astimezone()   # local time, correct offset
    return local.replace(minute=0, second=0, microsecond=0).timestamp()


def hour_starts(now, hours):
    """Start times of the last `hours` local clock hours, oldest first; the last contains `now`.

    Steps back one hour at a time from the current one, so daylight-saving
    days come out right: the hour that's skipped in spring isn't there, and
    the hour that repeats in autumn appears twice.
    """
    starts = [hour_start(now)]
    while len(starts) < hours:
        starts.append(hour_start(starts[-1] - 1))  # one second earlier = inside the previous hour
    return starts[::-1]


def default_encode_jpeg(image):
    """Image -> JPEG bytes, with OpenCV (imported here, so the module itself doesn't need it)."""
    import cv2
    ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise ValueError("OpenCV couldn't encode the image as JPEG")
    return data.tobytes()


def default_shrink(frame, max_w):
    """A copy of the frame, scaled down to at most max_w pixels wide (never up)."""
    height, width = frame.shape[:2]
    if width <= max_w:
        return frame.copy()
    import cv2
    size = (max_w, max(1, round(height * max_w / width)))      # OpenCV wants (width, height)
    return cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
