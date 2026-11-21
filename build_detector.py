"""Build ClearView's everyday-object detector from vocabulary.txt.

YOLOE is an open-vocabulary detector: instead of being trained on a fixed set of
objects, it finds whatever is named in a text list. This script bakes the list in
vocabulary.txt into two ready-to-use models:

- clearview-detector.pt                         desktop app (app.py)
- phone-web/public/models/clearview-detector.onnx  phone website
- phone-web/public/models/labels.json            the phone's list of names

Run after editing vocabulary.txt:
    .venv\\Scripts\\python.exe build_detector.py
The first run downloads YOLOE and its text encoder.
"""
import json
import shutil
from pathlib import Path

from ultralytics import YOLOE

PROJECT = Path(__file__).resolve().parent
BASE_MODEL = "yoloe-26n-seg.pt"
DESKTOP_MODEL = PROJECT / "clearview-detector.pt"
PHONE_MODELS = PROJECT / "phone-web" / "public" / "models"


def read_vocabulary(path=PROJECT / "vocabulary.txt"):
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        name = line.strip().lower()
        if name and not name.startswith("#") and name not in names:
            names.append(name)
    return names


def main():
    names = read_vocabulary()
    print(f"Building a detector for {len(names)} objects…")
    model = YOLOE(BASE_MODEL)
    model.set_classes(names, model.get_text_pe(names))

    model.save(DESKTOP_MODEL)
    print(f"Desktop model: {DESKTOP_MODEL.name}")

    exported = Path(model.export(format="onnx", imgsz=640, simplify=True))
    PHONE_MODELS.mkdir(parents=True, exist_ok=True)
    shutil.move(exported, PHONE_MODELS / "clearview-detector.onnx")
    (PHONE_MODELS / "labels.json").write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")
    print(f"Phone model: {PHONE_MODELS / 'clearview-detector.onnx'}")


if __name__ == "__main__":
    main()
