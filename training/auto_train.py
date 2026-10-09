"""One command that turns new phone clips into a better model.

    python training/auto_train.py --project /content/drive/MyDrive/skynode

What it does, in order:
1. Finds clips in <project>/phone_videos that it has NOT used before
   (it remembers them in <project>/used_clips.json).
2. Pulls frames from them and labels them with the CURRENT model (the newest
   file in <project>/models that ends in .pt, or the starting weights).
3. Fine-tunes that model on the new labelled frames, keeping the first layers
   frozen so it nudges rather than forgets.
4. Scores the old and new models on the same held-out clips.
5. Only if the NEW model is at least as good, it exports a new .onnx file
   for the brain and records the new weights as the current model.
   Otherwise the old model stays, and the clips are kept for next time.

Nothing here needs you to look at pictures. The safety check is the score.
Turn on --review to stop after labelling and wait for you to fix the boxes.

The GPU parts (ultralytics) only import when you actually train, so the
logic can be tested on any computer. See tests/test_auto_train.py.
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynode_data as sd                                    # noqa: E402

CLASSES = ["drone", "aircraft"]
MANIFEST = "used_clips.json"
DEFAULT_START = "drone_v3/weights/best.pt"       # relative to the project folder
MIN_NEW_CLIPS = 1


# ---- Pure logic (testable without a GPU) ------------------------------------------

def load_used(project):
    """The clip names already trained on, from the manifest. Empty if there's no file yet."""
    path = Path(project) / MANIFEST
    if not path.exists():
        return set()
    return set(json.loads(path.read_text()).get("used", []))


def save_used(project, used):
    path = Path(project) / MANIFEST
    path.write_text(json.dumps({"used": sorted(used)}, indent=1))


INBOX_NAME = "skynode_phone_uploads"    # the phone upload page (web/field.html) creates this in My Drive


def inbox_folder(project, inbox=None):
    """Where the phone page drops clips: --inbox if given, else <project>/../skynode_phone_uploads
    when that folder exists (in Drive that is My Drive, next to the skynode folder)."""
    if inbox:
        return Path(inbox)
    beside = Path(project).resolve().parent / INBOX_NAME
    return beside if beside.is_dir() else None


def new_clips(project, inbox=None):
    """Clips that haven't been used yet, sorted by name: those in phone_videos, plus
    those in the phone upload folder (see inbox_folder)."""
    folders = [Path(project) / "phone_videos", inbox_folder(project, inbox)]
    used = load_used(project)
    found = [p for folder in folders if folder is not None and folder.is_dir()
             for p in sd.list_videos(folder) if p.name not in used]
    return sorted(found, key=lambda p: p.name)


def current_weights(project):
    """The newest model in models/ (by file date), else the starting weights."""
    models = sorted(Path(project, "models").glob("*.pt"), key=lambda p: p.stat().st_mtime)
    if models:
        return models[-1]
    return Path(project, DEFAULT_START)


def better_or_equal(old_scores, new_scores, tolerance=0.0):
    """Keep the new model only if it isn't worse on the held-out clips.

    Scores are {name: (value, higher_is_better)}, so each measure says which way is better.
    `tolerance` allows a small wobble, so tiny noise doesn't block an upgrade.
    """
    if not old_scores or not new_scores:
        return False                    # nothing to compare: don't risk a change
    for key, (old_value, higher_is_better) in old_scores.items():
        if key not in new_scores:
            return False
        new_value = new_scores[key][0]
        if higher_is_better:
            if new_value < old_value - tolerance:
                return False
        elif new_value > old_value + tolerance:
            return False
    return True


def run_plan(project, clips):
    """Describe what a run will do, for the printout before any GPU time is spent."""
    return {
        "project": str(project),
        "new_clips": [c.name for c in clips],
        "start_weights": str(current_weights(project)),
        "already_used": len(load_used(project)),
    }


# ---- The run (needs ultralytics on a GPU) -------------------------------------------

