"""Benchmark ClearView's detectors on all 80 YOLO26 object types, using COCO.

Usage (from the project folder):
    .venv\\Scripts\\python.exe evaluation\\coco_benchmark.py

Uses COCO's *validation* photos, which none of the models were trained on (the
small coco8 / coco128 sets come from the training photos and would flatter
YOLO26). Photos are chosen so each of the 80 object types appears at least
--per-class times. Downloads (about 50 MB of labels plus the chosen photos) go to
evaluation/coco-cache/, which git ignores.

Three set-ups are scored from the same two model runs, with the apps' own
confidence bars:
    combined  everyday-object model + YOLO26, merged as the apps do
    everyday  the everyday-object model alone
    yolo26    YOLO26 alone

Per object type:
    found      real objects of that type found and named correctly (recall)
    correct    of the detections with that name, how many were really there (precision)
A detection counts when its name matches and its box overlaps the real one by
at least half (IoU >= 0.5), the usual standard. "Closest object" scores the apps'
main job: naming the largest non-person object in each photo.

Results: evaluation/coco-results.md (table) and evaluation/coco-results.csv.
"""
import argparse
import csv
import io
import random
import sys
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

import cv2  # noqa: E402
from ultralytics import YOLO  # noqa: E402

from clearview.config import (  # noqa: E402
    CLEARVIEW_MODEL_FILE,
    DETECTOR_CLEARVIEW,
    DETECTOR_CONFIDENCE,
    MIN_CONFIDENCE,
)
from clearview.detection import (  # noqa: E402
    COCO_TO_EVERYDAY,
    box_area,
    box_iou,
    drop_worn_items,
    load_coco_model,
    merge_with_coco,
    read_detections,
)

LABELS_ZIP = "https://github.com/ultralytics/assets/releases/download/v0.0.0/coco2017labels.zip"
IMAGE_URL = "http://images.cocodataset.org/val2017/{}.jpg"
CACHE = PROJECT / "evaluation" / "coco-cache"
SETUPS = ("combined", "everyday", "yolo26")
HEADERS = {"User-Agent": "ClearView-Benchmark/1.0"}
# For the fairer "equivalent names" scoring: more specific everyday names that are
# still a correct answer for a COCO type (a mug is a cup; COCO has no "mug").
EQUIVALENT_TO_COCO = {
    "mug": "cup", "glass": "cup",
    "water bottle": "bottle", "shampoo bottle": "bottle", "medicine bottle": "bottle", "pill bottle": "bottle",
    "monitor": "tv", "desk": "table", "notebook": "book", "bag": "handbag", "plastic bag": "handbag",
}


def download(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def load_val_labels():
    """{image id: [(class index, cx, cy, w, h), ...]} for COCO val2017 (normalised boxes)."""
    labels_dir = CACHE / "labels"
    if not labels_dir.exists():
        print("Downloading COCO validation labels…")
        with zipfile.ZipFile(io.BytesIO(download(LABELS_ZIP))) as archive:
            for name in archive.namelist():
                if "/labels/val2017/" in name and name.endswith(".txt"):
                    (labels_dir / Path(name).name).parent.mkdir(parents=True, exist_ok=True)
                    (labels_dir / Path(name).name).write_bytes(archive.read(name))
    labels = {}
    for path in labels_dir.glob("*.txt"):
        rows = []
        for line in path.read_text().splitlines():
            parts = line.split()
            if len(parts) == 5:
                rows.append((int(parts[0]), *map(float, parts[1:])))
        if rows:
            labels[path.stem] = rows
    return labels


def choose_images(labels, per_class, seed=7):
    """Pick photos until every class has at least per_class objects."""
    ids = sorted(labels)
    random.Random(seed).shuffle(ids)
    counts = [0] * 80
    chosen = []
    for image_id in ids:
        classes = {row[0] for row in labels[image_id]}
        if any(counts[c] < per_class for c in classes):
            chosen.append(image_id)
            for row in labels[image_id]:
                counts[row[0]] += 1
        if min(counts) >= per_class:
            break
    return chosen


def fetch_images(image_ids):
    folder = CACHE / "images"
    folder.mkdir(parents=True, exist_ok=True)
    missing = [i for i in image_ids if not (folder / f"{i}.jpg").exists()]
    if missing:
        print(f"Downloading {len(missing)} photos…")

        def get(image_id):
            (folder / f"{image_id}.jpg").write_bytes(download(IMAGE_URL.format(image_id)))

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(get, missing))
    return folder


