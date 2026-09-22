import json
import os

PROGRESS_FILENAME = "progress.json"

# Ordered phases with the fraction complete a client should show while in each.
PHASES = {
    "downloading": 0.15,
    "analyzing": 0.6,
    "finishing": 0.9,
}


def report_phase(output_dir, phase):
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, PROGRESS_FILENAME), "w", encoding="utf-8") as f:
            json.dump({"phase": phase, "progress": PHASES.get(phase)}, f)
    except OSError:
        pass


def read_phase(output_dir):
    try:
        with open(os.path.join(output_dir, PROGRESS_FILENAME), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
