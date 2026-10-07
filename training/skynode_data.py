"""Data helpers for the Colab training notebook (training/skynode_train.ipynb).

The notebook does the GPU work (pre-labeling and training). This file does the
careful bookkeeping around it, so it can be tested on any computer:

- pull frames out of phone videos,
- turn detector boxes into YOLO label lines,
- split frames into train / validation WITHOUT leaking (see split_frames),
- build the final YOLO dataset folder, optionally merged with an older dataset,
- make contact sheets so you can check the labels by eye before training.

A YOLO label line is: class_id center_x center_y width height, with the four
numbers as fractions of the image size (0 to 1). One line per object, one
.txt file per image. An image with an empty .txt file means "nothing here",
which is useful: empty-sky frames teach the model what NOT to flag.
"""
import json
import math
import random
import shutil
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SEPARATOR = "__"      # frame names look like  drone-backyard__000120.jpg


# ---- Videos and frames -----------------------------------------------------------

def list_videos(folder):
    """Every video file directly inside `folder`, sorted by name."""
    folder = Path(folder)
    return sorted(p for p in folder.iterdir()
                  if p.is_file() and p.suffix.lower() in VIDEO_EXTS and not p.name.startswith("."))


def safe_name(text):
    """A file-name-friendly version of `text` (letters, digits and dashes)."""
    cleaned = "".join(c if c.isalnum() else "-" for c in str(text)).strip("-")
    return cleaned or "video"


def class_hint(file_name, classes):
    """If a video is named like 'drone_backyard.mp4', the first word is a class hint.

    Returns the matching class name, or None. A hint lets the notebook keep only
    that class's boxes in that video, which removes most wrong pre-labels.
    """
    first = Path(file_name).stem.split("_")[0].lower()
    for name in classes:
        if name.lower() == first:
            return name
    return None


def video_of(frame_name):
    """Which video a frame came from, from its file name."""
    return Path(frame_name).stem.rsplit(SEPARATOR, 1)[0]


def extract_frames(video, out_dir, every_s=1.0, max_frames=None, max_side=1280):
    """Save about one frame every `every_s` seconds. Returns the saved paths in order.

    Frames are shrunk so the longest side is at most `max_side` pixels: plenty
    for training at 640, and it keeps Drive and Colab storage small.
    """
    import cv2

    video = Path(video)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise ValueError(f"Can't open video {video.name}")
    fps = capture.get(cv2.CAP_PROP_FPS)
    if not fps or math.isnan(fps) or fps <= 0:
        fps = 30.0
    step = max(1, round(fps * every_s))
    prefix = safe_name(video.stem)

    saved = []
    index = 0
    try:
        while max_frames is None or len(saved) < max_frames:
            if not capture.grab():
                break
            if index % step == 0:
                ok, frame = capture.retrieve()
                if ok:
                    height, width = frame.shape[:2]
                    scale = max_side / max(height, width)
                    if scale < 1:
                        frame = cv2.resize(frame, (round(width * scale), round(height * scale)),
                                           interpolation=cv2.INTER_AREA)
                    path = out_dir / f"{prefix}{SEPARATOR}{index:06d}.jpg"
                    cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
                    saved.append(path)
            index += 1
    finally:
        capture.release()
    return saved


# ---- Labels -------------------------------------------------------------------------

def format_label(class_id, x1, y1, x2, y2, width, height):
    """One YOLO label line from a pixel box, or None if the box is empty or off-image."""
    x1, x2 = sorted((min(max(x1, 0), width), min(max(x2, 0), width)))
    y1, y2 = sorted((min(max(y1, 0), height), min(max(y2, 0), height)))
    box_w, box_h = x2 - x1, y2 - y1
    if box_w < 2 or box_h < 2:              # under 2 px: a speck of noise, not an object
        return None
    cx, cy = (x1 + x2) / 2 / width, (y1 + y2) / 2 / height
    return f"{int(class_id)} {cx:.6f} {cy:.6f} {box_w / width:.6f} {box_h / height:.6f}"


def parse_label_lines(lines):
    """[(class_id, cx, cy, w, h), ...] from label lines. Skips blank or damaged lines."""
    parsed = []
    for line in lines:
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            class_id = int(parts[0])
            cx, cy, w, h = (float(v) for v in parts[1:])
        except ValueError:
            continue
        if class_id < 0 or not all(0 <= v <= 1 for v in (cx, cy, w, h)) or w == 0 or h == 0:
            continue
        parsed.append((class_id, cx, cy, w, h))
    return parsed