def run(model, frame, confidence):
    results = model.predict(frame, verbose=False, conf=confidence)
    return read_detections(results[0]) if results else []


def everyday_name(name):
    return COCO_TO_EVERYDAY.get(name, name)


def largest_object(detections):
    """The apps' closest object: the largest non-person, ignoring things worn by people."""
    things = [d for d in drop_worn_items(detections) if d["label"] != "person"]
    return max(things, key=box_area, default=None)


def score_image(truth, predictions, tally):
    """Match predictions to real objects of the same name (IoU >= 0.5)."""
    for name in {t["label"] for t in truth} | {p["label"] for p in predictions}:
        real = [t for t in truth if t["label"] == name]
        guesses = sorted((p for p in predictions if p["label"] == name), key=lambda p: -p["confidence"])
        used = set()
        hits = 0
        for guess in guesses:
            best, best_iou = None, 0.5
            for index, item in enumerate(real):
                iou = box_iou(guess["coordinates"], item["coordinates"])
                if index not in used and iou >= best_iou:
                    best, best_iou = index, iou
            if best is not None:
                used.add(best)
                hits += 1
        entry = tally.setdefault(name, {"real": 0, "guesses": 0, "hits": 0})
        entry["real"] += len(real)
        entry["guesses"] += len(guesses)
        entry["hits"] += hits


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--per-class", type=int, default=10, help="minimum objects of each type")
    args = parser.parse_args()

    labels = load_val_labels()
    image_ids = choose_images(labels, args.per_class)
    folder = fetch_images(image_ids)

    everyday_model = YOLO(str(PROJECT / CLEARVIEW_MODEL_FILE))
    coco_model = load_coco_model()
    coco_names = [coco_model.names[i] for i in range(len(coco_model.names))]
    in_vocabulary = set(everyday_model.names.values())

    tallies = {setup: {} for setup in SETUPS}
    fair_tallies = {setup: {} for setup in SETUPS}
    closest = {setup: 0 for setup in SETUPS}
    fair_closest = {setup: 0 for setup in SETUPS}
    misses = {setup: {"other COCO type": 0, "name COCO doesn't label": 0, "nothing found": 0} for setup in SETUPS}
    coco_label_set = {everyday_name(n) for n in coco_names}
    closest_total = 0
    for number, image_id in enumerate(image_ids, 1):
        frame = cv2.imread(str(folder / f"{image_id}.jpg"))
        if frame is None:
            continue
        height, width = frame.shape[:2]
        truth = [
            {
                "label": everyday_name(coco_names[c]),
                "coordinates": [(cx - w / 2) * width, (cy - h / 2) * height, (cx + w / 2) * width, (cy + h / 2) * height],
            }
            for c, cx, cy, w, h in labels[image_id]
        ]
        everyday = run(everyday_model, frame, DETECTOR_CONFIDENCE[DETECTOR_CLEARVIEW])
        coco = run(coco_model, frame, MIN_CONFIDENCE)
        outputs = {
            "combined": merge_with_coco(everyday, coco, coco_names),
            "everyday": everyday,
            "yolo26": [dict(d, label=everyday_name(d["label"])) for d in coco],
        }
        real_closest = largest_object(truth)
        if real_closest:
            closest_total += 1
        for setup, predictions in outputs.items():
            score_image(truth, predictions, tallies[setup])
            fair = [dict(p, label=EQUIVALENT_TO_COCO.get(p["label"], p["label"])) for p in predictions]
            score_image(truth, fair, fair_tallies[setup])
            guess = largest_object(predictions)
            fair_guess = largest_object(fair)
            if not real_closest:
                continue
            if guess and guess["label"] == real_closest["label"]:
                closest[setup] += 1
            if fair_guess and fair_guess["label"] == real_closest["label"]:
                fair_closest[setup] += 1
            elif not fair_guess:
                misses[setup]["nothing found"] += 1
            elif fair_guess["label"] in coco_label_set:
                misses[setup]["other COCO type"] += 1
            else:
                misses[setup]["name COCO doesn't label"] += 1
        if number % 50 == 0:
            print(f"  {number}/{len(image_ids)} photos")

    write_results(tallies, closest, closest_total, len(image_ids), coco_names, in_vocabulary,
                  fair_tallies, fair_closest, misses)