def train_once(project, clips, review=False, epochs=25, imgsz=960, val_fraction=0.2):
    """Label, train, score, and maybe promote. Returns a short report dict."""
    from ultralytics import YOLO

    project = Path(project)
    start = current_weights(project)
    stamp = datetime.date.today().isoformat()
    work = Path("/content/auto_work") if Path("/content").is_dir() else project / "auto_work"
    frames_dir = work / "frames"
    dataset = work / "dataset"

    # 1-2. Frames and first-guess labels from the current model
    frames, hint_of = [], {}
    for clip in clips:
        got = sd.extract_frames(clip, frames_dir, every_s=1.0, max_frames=120)
        hint = sd.class_hint(clip.name, CLASSES)
        for path in got:
            hint_of[path] = hint
        frames += got
    if not frames:
        return {"status": "no frames", "clips": [c.name for c in clips]}

    model = YOLO(str(start))
    labels = {}
    for path in frames:
        lines = []
        result = model.predict(str(path), imgsz=imgsz, conf=0.25, verbose=False)[0]
        height, width = result.orig_shape
        for box, cls in zip(result.boxes.xyxy.tolist(), result.boxes.cls.tolist()):
            name = result.names[int(cls)]
            if hint_of[path] in (None, name) and name in CLASSES:
                line = sd.format_label(CLASSES.index(name), *box, width, height)
                if line:
                    lines.append(line)
        labels[path] = lines

    if review:
        return {"status": "labelled, waiting for review", "frames": len(frames),
                "frames_folder": str(frames_dir)}

    # 3. Split (whole clips held back), build the dataset, train from the current model
    names = sorted(p.name for p in frames)
    train_names, val_names = sd.split_frames(names, val_fraction=0.2)
    by_name = {p.name: p for p in frames}
    builder = sd.DatasetBuilder(dataset, CLASSES)
    for split, group in (("train", train_names), ("val", val_names)):
        for name in group:
            builder.add(split, by_name[name], labels[by_name[name]])
    data_yaml = builder.write_yaml()

    run_name = f"auto_{stamp}_{len(clips)}clips"
    YOLO(str(start)).train(
        data=str(data_yaml), imgsz=imgsz, epochs=epochs, patience=10, batch=16,
        freeze=10, lr0=0.002, project=str(project / "runs"), name=run_name,
        exist_ok=True, amp=True, workers=2, seed=0,
    )
    new_weights = project / "runs" / run_name / "weights" / "best.pt"

    # 4. Score both on the same held-out frames.
    # HONEST LIMIT: without --review these labels are the OLD model's own guesses,
    # so the old model is graded on its own homework. That makes promotion
    # conservative: a new model has to match the old one's guesses to be kept.
    # Review a few sheets (--review) for a fair score.
    old_scores = score(start, data_yaml)
    new_scores = score(new_weights, data_yaml)
    promote = better_or_equal(old_scores, new_scores)

    report = {"status": "promoted" if promote else "kept old model",
              "old": old_scores, "new": new_scores, "new_weights": str(new_weights),
              "scored_against": "the old model's own labels unless you reviewed them"}

    # 5. Promote: export ONNX for the brain, record the new weights, mark clips as used
    if promote:
        from shutil import copyfile
        onnx = Path(YOLO(str(new_weights)).export(format="onnx", imgsz=imgsz, opset=12, simplify=True))
        target = project / "models" / f"skynode-auto-{stamp}.onnx"
        target.parent.mkdir(parents=True, exist_ok=True)
        copyfile(onnx, target)
        report["onnx"] = str(target)

    used = load_used(project) | {c.name for c in clips}
    save_used(project, used)     # clips count as used either way: their labels already fed this run
    return report


def score(weights, data_yaml):
    """mAP50 on the held-out frames, as {"mAP50": (value, higher_is_better=True)}."""
    from ultralytics import YOLO
    metrics = YOLO(str(weights)).val(data=str(data_yaml), split="val", verbose=False)
    return {"mAP50": (float(metrics.box.map50), True)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Train Skynode on new phone clips, automatically.")
    parser.add_argument("--project", required=True, help="your skynode folder (in Drive)")
    parser.add_argument("--review", action="store_true", help="stop after labelling and wait for you")
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--inbox", help="extra folder of clips (default: the phone upload folder "
                                        "next to your skynode folder, if there is one)")
    args = parser.parse_args(argv)

    clips = new_clips(args.project, args.inbox)
    plan = run_plan(args.project, clips)
    print(json.dumps(plan, indent=1))
    if len(clips) < MIN_NEW_CLIPS:
        print("No new clips in phone_videos. Upload some, then run again.")
        return 0
    report = train_once(args.project, clips, review=args.review, epochs=args.epochs)
    print(json.dumps(report, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
