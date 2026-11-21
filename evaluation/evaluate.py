"""Score ClearView's object detection on your own labelled photos.

Usage (from the project folder):
    .venv\\Scripts\\python.exe evaluation\\evaluate.py evaluation\\photos evaluation\\labels.csv

labels.csv has one row per photo:
    photo,closest,also_visible
    desk1.jpg,cup,laptop;book
    kitchen2.jpg,bottle,

Names must be ones in vocabulary.txt (see evaluation/README.md).
This runs the same everyday-object detector and the same "closest = largest object"
logic as both apps, so the scores describe both. Results are written to
evaluation/results.csv.
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
    DETECTOR_CLEARVIEW,
    DETECTOR_CONFIDENCE,
    AnalysisWorker,
)


def parse_names(cell):
    return {name.strip().lower() for name in (cell or "").split(";") if name.strip()}


def predict(model, image_path, min_confidence):
    frame = cv2.imread(str(image_path))
    if frame is None:
        raise ValueError(f"could not open {image_path.name}")
    results = model.predict(frame, verbose=False, conf=min_confidence)
    detections = AnalysisWorker._read_detections(results[0]) if results else []
    chosen = AnalysisWorker._select_detection(detections)
    closest = chosen["label"].strip().lower().replace("_", " ") if chosen else ""
    return closest, set(AnalysisWorker._list_labels(detections))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("photos", type=Path, help="folder of photos")
    parser.add_argument("labels", type=Path, help="labels.csv")
    parser.add_argument("--model", default=str(PROJECT / CLEARVIEW_MODEL_FILE))
    parser.add_argument(
        "--conf", type=float, default=DETECTOR_CONFIDENCE[DETECTOR_CLEARVIEW],
        help="minimum confidence (use 0.3 when testing yolo26n.pt)",
    )
    parser.add_argument("--out", type=Path, default=PROJECT / "evaluation" / "results.csv")
    args = parser.parse_args()

    with args.labels.open(newline="", encoding="utf-8-sig") as labels_file:
        rows = [row for row in csv.DictReader(labels_file) if (row.get("photo") or "").strip()]
    if not rows:
        sys.exit(f"No photos listed in {args.labels}.")

    model = YOLO(args.model)
    results = []
    for row in rows:
        photo = args.photos / row["photo"].strip()
        expected_closest = row["closest"].strip().lower()
        expected_all = parse_names(row.get("also_visible")) | {expected_closest}
        try:
            predicted_closest, predicted_all = predict(model, photo, args.conf)
        except ValueError as error:
            print(f"Skipped: {error}")
            continue
        results.append({
            "photo": photo.name,
            "expected_closest": expected_closest,
            "predicted_closest": predicted_closest,
            "closest_correct": predicted_closest == expected_closest,
            "expected_all": expected_all,
            "predicted_all": predicted_all,
        })

    if not results:
        sys.exit("No photos could be scored.")

    closest_hits = sum(result["closest_correct"] for result in results)
    found = sum(len(r["expected_all"] & r["predicted_all"]) for r in results)
    expected = sum(len(r["expected_all"]) for r in results)
    predicted = sum(len(r["predicted_all"]) for r in results)
    recall = found / expected if expected else 0.0
    precision = found / predicted if predicted else 0.0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as out_file:
        writer = csv.writer(out_file)
        writer.writerow([
            "photo", "expected_closest", "predicted_closest", "closest_correct",
            "missed", "extra",
        ])
        for r in results:
            writer.writerow([
                r["photo"], r["expected_closest"], r["predicted_closest"],
                "yes" if r["closest_correct"] else "no",
                ";".join(sorted(r["expected_all"] - r["predicted_all"])),
                ";".join(sorted(r["predicted_all"] - r["expected_all"])),
            ])

    count = len(results)
    print(f"Photos scored: {count}")
    print(f"Closest object named correctly: {closest_hits}/{count} ({closest_hits / count:.0%})")
    print(f"Objects found (recall): {found}/{expected} ({recall:.0%})")
    print(f"Listed objects that were really there (precision): {found}/{predicted} ({precision:.0%})")
    misses = [r for r in results if not r["closest_correct"]]
    if misses:
        print("\nWrong closest object:")
        for r in misses:
            print(f"  {r['photo']}: expected {r['expected_closest']}, got {r['predicted_closest'] or 'nothing'}")
    print(f"\nPer-photo details: {args.out}")


if __name__ == "__main__":
    main()
