"""The watcher: notice new clips in Drive, train on Kaggle's free GPU, publish the result.

Runs on GitHub Actions (.github/workflows/auto-train.yml), every half hour and on demand.

    1. Look in your Drive clip folders (read-only) for clips not trained on yet.
    2. If there are some: copy them, plus the model to start from, into a private
       Kaggle dataset, and run training/automation/kaggle_train.py on a free Kaggle GPU.
    3. Collect the result and publish it as a GitHub *pre-release* (the .onnx model and
       a report). It never touches your node: you copy a model across yourself.

State lives in two small GitHub releases, so nothing needs a database:
    training-state   used_clips.json (which clips are already trained on) and last_failure.json
    current-model    current.pt, the weights the next run starts from

    python training/automation/run_pipeline.py --dry-run     # look and report, change nothing

Needs, as GitHub secrets: GOOGLE_SERVICE_ACCOUNT_JSON, KAGGLE_USERNAME, KAGGLE_KEY, and as
GitHub variables: DRIVE_CLIP_FOLDER_IDS, DRIVE_START_WEIGHTS_FILE_ID. If any is missing
it says which and stops without an error, so a half-set-up repo never goes red.
Setup is in training/automation/README.md.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import drive_watch as dw  # noqa: E402

DATASET_SLUG = "skynode-train-input"
KERNEL_SLUG = "skynode-train"
STATE_TAG, MODEL_TAG = "training-state", "current-model"
USED_FILE, FAILURE_FILE, WEIGHTS_FILE = "used_clips.json", "last_failure.json", "current.pt"
MAX_BATCH_BYTES = 2 * 1024 ** 3        # clips copied to Kaggle per run; the rest wait for the next
RETRY_AFTER = timedelta(hours=24)      # after a failed run, wait this long (don't burn the GPU quota)
KAGGLE_WAIT_S = 5 * 3600
DATASET_WAIT_S = 20 * 60
POLL_S = 60
REQUIRED_SECRETS = ("GOOGLE_SERVICE_ACCOUNT_JSON", "KAGGLE_USERNAME", "KAGGLE_KEY")
REQUIRED_VARIABLES = ("DRIVE_CLIP_FOLDER_IDS", "DRIVE_START_WEIGHTS_FILE_ID")
FAILED = ("ERROR", "CANCEL_REQUESTED", "CANCEL_ACKNOWLEDGED")
STATE_NOTES = "Which clips are already trained on. Managed by the auto-train pipeline: don't edit."


class NotConfigured(Exception):
    """Something the pipeline needs is not set up yet (the message says what)."""


def read_config(environ):
    missing = [name for name in REQUIRED_SECRETS + REQUIRED_VARIABLES if not environ.get(name, "").strip()]
    if missing:
        raise NotConfigured("Not set up yet, so nothing was done. Missing: " + ", ".join(missing)
                            + ". See training/automation/README.md.")
    folders = [part for part in re.split(r"[,\s]+", environ["DRIVE_CLIP_FOLDER_IDS"].strip()) if part]
    for folder in folders:
        dw.check_id(folder, "folder id")
    return {
        "key_json": environ["GOOGLE_SERVICE_ACCOUNT_JSON"],
        "user": environ["KAGGLE_USERNAME"].strip(),
        "folders": folders,
        "weights_id": dw.check_id(environ["DRIVE_START_WEIGHTS_FILE_ID"].strip(), "weights file id"),
    }


# ---- Pure logic (tested without any network) -------------------------------------------

def pick_new(clips, used, cap=MAX_BATCH_BYTES):
    """(clips to train on now, clips left for later): not used yet, in name order, within `cap` bytes.
    The first clip is always taken, so one huge clip can't block the queue."""
    fresh = [c for c in clips if c["name"] not in used]
    now, total = [], 0
    for index, clip in enumerate(fresh):
        if now and total + clip["size"] > cap:
            return now, fresh[index:]
        now.append(clip)
        total += clip["size"]
    return now, []


def parse_status(text):
    """'user/x has status "KernelWorkerStatus.COMPLETE"' -> 'COMPLETE' (or UNKNOWN)."""
    match = re.search(r'status\s+"?(?:KernelWorkerStatus\.)?([A-Za-z_]+)"?', str(text))
    return match.group(1).upper() if match else "UNKNOWN"


def recently_failed(failure_text, now):
    """True if last_failure.json says a run failed less than RETRY_AFTER ago."""
    try:
        when = datetime.fromisoformat(json.loads(failure_text)["time"])
    except (TypeError, ValueError, KeyError):
        return False
    return now - when < RETRY_AFTER


