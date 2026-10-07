# Contributing to Skynode

Thanks for looking. Skynode is one student's project, so reviews can take a few days, and small, focused pull requests get merged fastest.

## Scope first

Skynode is a **passive** sensing and tracking platform. Pull requests that transmit on aviation or drone-control frequencies, jam, spoof, or act on aircraft won't be merged. The README's Scope section is the rule.

## Setup

```bash
pip install -r brain/requirements.txt opencv-python-headless onnx
python -m unittest discover tests -v
pip install ruff && ruff check .
```

Website work lives in `web/`:

```bash
cd web
npm ci
npm run check
npm run build
```

## Before you open a pull request

- The tests and `ruff check .` pass. CI runs the same two commands.
- If you change the behavior or status of something, update the README status table and the website Status section together. They must say the same thing.
- Don't add a number to the docs unless its source is in the repo (a file, a test, or a dataset note).
- Anything that hasn't run on real hardware must say "simulated" or "not built yet." Don't remove those labels without evidence.
- Keep the diff to one change. Unrelated cleanup goes in its own pull request.

## Commits and branches

Use short imperative commit messages ("Add tracker timeout to config"). Branch from `main`.

## Privacy

Don't commit Wi-Fi names or passwords, camera addresses with passwords, photos or videos of people, or personal details. Snapshots from the logger are gitignored; keep it that way.

## Where things are

| Folder | What's there |
|---|---|
| `brain/` | Detection, tracking, control, logging, dashboard (laptop or Pi) |
| `pico/` | MicroPython servo firmware |
| `hardware/` | Pan-tilt CAD and printable files |
| `web/` | The project website |
| `tests/` | Laptop-side tests |
| `training/` | Colab training notebook and dataset scripts |
