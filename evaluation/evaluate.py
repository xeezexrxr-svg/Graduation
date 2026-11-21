"""Score ClearView's object detection on your own labelled photos.

Usage (from the project folder):
    .venv\\Scripts\\python.exe evaluation\\evaluate.py evaluation\\photos evaluation\\labels.csv
    .venv\\Scripts\\python.exe evaluation\\evaluate.py evaluation\\photos evaluation\\labels.csv --compare

labels.csv has one row per photo:
    photo,closest,also_visible
    desk1.jpg,cup,laptop;book
    kitchen2.jpg,bottle,

Names must be ones in vocabulary.txt (see evaluation/README.md).

Detector set-ups (--detector):
    combined  the default in both apps: everyday-object model + YOLO26
    everyday  the everyday-object model alone
    yolo26    YOLO26 alone (80 object types)
--compare scores all three on the same photos and prints a comparison table.
All use the same "closest = largest object" logic as the apps. Per-photo
results are written to evaluation/results-<set-up>.csv.
"""
import argparse
import csv
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

import cv2  # noqa: E402
from ultralytics import YOLO  # noqa: E402

from app import (  # noqa: E402
    CLEARVIEW_MODEL_FILE,
    COCO_TO_EVERYDAY,
    DETECTOR_CLEARVIEW,
    DETECTOR_CONFIDENCE,
    MIN_CONFIDENCE,
    AnalysisWorker,
    load_coco_model,
    merge_with_coco,
)

SETUPS = ("combined", "everyday", "yolo26")


def parse_names(cell):
    return {name.strip().lower() for name in (cell or "").split(";") if name.strip()}


class Detector:
    """One detector set-up, giving detections in the desktop app's format."""

    def __init__(self, setup):
        self.setup = setup
        self.everyday = YOLO(str(PROJECT / CLEARVIEW_MODEL_FILE)) if setup != "yolo26" else None
        self.coco = load_coco_model() if setup != "everyday" else None
        if setup != "everyday" and self.coco is None:
            sys.exit("YOLO26 (yolo26n.pt) could not be loaded.")

    def _run(self, model, frame, confidence):
        results = model.predict(frame, verbose=False, conf=confidence)
        return AnalysisWorker._read_detections(results[0]) if results else []

    def detect(self, frame):
        everyday = (
            self._run(self.everyday, frame, DETECTOR_CONFIDENCE[DETECTOR_CLEARVIEW])
            if self.everyday else []
        )
        if self.coco is None:
            return everyday
        coco = self._run(self.coco, frame, MIN_CONFIDENCE)
        if self.everyday is None:
            # Use the same names as vocabulary.txt so labels.csv scores fairly.
            return [dict(d, label=COCO_TO_EVERYDAY.get(d["label"], d["label"])) for d in coco]
        return merge_with_coco(everyday, coco, self.coco.names.values())


def score(detector, photos, rows):
    results = []
    for row in rows:
        photo = photos / row["photo"].strip()
        frame = cv2.imread(str(photo))
        if frame is None:
            print(f"Skipped: could not open {photo.name}")
            continue
        detections = detector.detect(frame)
        chosen = AnalysisWorker._select_detection(detections)
        expected_closest = row["closest"].strip().lower()
        predicted_closest = chosen["label"].strip().lower().replace("_", " ") if chosen else ""
        results.append({
            "photo": photo.name,
            "expected_closest": expected_closest,
            "predicted_closest": predicted_closest,
            "closest_correct": predicted_closest == expected_closest,
            "expected_all": parse_names(row.get("also_visible")) | {expected_closest},
            "predicted_all": set(AnalysisWorker._list_labels(detections)),
        })
    return results


def summarise(results):
    found = sum(len(r["expected_all"] & r["predicted_all"]) for r in results)
    expected = sum(len(r["expected_all"]) for r in results)
    predicted = sum(len(r["predicted_all"]) for r in results)
    return {
        "photos": len(results),
        "closest": sum(r["closest_correct"] for r in results),
        "found": found,
        "expected": expected,
        "predicted": predicted,
    }


def write_details(results, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as out_file:
        writer = csv.writer(out_file)
        writer.writerow(["photo", "expected_closest", "predicted_closest", "closest_correct", "missed", "extra"])
        for r in results:
            writer.writerow([
                r["photo"], r["expected_closest"], r["predicted_closest"],
                "yes" if r["closest_correct"] else "no",
                ";".join(sorted(r["expected_all"] - r["predicted_all"])),
                ";".join(sorted(r["predicted_all"] - r["expected_all"])),
            ])


def percent(part, whole):
    return f"{part}/{whole} ({part / whole:.0%})" if whole else "n/a"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("photos", type=Path, help="folder of photos")
    parser.add_argument("labels", type=Path, help="labels.csv")
    parser.add_argument("--detector", choices=SETUPS, default="combined")
    parser.add_argument("--compare", action="store_true", help="score all three set-ups")
    parser.add_argument("--out-dir", type=Path, default=PROJECT / "evaluation")
    args = parser.parse_args()

    with args.labels.open(newline="", encoding="utf-8-sig") as labels_file:
        rows = [row for row in csv.DictReader(labels_file) if (row.get("photo") or "").strip()]
    if not rows:
        sys.exit(f"No photos listed in {args.labels}.")

    setups = SETUPS if args.compare else (args.detector,)
    summaries = {}
    for setup in setups:
        results = score(Detector(setup), args.photos, rows)
        if not results:
            sys.exit("No photos could be scored.")
        write_details(results, args.out_dir / f"results-{setup}.csv")
        summaries[setup] = summarise(results)
        if not args.compare:
            misses = [r for r in results if not r["closest_correct"]]
            if misses:
                print("Wrong closest object:")
                for r in misses:
                    print(f"  {r['photo']}: expected {r['expected_closest']}, got {r['predicted_closest'] or 'nothing'}")
                print()

    print(f"{'Set-up':<10} {'Closest correct':<18} {'Found (recall)':<18} {'Really there (precision)'}")
    for setup, s in summaries.items():
        print(
            f"{setup:<10} {percent(s['closest'], s['photos']):<18} "
            f"{percent(s['found'], s['expected']):<18} {percent(s['found'], s['predicted'])}"
        )
    print(f"\nPer-photo details: {args.out_dir}\\results-<set-up>.csv")


if __name__ == "__main__":
    main()
