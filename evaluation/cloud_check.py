"""Score what the full app says: on-device detector + the cloud description.

Like the apps, each photo's closest object is cropped and sent to the live
ClearView cloud (/api/identify); with no detection, or a box too small to
trust (see worth_cropping), the whole photo is sent.
The cloud's name wins when it gives one, as in the apps. A photo counts as
right when the expected name appears in that answer ("pear" in "Asian pear").

Usage (from the project folder):
    .venv\\Scripts\\python.exe evaluation\\cloud_check.py evaluation\\photos evaluation\\labels.csv
Writes evaluation/results-cloud.csv.
"""
import argparse
import csv
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "evaluation"))

import cv2  # noqa: E402

from clearview.analysis import CLOUD_ERRORS, request_cloud_details  # noqa: E402
from clearview.detection import select_closest  # noqa: E402
from evaluate import Detector  # noqa: E402


# Other answers that also count as right, agreed when checking the labels.
ALSO_RIGHT = {
    "computer mouse": ["mouse"],  # the cloud shortens it on purpose
    "light bulb": ["ceiling light"],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("photos", type=Path)
    parser.add_argument("labels", type=Path)
    parser.add_argument("--out", type=Path, default=PROJECT / "evaluation" / "results-cloud.csv")
    args = parser.parse_args()

    with args.labels.open(newline="", encoding="utf-8") as labels_file:
        rows = [row for row in csv.DictReader(labels_file) if (row.get("photo") or "").strip()]

    detector = Detector("combined")
    results = []
    for row in rows:
        frame = cv2.imread(str(args.photos / row["photo"].strip()))
        if frame is None:
            print(f"Skipped: could not open {row['photo']}")
            continue
        chosen = select_closest(detector.detect(frame))
        height, width = frame.shape[:2]
        target = chosen or {"label": "", "coordinates": [0, 0, width, height]}
        try:
            cloud = request_cloud_details(frame, target)
        except CLOUD_ERRORS as error:
            cloud = {"label": "", "description": f"(cloud failed: {error})"}
        # "bread|hot dog": either name counts as right for this photo.
        names = [name.strip() for name in row["closest"].lower().split("|")]
        expected = names[0]
        answer = (cloud.get("label") or "").strip() or target["label"]
        correct = any(name in answer.lower() for name in [*names, *ALSO_RIGHT.get(expected, [])])
        results.append([row["photo"], expected, target["label"], answer,
                         "yes" if correct else "no", (cloud.get("description") or "").strip()])
        print(f"{row['photo']:<18} {'yes' if correct else 'no ':<4} {answer}")

    out = args.out
    with out.open("w", newline="", encoding="utf-8") as out_file:
        writer = csv.writer(out_file)
        writer.writerow(["photo", "expected", "detector_said", "app_said", "correct", "cloud_description"])
        writer.writerows(results)
    right = sum(r[4] == "yes" for r in results)
    print(f"\nApp's answer correct: {right}/{len(results)} ({round(100 * right / len(results))}%)")
    print(f"Details: {out}")


if __name__ == "__main__":
    main()
