"""The training script that runs ON Kaggle's free GPU. run_pipeline.py pushes it there.

Not meant to be run by hand. It expects one Kaggle dataset, attached by the pipeline:

    clips/             the new phone clips
    current.pt         the model to start from
    used_clips.json    the clips already trained on (may be missing the first time)

It runs training/auto_train.py's real training function on those, then writes what the
pipeline collects into /kaggle/working/out:

    report.json        what happened (also written, as an error, if training crashed)
    used_clips.json    updated list of used clips
    skynode-auto-*.onnx and current.pt   only if the new model was good enough to keep

A crash re-raises, so Kaggle marks the run as failed and the pipeline says so.
"""
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

REPO = os.environ.get("SKYNODE_REPO", "https://github.com/bsalsa2/Skynode")
EPOCHS = int(os.environ.get("SKYNODE_EPOCHS", "25"))
WORK = Path("/kaggle/working")
OUT = WORK / "out"


def find_dataset(root=Path("/kaggle/input")):
    """The attached dataset's folder: the one that contains clips/."""
    for folder in sorted(root.glob("*")) + sorted(root.glob("*/*")):
        if (folder / "clips").is_dir():
            return folder
    raise SystemExit(f"No dataset with a clips/ folder under {root}.")


def prepare_project(dataset, project):
    """Lay the dataset out the way auto_train.py expects its project folder."""
    (project / "phone_videos").mkdir(parents=True)
    (project / "models").mkdir()
    for clip in sorted((dataset / "clips").iterdir()):
        if clip.is_file():
            shutil.copy2(clip, project / "phone_videos" / clip.name)
    shutil.copy2(dataset / "current.pt", project / "models" / "current.pt")
    used = dataset / "used_clips.json"
    if used.is_file():
        shutil.copy2(used, project / "used_clips.json")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        try:
            import ultralytics  # noqa: F401  Kaggle images usually include it
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "ultralytics"], check=True)
        subprocess.run(["git", "clone", "-q", "--depth", "1", REPO, str(WORK / "Skynode")], check=True)
        sys.path.insert(0, str(WORK / "Skynode" / "training"))
        import auto_train as at

        project = WORK / "project"
        prepare_project(find_dataset(), project)
        clips = at.new_clips(project)
        print(json.dumps(at.run_plan(project, clips), indent=1))
        if not clips:
            report = {"status": "no new clips"}
        else:
            report = at.train_once(project, clips, review=False, epochs=EPOCHS)
        if report.get("status") == "promoted":
            shutil.copy2(report["new_weights"], OUT / "current.pt")
            if report.get("onnx"):
                shutil.copy2(report["onnx"], OUT / Path(report["onnx"]).name)
        if (project / "used_clips.json").is_file():
            shutil.copy2(project / "used_clips.json", OUT / "used_clips.json")
        (OUT / "report.json").write_text(json.dumps(report, indent=1, default=str))
        print(json.dumps(report, indent=1, default=str))
    except BaseException:
        (OUT / "report.json").write_text(json.dumps(
            {"status": "error", "detail": traceback.format_exc()[-4000:]}, indent=1))
        raise


if __name__ == "__main__":
    main()
