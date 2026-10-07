# training/

Train Skynode's own aircraft and drone detector in **Google Colab**, using videos you film on your phone. Everything heavy happens on Google's computers: nothing is stored or run on your laptop.

| File | What it is |
|---|---|
| `skynode_train.ipynb` | The Colab notebook. Open it in Colab and run the cells top to bottom |
| `skynode_v4_export_and_phone_finetune.ipynb` | Fits the existing `skynode/` Drive folder: export v3, then fine-tune on phone video |
| `skynode_data.py` | The bookkeeping the notebook uses (frames, labels, the train/validation split, the dataset folder). Tested in `tests/test_training_data.py` |

## Automatic: `skynode_auto_train.ipynb` (start here)

One notebook, one Run. Put clips in **phone_videos**, run it, and it retrains on only the new clips. It replaces the model only when the new one scores at least as well. Full details are in the notebook. The logic lives in `training/auto_train.py` and is tested in `tests/test_auto_train.py`.

## If you already have a trained model: `skynode_v4_export_and_phone_finetune.ipynb`

This is the notebook that matches the existing `skynode/` Drive folder (classes `drone` and `aircraft`, 960 px, `drone_v3/weights/best.pt`). It leaves the v3 notebook and run untouched and:

1. **exports v3 to ONNX** for `brain/detector.py` (a 2-minute job, runs on its own);
2. scores v3 on your phone videos (false-drone rate on aircraft clips and so on);
3. uses v3 itself to draw first-guess boxes, which you check on contact sheets;
4. fine-tunes v3 into **v4** with the backbone frozen, mixing in a sample of the Roboflow dataset so it doesn't forget;
5. compares v3 and v4 on phone clips the model never trained on, then exports v4.

Put clips in **Drive ▸ skynode ▸ phone_videos**, named `drone_*.mp4`, `aircraft_*.mp4` or `sky_*.mp4`. Your Roboflow key stays in Colab's Secrets (`ROBOFLOW_API_KEY`), never in a cell.

`skynode_train.ipynb` below is the from-scratch version for a fresh Drive.

## Quick start

1. Upload your phone videos to Google Drive in **My Drive ▸ skynode ▸ videos**.
   Name a video after what it shows when it shows only one thing: `drone_garden.mp4`, `airplane_morning.mp4`. The word before the first `_` tells the notebook to keep only that class's boxes. Mixed or empty-sky clips can have any other name (`sky_clear.mp4`).
2. Open `skynode_train.ipynb` in Colab (on GitHub, open the file and use the Colab link, or go to colab.research.google.com ▸ GitHub and paste the repo address). Set **Runtime ▸ Change runtime type ▸ T4 GPU**.
3. Run the cells in order. At the end you get an `.onnx` file in **Drive ▸ skynode ▸ models** (it also downloads).
4. Copy it to `brain/models/`, set `[model] path` and `target_classes` in `brain/config.toml` (the last cell prints the exact lines), and test on a video the model never saw: `python -m brain.run --source some_video.mp4`.

## How it works, and where it can go wrong

1. **Frames:** about one per second of video, shrunk to at most 1280 px on the long side.
2. **First-guess labels:** a ready-made COCO model draws boxes for planes and birds; YOLO-World, which finds things by name, tries for drones. These are guesses.
3. **You check the labels.** The notebook shows contact sheets with numbered boxes; you list frames to `DROP` or `WIPE`. Auto-labels can miss small, distant drones, and a missing box on a real drone teaches the model to ignore drones. This step decides how good the result is.
4. **Honest grading:** with two or more videos, whole videos are held back for validation. Frames from one video are near-duplicates, so mixing them would make the score look better than the real world will be. With a single video, the last 20% is held back.
5. **Train** a small YOLOv8n starting from the COCO weights, saving a checkpoint to Drive every epoch. If Colab disconnects, run the cells again and training resumes.
6. **Export** to ONNX in the same format `brain/detector.py` already reads (class names are stored in the file).

The notebook warns you before training if a class has no (or very few) boxes, or if validation is too small to trust. Heed those: with only 2 or 3 videos the split can leave a class entirely on one side.

## What the scores mean

`mAP50` is measured on your held-out footage, so it describes how the model does on *your* kind of sky. It is not a general accuracy figure. To publish accuracy numbers, compare logged sightings against ADS-B flight data (see `brain/README.md`) rather than quoting this score.

## Adding an older dataset

If you already have a labeled YOLO dataset (an `images/` and `labels/` folder plus a `data.yaml` with class names), put it in Drive and set `EXISTING_DATASET` in the Settings cell. Classes are matched **by name**, so differently numbered datasets merge correctly, and classes you don't use are ignored.

## Limits to know about

- Colab's free GPU time is limited and sessions end after a while. The notebook saves to Drive for this reason.
- Videos still syncing to Drive from your phone can look empty or cut short. Wait until the upload finishes.
- YOLO-World may be slow to download the first time.
- I wrote and tested the notebook's bookkeeping on a laptop, but the GPU cells (auto-labeling, training, export) had not been run in Colab when this was written. If a cell errors, the error message is the thing to bring back.