def ratio(part, whole):
    return f"{part / whole:.0%}" if whole else "–"


def summary_rows(tallies, closest, closest_total, names):
    rows = []
    for setup in SETUPS:
        t = {key: sum(tallies[setup].get(n, {}).get(key, 0) for n in names) for key in ("real", "guesses", "hits")}
        rows.append(
            f"| {setup} | {ratio(closest[setup], closest_total)} ({closest[setup]}/{closest_total}) "
            f"| {ratio(t['hits'], t['real'])} | {ratio(t['hits'], t['guesses'])} |"
        )
    return rows


def write_results(tallies, closest, closest_total, photos, coco_names, in_vocabulary,
                  fair_tallies, fair_closest, misses):
    names = [everyday_name(n) for n in coco_names]
    header = [
        "| Set-up | Closest object named correctly | Objects found (recall) | Detections really there (precision) |",
        "|---|---|---|---|",
    ]
    lines = [
        "# COCO benchmark: all 80 YOLO26 object types",
        "",
        f"{photos} COCO validation photos (not used to train any of the models), chosen so every type "
        "appears at least 10 times. Created by `evaluation/coco_benchmark.py`.",
        "",
        "## Strict scoring (only COCO's own names count)",
        "",
        *header,
        *summary_rows(tallies, closest, closest_total, names),
        "",
        "## Fairer scoring (clear equivalents accepted)",
        "",
        "Also accepts more specific names that are still right: "
        + ", ".join(f"{a} → {b}" for a, b in EQUIVALENT_TO_COCO.items()) + ".",
        "",
        *header,
        *summary_rows(fair_tallies, fair_closest, closest_total, names),
        "",
        "Why the closest object was missed (fairer scoring):",
        "",
        "| Set-up | Named another COCO type | Named something COCO doesn't label | Found nothing |",
        "|---|---|---|---|",
    ]
    for setup in SETUPS:
        other, unlabelled, nothing = misses[setup].values()
        lines.append(f"| {setup} | {other} | {unlabelled} | {nothing} |")
    lines += [
        "",
        "## Per object type",
        "",
        "Found = real objects of this type found and named correctly. Correct = detections with this name "
        "that were really there. ✗ = the type isn't in vocabulary.txt, so the everyday model can't name it.",
        "",
        "| Object | Real | Found: combined | everyday | yolo26 | Correct: combined | everyday | yolo26 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    rows = []
    for name in sorted(set(names)):
        cells = {s: tallies[s].get(name, {"real": 0, "guesses": 0, "hits": 0}) for s in SETUPS}
        real = cells["combined"]["real"]
        mark = "" if name in in_vocabulary else " ✗"
        found = [ratio(cells[s]["hits"], cells[s]["real"]) for s in SETUPS]
        correct = [ratio(cells[s]["hits"], cells[s]["guesses"]) for s in SETUPS]
        lines.append(f"| {name}{mark} | {real} | " + " | ".join(found + correct) + " |")
        rows.append([name, name in in_vocabulary, real] + [cells[s][k] for s in SETUPS for k in ("hits", "guesses")])
    (PROJECT / "evaluation" / "coco-results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (PROJECT / "evaluation" / "coco-results.csv").open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["object", "in_vocabulary", "real"] + [f"{s}_{k}" for s in SETUPS for k in ("hits", "detections")])
        writer.writerows(rows)
    print("\n".join(lines[4:4 + 2 + len(SETUPS)]))
    print("\nFull table: evaluation/coco-results.md")


if __name__ == "__main__":
    main()
