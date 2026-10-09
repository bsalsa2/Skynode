"""Read-only look at the Drive folders that hold your phone clips.

Used by run_pipeline.py on GitHub Actions. It signs in as a Google *service account*,
which can see only what you shared with its e-mail address, so share just the clip
folders (and the starting model) with it, as Viewer. It asks Google for the read-only
scope as well, so it could not change anything even if the sharing were wider.

The Google libraries are imported only when a connection is made, so the logic here
(and its tests) work without them.
"""
import json
import re
from pathlib import Path

SCOPE = "https://www.googleapis.com/auth/drive.readonly"
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}     # as training/skynode_data.py
SAFE_ID = re.compile(r"[A-Za-z0-9_-]+")                            # a Drive id: letters, digits, - and _
FOLDER_TYPE = "application/vnd.google-apps.folder"


def drive_service(key_json):
    """A Drive client for the service account whose key file text is `key_json`."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    info = json.loads(key_json)
    credentials = service_account.Credentials.from_service_account_info(info, scopes=[SCOPE])
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def check_id(value, what="id"):
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise ValueError(f"{what} {value!r} does not look like a Drive id")
    return value


def list_clips(service, folder_ids):
    """Video files directly inside the folders, as dicts (id, name, size, folder), by name.

    If two folders hold a clip with the same name, the first folder wins (training
    remembers clips by name, so a repeat would be skipped anyway).
    """
    found = {}
    for folder in folder_ids:
        check_id(folder, "folder id")
        token = None
        while True:
            reply = service.files().list(
                q=f"'{folder}' in parents and trashed = false and mimeType != '{FOLDER_TYPE}'",
                fields="nextPageToken, files(id, name, size)",
                pageSize=200, pageToken=token,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()
            for item in reply.get("files", []):
                name = item.get("name", "")
                if Path(name).suffix.lower() in VIDEO_EXTS and not name.startswith("."):
                    found.setdefault(name, {"id": item["id"], "name": name,
                                            "size": int(item.get("size") or 0), "folder": folder})
            token = reply.get("nextPageToken")
            if not token:
                break
    return [found[name] for name in sorted(found)]


def download(service, file_id, destination, chunk=16 * 1024 * 1024):
    """Save one Drive file to `destination` (a path), in chunks."""
    from googleapiclient.http import MediaIoBaseDownload
    check_id(file_id, "file id")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "wb") as handle:
        downloader = MediaIoBaseDownload(handle, service.files().get_media(
            fileId=file_id, supportsAllDrives=True), chunksize=chunk)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return destination
