# Evaluating ClearView

Two kinds of evidence: **how accurate the detection is** (measured with photos) and
**whether it helps dyslexic readers** (measured with people). Use both in your report.

## 1. Accuracy test

### Take the photos
- Take **30–50 photos** of real scenes your users would meet: a desk, a kitchen
  counter, a shelf, a bag's contents. Use a phone, the same way a user would.
- Most photos should have **3 or more objects**, with one clearly closest to the camera.
- Mix the conditions: good and poor light, plain and busy backgrounds, objects
  partly hidden. Real use is messy; the test should be too.
- Put them all in `evaluation/photos/`.

### Label them
Copy `labels-template.csv` to `labels.csv` and add one row per photo. Write what is
**actually** in the photo, before running the test, so the answer can't influence you.

| Column | What to write |
|---|---|
| `photo` | the file name, e.g. `desk1.jpg` |
| `closest` | the object nearest the camera |
| `also_visible` | every other object, separated by `;` (leave out people) |

Only the names in `vocabulary.txt` (in the project folder) can be detected, so use them
exactly, in lower case. If an object in the photo isn't on the list, leave it out and note
it in your report as a known limit: the detector can't name it, though the cloud
description sometimes can. (Or add it to the list and rebuild; see the main README.)

### Run it
```powershell
.venv\Scripts\python.exe evaluation\evaluate.py evaluation\photos evaluation\labels.csv
```

It prints three numbers and writes `evaluation/results-combined.csv` with every photo's result:

- **Closest object named correctly**: the headline number. How often the app names the
  object the user is pointing at.
- **Recall**: of all the objects really there, how many it found.
- **Precision**: of the objects it listed, how many were really there (low = it invents things).

The test uses the same detectors and logic as both apps (the phone runs the same models
in the browser), so the numbers describe both. Add `--compare` to score three set-ups on the
same photos (both detectors combined, as the apps do; the everyday-object model alone; YOLO26
alone) and get a comparison table: a good section for a report, because it shows why the apps
combine them. It does not score the cloud
description sentence; judge a sample of those by hand if you want to report on them.

## 1b. Benchmark on all 80 YOLO26 object types (COCO)

```powershell
.venv\Scripts\python.exe evaluation\coco_benchmark.py
```

Downloads COCO *validation* photos (never used to train the models), chosen so all 80 object
types appear at least 10 times, and scores the three set-ups per object type. Results:
[coco-results.md](coco-results.md). Read them with two limits in mind:

- COCO only labels its 80 types, so when the everyday model correctly names something else
  (a plate, a mirror, a game controller in someone's hand) it is scored as wrong.
- COCO photos are wide scenes; the apps are used close up on one object, where
  "largest = closest" is much less ambiguous. Your own photos (section 1) test that.

## 2. Testing with dyslexic readers

See [user-testing.md](user-testing.md) for a ready-to-use session plan and questionnaire.