def dataset_metadata(user):
    return {"title": "skynode train input", "id": f"{user}/{DATASET_SLUG}",
            "licenses": [{"name": "CC0-1.0"}]}


def kernel_metadata(user):
    return {"id": f"{user}/{KERNEL_SLUG}", "title": "skynode train", "code_file": "kaggle_train.py",
            "language": "python", "kernel_type": "script", "is_private": True,
            "enable_gpu": True, "enable_internet": True, "enable_tpu": False,
            "dataset_sources": [f"{user}/{DATASET_SLUG}"], "competition_sources": [], "kernel_sources": []}


def run_summary(report):
    """One readable line for a release page."""
    status = report.get("status", "unknown")
    scores = report.get("new") or {}
    value = scores.get("mAP50", [None])[0] if isinstance(scores.get("mAP50"), (list, tuple)) else None
    return status + (f", mAP50 {value:.3f}" if isinstance(value, (int, float)) else "")


# ---- Talking to Kaggle and GitHub (thin wrappers; checked by real runs) --------------------

def sh(command, cwd=None, check=True):
    """Run a command (a list, never a shell string) and return its output."""
    done = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if check and done.returncode != 0:
        raise RuntimeError(f"{' '.join(command[:3])} failed ({done.returncode}): "
                           f"{(done.stderr or done.stdout).strip()[-1500:]}")
    return (done.stdout or "") + (done.stderr or "")


def gh(args, check=True):
    return sh(["gh", *args, "--repo", os.environ["GITHUB_REPOSITORY"]], check=check)


def download_asset(tag, name, folder):
    """Save one release asset into `folder`. True if it was there, False if the release or file isn't yet."""
    try:
        gh(["release", "download", tag, "--pattern", name, "--dir", str(folder), "--clobber"])
    except RuntimeError:
        return False
    return (Path(folder) / name).is_file()


def read_state_file(tag, name, folder):
    """The text of a small release asset, or '' if it isn't there yet."""
    return (Path(folder) / name).read_text() if download_asset(tag, name, folder) else ""


def ensure_release(tag, title, notes):
    viewed = subprocess.run(["gh", "release", "view", tag, "--repo", os.environ["GITHUB_REPOSITORY"]],
                            capture_output=True, text=True)
    if viewed.returncode == 0:
        return
    try:
        gh(["release", "create", tag, "--title", title, "--notes", notes, "--prerelease"])
    except RuntimeError:
        gh(["release", "view", tag])        # made by a run that overlapped ours: fine


def upload(tag, title, notes, files):
    ensure_release(tag, title, notes)
    gh(["release", "upload", tag, *[str(f) for f in files], "--clobber"])


def dataset_exists(user):
    """Does our private Kaggle dataset exist yet? Asked before uploading, because a missing one can
    come back as 404 or as 403, and by then a gigabyte would already have been sent."""
    reply = sh(["kaggle", "datasets", "status", f"{user}/{DATASET_SLUG}"], check=False).lower()
    missing = any(word in reply for word in ("404", "403", "forbidden", "not found"))
    return bool(reply.strip()) and not missing


def publish_dataset(user, folder):
    """Create the private Kaggle dataset the first time, add a new version afterwards."""
    (Path(folder) / "dataset-metadata.json").write_text(json.dumps(dataset_metadata(user)))
    if dataset_exists(user):
        sh(["kaggle", "datasets", "version", "-p", str(folder), "-m", "new clips", "--dir-mode", "zip"])
    else:
        sh(["kaggle", "datasets", "create", "-p", str(folder), "--dir-mode", "zip"])


def wait_until(check, limit_s, what):
    deadline = time.time() + limit_s
    while time.time() < deadline:
        result = check()
        if result:
            return result
        time.sleep(POLL_S)
    raise RuntimeError(f"Timed out waiting for {what}.")


def wait_for_dataset(user):
    ref = f"{user}/{DATASET_SLUG}"
    wait_until(lambda: "ready" in sh(["kaggle", "datasets", "status", ref], check=False).lower(),
               DATASET_WAIT_S, "the Kaggle dataset to be ready")