def remap_labels(lines, source_names, classes, aliases=None):
    """Translate label lines from another dataset's class numbering to ours, by NAME.

    Two datasets rarely number their classes the same way. `aliases` lets several
    of their names fold into one of ours, e.g. {"multi-rotor": "drone",
    "military helicopter": "aircraft", "civilian car": None} (None = drop).
    Returns (new_lines, dropped): a line is dropped when its class isn't one of ours.
    """
    ours = {name.lower(): i for i, name in enumerate(classes)}
    for source, target in (aliases or {}).items():
        if target is None:
            ours.pop(source.lower(), None)
        else:
            ours[source.lower()] = classes.index(target)
    dropped_names = {s.lower() for s, t in (aliases or {}).items() if t is None}
    new_lines, dropped = [], 0
    for line in lines:
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            source_id = int(parts[0])
        except ValueError:
            dropped += 1
            continue
        name = source_names[source_id].lower() if 0 <= source_id < len(source_names) else None
        if name in ours and name not in dropped_names:
            new_lines.append(" ".join([str(ours[name])] + parts[1:]))
        else:
            dropped += 1
    return new_lines, dropped


# ---- Train / validation split ---------------------------------------------------------

def split_frames(frame_names, val_fraction=0.2, seed=0, gap=5):
    """Split frames into (train, validation) so the validation score is honest.

    Frames half a second apart in one video are nearly identical. If some went
    to training and their twins to validation, the model would be graded on
    pictures it has practically already seen, and the score would look better
    than the real world will be. So:

    - two or more videos: whole videos go to one side or the other;
    - only one video: the last part of the video is validation, and `gap`
      frames between the two parts are thrown away.
    """
    names = sorted(frame_names)
    if len(names) < 2:
        raise ValueError("Need at least 2 frames to make a validation set.")
    by_video = {}
    for name in names:
        by_video.setdefault(video_of(name), []).append(name)

    if len(by_video) >= 2:
        videos = sorted(by_video)
        random.Random(seed).shuffle(videos)
        count = min(len(videos) - 1, max(1, round(len(videos) * val_fraction)))
        val_videos = set(videos[:count])
        train = [n for n in names if video_of(n) not in val_videos]
        val = [n for n in names if video_of(n) in val_videos]
        return train, val

    count = min(len(names) - 1, max(1, round(len(names) * val_fraction)))
    val = names[-count:]
    train = names[:max(len(names) - count - gap, 1)]
    return train, val


# ---- The dataset folder ------------------------------------------------------------------

class DatasetBuilder:
    """Builds the YOLO folder layout that training reads:

        root/images/train  root/images/val
        root/labels/train  root/labels/val   (one .txt per image)
        root/data.yaml
    """

    SPLITS = ("train", "val")
    SPLIT_ALIASES = {"train": ("train",), "val": ("val", "valid", "validation")}

    def __init__(self, root, classes, fresh=True):
        self.root = Path(root)
        self.classes = list(classes)
        if not self.classes:
            raise ValueError("classes can't be empty")
        if fresh and self.root.exists():
            shutil.rmtree(self.root)     # never train on leftovers from a previous run
        for kind in ("images", "labels"):
            for split in self.SPLITS:
                (self.root / kind / split).mkdir(parents=True, exist_ok=True)

    def add(self, split, image_path, lines, name=None):
        """Copy one image in, with its label lines (an empty list = empty sky)."""
        if split not in self.SPLITS:
            raise ValueError(f"split must be one of {self.SPLITS}")
        image_path = Path(image_path)
        name = name or image_path.name
        target = self.root / "images" / split / name
        if target.exists():
            raise ValueError(f"Duplicate image name in {split}: {name}")
        for class_id, *_ in parse_label_lines(lines):
            if class_id >= len(self.classes):
                raise ValueError(f"{name}: class id {class_id} but only {len(self.classes)} classes")
        shutil.copyfile(image_path, target)
        label = self.root / "labels" / split / (Path(name).stem + ".txt")
        label.write_text("".join(line + "\n" for line in lines))

    def add_existing(self, existing_root, source_names, prefix="ext", aliases=None,
                     limits=None, seed=0, layout="images-first"):
        """Merge an older YOLO dataset, matching classes by name (see remap_labels for aliases).

        `limits` caps how many images to take per split, e.g. {"train": 4000, "val": 500};
        a random but repeatable sample is taken. `layout` is "images-first"
        (root/images/train, root/labels/train) or "split-first" (root/train/images,
        root/train/labels: what Roboflow exports).
        Returns (images_added, labels_dropped). Images are renamed with `prefix`
        so they can't collide with your own frames.
        """
        existing_root = Path(existing_root)
        added = dropped_total = 0
        for split in self.SPLITS:
            found = []
            for alias in self.SPLIT_ALIASES[split]:
                if layout == "split-first":
                    image_dir, label_dir = existing_root / alias / "images", existing_root / alias / "labels"
                else:
                    image_dir, label_dir = existing_root / "images" / alias, existing_root / "labels" / alias
                if image_dir.is_dir():
                    found += [(alias, image, label_dir) for image in sorted(image_dir.iterdir())
                              if image.suffix.lower() in IMAGE_EXTS]
            limit = (limits or {}).get(split)
            if limit is not None and len(found) > limit:
                found = sorted(random.Random(seed).sample(found, limit), key=lambda item: item[1].name)
            for alias, image, label_dir in found:
                label_file = label_dir / (image.stem + ".txt")
                lines = label_file.read_text().splitlines() if label_file.exists() else []
                new_lines, dropped = remap_labels(lines, source_names, self.classes, aliases)
                self.add(split, image, new_lines, name=f"{prefix}{SEPARATOR}{alias}-{image.name}")
                added += 1
                dropped_total += dropped
        return added, dropped_total

    def write_yaml(self):
        """Write data.yaml and return its path."""
        names = "\n".join(f"  {i}: {json.dumps(name)}" for i, name in enumerate(self.classes))
        text = (f"path: {json.dumps(str(self.root.resolve()))}\n"
                "train: images/train\nval: images/val\n"
                f"names:\n{names}\n")
        path = self.root / "data.yaml"
        path.write_text(text)
        return path

    def summary(self):
        """{'train': {'images': n, 'empty': n, 'instances': {class: n}}, 'val': {...}}"""
        result = {}
        for split in self.SPLITS:
            images = [p for p in (self.root / "images" / split).iterdir() if p.is_file()]
            counts = {name: 0 for name in self.classes}
            empty = 0
            for image in images:
                label = self.root / "labels" / split / (image.stem + ".txt")
                parsed = parse_label_lines(label.read_text().splitlines()) if label.exists() else []
                if not parsed:
                    empty += 1
                for class_id, *_ in parsed:
                    if class_id < len(self.classes):
                        counts[self.classes[class_id]] += 1
            result[split] = {"images": len(images), "empty": empty, "instances": counts}
        return result


