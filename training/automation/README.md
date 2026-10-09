# Automatic training (free)

Drop a phone clip into your Google Drive and, within about half an hour, a free Kaggle GPU trains on it and the result appears as a GitHub pre-release. Nothing runs on your computer. Everything here is on a free tier (GitHub Actions on a public repo, a Kaggle notebook, a Google service account).

```
Drive clip folders ──read-only──▶ GitHub Actions (every 30 min) ──▶ private Kaggle dataset
                                                                          │
GitHub pre-release  ◀── model + report ◀── Kaggle free GPU trains ◀───────┘
```

**It never changes your node.** A trained model is published as a *pre-release*. You copy the `.onnx` file across yourself, after looking at the report.

**Read this before trusting a result.** Unattended runs label the clips with the *old* model's own guesses and then score the new model against those same guesses (see `auto_train.py`). A new model is only kept if it is no worse than the old one by that test, which is cautious, but it can't catch a mistake the old model already made. For a fair score, label a few frames by hand (`--review`).

## Files

| File | Runs where | Does |
|---|---|---|
| `drive_watch.py` | GitHub | Lists and downloads clips from Drive, read-only |
| `run_pipeline.py` | GitHub | The watcher: new clips? start Kaggle, wait, publish |
| `kaggle_train.py` | Kaggle | Runs the real training (`auto_train.py`) on the GPU |
| `.github/workflows/auto-train.yml` | GitHub | The schedule and the "Run workflow" button |

## One-time setup (all in a browser)

**1. Kaggle** (free)
1. Make an account at kaggle.com and **verify your phone** (Kaggle needs this before it gives a GPU or internet in notebooks).
2. Profile ▸ **Settings ▸ API ▸ Create New Token**. It downloads `kaggle.json` holding your username and key.

**2. Google service account** (free)
1. In the same Google Cloud project you used for sign-in (or a new one): **APIs & Services ▸ Library ▸ Google Drive API** is already enabled.
2. **IAM & Admin ▸ Service Accounts ▸ Create service account**, named `skynode-reader`. No roles needed.
3. Open it ▸ **Keys ▸ Add key ▸ Create new key ▸ JSON**. A file downloads. Treat it like a password.
4. Copy the service account's e-mail address (`skynode-reader@…iam.gserviceaccount.com`).
5. In Drive, **share with that e-mail as Viewer**: your `phone_videos` folder, your `skynode_phone_uploads` folder if you use the phone page, and the starting-model file (`drone_v3/weights/best.pt`). Nothing else.

**3. GitHub** (repository ▸ Settings ▸ Secrets and variables ▸ Actions)

*Secrets* (never paste these into a chat):

| Name | Value |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | the whole text of the downloaded JSON key file |
| `KAGGLE_USERNAME` | `username` from `kaggle.json` |
| `KAGGLE_KEY` | `key` from `kaggle.json` |

*Variables*:

| Name | Value |
|---|---|
| `DRIVE_CLIP_FOLDER_IDS` | the Drive folder ids, comma separated (the id is the end of the folder's address) |
| `DRIVE_START_WEIGHTS_FILE_ID` | the id of `best.pt`, used for the very first run |
| `AUTO_TRAIN_ENABLED` | leave unset until the dry run looks right, then `true` |

## Trying it

1. **Actions ▸ Auto train ▸ Run workflow**, leave *dry run* ticked. It lists your Drive clips and says which are new. Nothing is copied or started.
2. Untick *dry run* and run again to do one real run by hand. Watch the log: Kaggle can take a while to start.
3. When you're happy, set `AUTO_TRAIN_ENABLED` to `true`. After that it checks every 30 minutes by itself. (Scheduled runs only start once this workflow is on the default branch.)

## Good to know

- **Clips are read from the folders directly, not from subfolders** (as `auto_train.py` does). A clip is remembered by its file name.
- **A failed run pauses retries for a day**, so a broken setup can't burn your GPU allowance. To retry sooner, delete `last_failure.json` from the `training-state` release.
- **Kaggle's free GPU has a weekly allowance** and can queue. Check Kaggle for the current numbers.
- **Where things are kept:** `training-state` release (which clips are used), `current-model` release (the weights the next run starts from), and one `model-<date>` pre-release per run with the `.onnx` and a `report.json`.
- **Cost:** nothing. If a free tier changes, this is the part to revisit.