def run_kernel(user, folder):
    """Push the training script, wait for it, and return the folder holding its output."""
    folder = Path(folder)
    (folder / "kernel-metadata.json").write_text(json.dumps(kernel_metadata(user), indent=1))
    shutil.copy2(HERE / "kaggle_train.py", folder / "kaggle_train.py")
    ref = f"{user}/{KERNEL_SLUG}"
    sh(["kaggle", "kernels", "push", "-p", str(folder)])

    def finished():
        status = parse_status(sh(["kaggle", "kernels", "status", ref], check=False))
        print(f"  Kaggle: {status}", flush=True)
        if status == "COMPLETE":
            return "COMPLETE"
        if status in FAILED:
            return status
        return None
    status = wait_until(finished, KAGGLE_WAIT_S, "training on Kaggle")
    output = Path(tempfile.mkdtemp(prefix="kaggle-out-"))
    sh(["kaggle", "kernels", "output", ref, "-p", str(output)], check=False)
    if status != "COMPLETE":
        report = next(iter(output.rglob("report.json")), None)
        detail = report.read_text()[-1500:] if report else "no report was produced"
        raise RuntimeError(f"Kaggle run ended as {status}: {detail}")
    return output


# ---- The run -------------------------------------------------------------------------------

def main(argv=None, environ=None):
    parser = argparse.ArgumentParser(description="Train on Kaggle when there are new Drive clips.")
    parser.add_argument("--dry-run", action="store_true", help="look and report; change nothing")
    parser.add_argument("--force", action="store_true",
                        help="go ahead even if a run failed less than a day ago (for runs started by hand)")
    args = parser.parse_args(argv)
    environ = os.environ if environ is None else environ
    try:
        config = read_config(environ)
    except NotConfigured as error:
        print(error)
        return 0

    state = Path(tempfile.mkdtemp(prefix="state-"))
    service = dw.drive_service(config["key_json"])
    clips = dw.list_clips(service, config["folders"])
    used = set(json.loads(read_state_file(STATE_TAG, USED_FILE, state) or '{"used": []}').get("used", []))
    batch, later = pick_new(clips, used)
    print(f"Drive has {len(clips)} clips; {len(used)} already trained on; "
          f"{len(batch)} new now, {len(later)} waiting for a later run.")
    for clip in batch:
        print(f"  new: {clip['name']} ({clip['size'] / 1e6:.1f} MB)")
    if not batch:
        return 0
    if not args.force and recently_failed(read_state_file(STATE_TAG, FAILURE_FILE, state),
                                          datetime.now(timezone.utc)):
        print("A run failed less than a day ago, so it is not retrying yet. "
              "Delete last_failure.json from the training-state release to retry now.")
        return 0
    if args.dry_run:
        print("Look-only run: stopping here. Nothing was copied or started. "
              "To train for real, run the workflow again with 'train_for_real' ticked.")
        return 0

    try:
        stage = Path(tempfile.mkdtemp(prefix="stage-"))
        for clip in batch:
            print(f"Downloading {clip['name']}…", flush=True)
            dw.download(service, clip["id"], stage / "clips" / clip["name"])
        if not download_asset(MODEL_TAG, WEIGHTS_FILE, stage):
            print("No trained model saved yet: starting from the weights in Drive.")
            dw.download(service, config["weights_id"], stage / WEIGHTS_FILE)
        (stage / USED_FILE).write_text(json.dumps({"used": sorted(used)}))
        publish_dataset(config["user"], stage)
        wait_for_dataset(config["user"])
        output = run_kernel(config["user"], tempfile.mkdtemp(prefix="kernel-"))
    except Exception as error:
        try:        # remember the failure, so the next half hour doesn't try (and burn GPU quota) again
            marker = state / FAILURE_FILE
            marker.write_text(json.dumps({"time": datetime.now(timezone.utc).isoformat(),
                                          "error": str(error)[-1500:]}))
            upload(STATE_TAG, "Training state", STATE_NOTES, [marker])
        except Exception as note_error:
            print(f"Could not record the failure: {note_error}")
        raise

    report_path = next(output.rglob("report.json"), None)
    report = json.loads(report_path.read_text()) if report_path else {"status": "no report"}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    files = [p for p in output.rglob("*") if p.is_file() and (p.suffix == ".onnx" or p.name == "report.json")]
    upload(f"model-{stamp}", f"Training run {stamp}: {run_summary(report)}",
           f"{len(batch)} new clips. Automatic run on a free Kaggle GPU, scored against the old model's own "
           "labels (see training/auto_train.py). Review it before using it on the node: copy the .onnx "
           "yourself.", files)
    weights = next(output.rglob(WEIGHTS_FILE), None)       # only there if the new model was kept
    if weights:
        upload(MODEL_TAG, "Current model weights", "The weights the next automatic run starts from.", [weights])
    new_used = next(output.rglob(USED_FILE), None)
    if new_used:
        upload(STATE_TAG, "Training state", STATE_NOTES, [new_used])
    print("Done:", run_summary(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