def dataset_warnings(summary, min_val_images=10):
    """Plain-English problems to fix before spending GPU time on training."""
    warnings = []
    if summary["train"]["images"] == 0:
        warnings.append("There are no training images.")
    if summary["val"]["images"] < min_val_images:
        warnings.append(f"Only {summary['val']['images']} validation images. The score will be a "
                        "rough guess; add more videos for a trustworthy number.")
    for name, count in summary["train"]["instances"].items():
        if count == 0:
            warnings.append(f"No '{name}' boxes in training: the model can't learn it.")
        elif count < 50:
            warnings.append(f"Only {count} '{name}' boxes in training (aim for hundreds).")
    for name, count in summary["val"]["instances"].items():
        if count == 0 and summary["train"]["instances"].get(name, 0) > 0:
            warnings.append(f"No '{name}' boxes in validation, so its score can't be measured.")
    return warnings


# ---- Checking labels by eye ---------------------------------------------------------------

_BOX_COLORS = [(46, 77, 255), (240, 211, 143), (155, 232, 155), (200, 200, 200), (90, 190, 255)]


def draw_preview(image_path, lines, classes, cell_width=220, caption=None):
    """The image with its boxes drawn on, shrunk to `cell_width` wide, for a contact sheet."""
    import cv2

    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Can't read {image_path}")
    height, width = image.shape[:2]
    for class_id, cx, cy, w, h in parse_label_lines(lines):
        color = _BOX_COLORS[class_id % len(_BOX_COLORS)]     # (blue, green, red)
        x1, y1 = round((cx - w / 2) * width), round((cy - h / 2) * height)
        x2, y2 = round((cx + w / 2) * width), round((cy + h / 2) * height)
        thickness = max(2, round(width / 400))
        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)
        label = classes[class_id] if class_id < len(classes) else f"class{class_id}"
        cv2.putText(image, label, (x1, max(y1 - 6, 14)), cv2.FONT_HERSHEY_SIMPLEX,
                    max(0.5, width / 1400), color, 2, cv2.LINE_AA)
    scale = cell_width / width
    image = cv2.resize(image, (cell_width, max(1, round(height * scale))), interpolation=cv2.INTER_AREA)
    if caption:
        cv2.rectangle(image, (0, 0), (8 + 11 * len(caption), 22), (0, 0, 0), -1)
        cv2.putText(image, caption, (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return image


def make_contact_sheet(previews, columns=6, background=18):
    """Tile preview images into one big picture (cells are padded to the biggest)."""
    import numpy as np

    if not previews:
        raise ValueError("No previews to tile")
    cell_h = max(p.shape[0] for p in previews)
    cell_w = max(p.shape[1] for p in previews)
    rows = math.ceil(len(previews) / columns)
    sheet = np.full((rows * cell_h, columns * cell_w, 3), background, dtype=np.uint8)
    for i, preview in enumerate(previews):
        r, c = divmod(i, columns)
        sheet[r * cell_h:r * cell_h + preview.shape[0], c * cell_w:c * cell_w + preview.shape[1]] = preview
    return sheet
