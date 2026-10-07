"""Remember what the camera saw: a log of sightings, for the dashboard and for you.

A *sighting* is one continuous lock: it starts on the first frame the tracker
returns a target, and ends on the first frame where the tracker has given up
(tracker.locked is False). For each sighting we keep one line of facts (when,
how long, what the model called it, how sure it was at its best moment, where
the camera was pointing) plus a small JPEG of that best moment.

Where it all goes ([logger] folder in brain/config.toml, normally logs/):

    logs/skynode.db                          every sighting and sky check (SQLite)
    logs/snapshots/20261007-140217-001.jpg   the best frame of that sighting

SQLite is one ordinary file that any tool can open (the `sqlite3` command, Python,
DB Browser). Each record is committed the moment it is finished, so a crash or a
power cut loses nothing that was already logged. Older versions wrote one
sightings-YYYY-MM-DD.jsonl file per day; those are imported into the database
the first time the new version starts, then renamed to .jsonl.imported.

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
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path

DRONE, AIRCRAFT, OTHER, CLEAR = "drone", "aircraft", "other", "clear"
CATEGORIES = (DRONE, AIRCRAFT, OTHER, CLEAR)
KINDS = ("sighting", "check")
SNAPSHOT_WIDTH = 640                                 # snapshots are shrunk to at most this wide
SAFE_ID = re.compile(r"[0-9A-Za-z_-]+")              # ids end up in file names and URLs
SNAPSHOT_NAME = re.compile(r"[0-9A-Za-z_-]+\.jpg")   # the only names snapshot_path() accepts
MAX_LINE_BYTES = 16 * 1024      # old .jsonl files only: a real record is a few hundred bytes
DB_NAME = "skynode.db"


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


# One column per Sighting field. "end" is a reserved word in SQL, so the time
# columns are called started and ended.
COLUMNS = ("id", "kind", "category", "class_name", "started", "ended", "duration_s",
           "confidence", "pan", "tilt", "box", "frames", "snapshot")
SCHEMA = """
CREATE TABLE IF NOT EXISTS sightings (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL CHECK (kind IN ('sighting', 'check')),
    category    TEXT NOT NULL CHECK (category IN ('drone', 'aircraft', 'other', 'clear')),
    class_name  TEXT NOT NULL,
    started     REAL NOT NULL,      -- unix time, seconds
    ended       REAL NOT NULL,
    duration_s  REAL NOT NULL,
    confidence  REAL NOT NULL,
    pan         REAL NOT NULL,
    tilt        REAL NOT NULL,
    box         TEXT,               -- JSON [x1, y1, x2, y2] as fractions of the frame, or NULL
    frames      INTEGER NOT NULL,
    snapshot    TEXT                -- JPEG file name in snapshots/, or NULL
);
CREATE INDEX IF NOT EXISTS sightings_started ON sightings (started);
"""


def row_to_dict(row):
    """One database row as the dict Sighting.from_dict() expects (raises ValueError if damaged)."""
    data = dict(zip(COLUMNS, row))
    data["start"], data["end"] = data.pop("started"), data.pop("ended")
    if data["box"] is not None:
        data["box"] = json.loads(data["box"])
    return data


class SightingDB:
    """The sightings table in <folder>/skynode.db.

    Only the main loop writes to it, and only the main loop reads it (once, at
    start-up): the dashboard's threads read the logger's in-memory copy, so the
    connection never crosses threads. The file and its folder are created on
    the first write, so a node that never sees anything leaves no trace.
    """

    def __init__(self, folder):
        self.path = Path(folder) / DB_NAME
        self._conn = None

    def _connect(self, create):
        """The open connection, opening it first if needed. None if the file doesn't exist
        yet and create is False."""
        if self._conn is None:
            if not self.path.is_file():
                if not create:
                    return None
                self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path, timeout=10)
            try:
                conn.executescript(SCHEMA)
                conn.execute("SELECT count(*) FROM sightings").fetchone()  # is it really ours?
            except sqlite3.DatabaseError:
                conn.close()
                raise
            self._conn = conn
        return self._conn

    def move_damaged_aside(self):
        """Rename a file that isn't a usable database, so a fresh one can take its place."""
        self.close()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = self.path.with_name(f"{self.path.name}.damaged-{stamp}")
        os.replace(self.path, target)
        return target

    def insert(self, record, ignore_duplicates=False):
        conn = self._connect(create=True)
        values = record.to_dict()
        row = [values["start" if c == "started" else "end" if c == "ended" else c] for c in COLUMNS]
        row[COLUMNS.index("box")] = None if record.box is None else json.dumps(record.box)
        verb = "INSERT OR IGNORE" if ignore_duplicates else "INSERT"
        with conn:      # commits (or rolls back) right now
            cursor = conn.execute(
                f"{verb} INTO sightings ({', '.join(COLUMNS)}) "
                f"VALUES ({', '.join('?' * len(COLUMNS))})", row)
        return cursor.rowcount == 1

    def ids(self):
        """Every id in the table, so a new id never repeats an old one."""
        conn = self._connect(create=False)
        if conn is None:
            return set()
        return {row[0] for row in conn.execute("SELECT id FROM sightings")}

    def load(self, cutoff):
        """(records that started at or after `cutoff`, oldest first; how many rows were damaged)."""
        conn = self._connect(create=False)
        if conn is None:
            return [], 0
        records, skipped = [], 0
        query = f"SELECT {', '.join(COLUMNS)} FROM sightings WHERE started >= ? ORDER BY started, rowid"
        for row in conn.execute(query, (cutoff,)):
            try:
                records.append(Sighting.from_dict(row_to_dict(row)))
            except (ValueError, TypeError, OverflowError, RecursionError):
                skipped += 1        # edited by hand, or from a broken version: skip, don't crash
        return records, skipped

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def import_jsonl(folder, db):
    """Move records from the old per-day .jsonl files into the database, once.

    Returns (imported, damaged). Each file is renamed to .jsonl.imported when
    it's done, so it isn't read again. Damaged lines (cut short by a crash,
    edited by hand, not ours) are skipped and counted.
    """
    imported = damaged = 0
    seen = set()
    for path in sorted(Path(folder).glob("sightings-*.jsonl")):
        try:
            datetime.strptime(path.stem.removeprefix("sightings-"), "%Y-%m-%d")
            lines = path.read_bytes().splitlines()
        except (ValueError, OSError):
            continue                    # not one of our daily files, or unreadable: leave it
        for line in lines:
            if not line.strip():
                continue
            if len(line) > MAX_LINE_BYTES:              # far too long to be one of ours
                damaged += 1
                continue
            try:
                record = Sighting.from_dict(json.loads(line))
            except (ValueError, OverflowError, RecursionError):
                damaged += 1
                continue
            if record.id in seen:                       # the same id twice: keep the first
                damaged += 1
                continue
            seen.add(record.id)
            if db.insert(record, ignore_duplicates=True):
                imported += 1
        try:
            os.replace(path, path.with_name(path.name + ".imported"))
        except OSError:
            pass                        # it stays, and importing it again adds nothing new
    return imported, damaged


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
        self._db = SightingDB(self.folder)
        self._ids = set()               # every id seen, so a new one never repeats an old one
        self._seq = 0                   # the counter at the end of each new id
        self._last_slot = None          # heartbeat slot of the previous frame (None = no frame yet)
        self._warned = set()
        self.skipped_lines = 0          # damaged lines found while loading old logs

        self.started_at = clock()
        self._open_database()
        self._records = self._load(self.started_at - keep_hours * 3600)    # oldest first
        earliest = self._records[0].start if self._records else self.started_at
        # The earliest moment the logs vouch for: before this, "no sightings" means "don't know"
        self.history_start = min(self.started_at, earliest)
        if self.skipped_lines:
            print(f"WARN skipped {self.skipped_lines} damaged record(s) in the logs in {self.folder}")

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
        logged = None if self._open is None else self._finish(now)
        self._db.close()        # reopened by the next write, if there is one
        return logged

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
        self._store(record)
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

    def _store(self, record):
        """Save the record in the database right now (committed, so a crash can't lose it)."""
        try:
            self._db.insert(record)
        except (sqlite3.Error, OSError) as error:   # keep tracking even if the disk is full
            self._warn("write", f"WARN can't write the sighting log {self._db.path}: {error}")

    def _prune(self, now):
        """Forget records older than keep_hours (the files on disk keep them). Hold the lock."""
        cutoff = now - self.keep_hours * 3600
        old = bisect.bisect_left(self._records, cutoff, key=start_time)
        if old:
            del self._records[:old]
            # Memory no longer vouches for the time before the cutoff
            self.history_start = max(self.history_start, cutoff)

    def _open_database(self):
        """Open skynode.db (if there is one), bring in old .jsonl files, and note every id."""
        try:
            self._ids = self._db.ids()
        except sqlite3.DatabaseError as error:
            # Not a database (or broken beyond use): keep the file, start a fresh one
            try:
                moved = self._db.move_damaged_aside()
                print(f"WARN {self._db.path} is damaged ({error}). Moved it to {moved.name} "
                      "and started a new log.")
            except OSError as problem:
                print(f"WARN {self._db.path} is damaged ({error}) and can't be moved: {problem}")
            self._ids = set()
        try:
            _, damaged = import_jsonl(self.folder, self._db)
            self.skipped_lines += damaged
            self._ids = self._db.ids()
        except (sqlite3.Error, OSError) as error:
            self._warn("import", f"WARN couldn't import the old .jsonl logs: {error}")

    def _load(self, cutoff):
        """Read back the records that started at or after `cutoff` from the database."""
        try:
            records, skipped = self._db.load(cutoff)
        except sqlite3.Error as error:
            self._warn("read", f"WARN can't read the sighting log {self._db.path}: {error}")
            return []
        self.skipped_lines += skipped
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
