# ClearView

ClearView is a camera assistant for people with dyslexia or other reading difficulties. Point a camera at everyday things and it names the closest object, lists everything else in view, reads any label text, and reads the result aloud with word-by-word highlighting, on reading colours and spacing each person chooses.

It comes in two forms that share the same detection model and design:

| | Phone website (`phone-web/`) | Desktop app (`app.py`) |
|---|---|---|
| Best for | Everyday use: point your phone at things | A fixed reading station, or offline use |
| Object detection | Everyday-object detector (YOLOE, 175 objects) combined with YOLO26, in the browser | The same pair locally (YOLO26 alone and YOLO-World as options) |
| Description of the closest object | Cloudflare Workers AI | Cloudflare Workers AI (optional) |
| Label / page text | Workers AI, plus Tesseract.js for whole pages | EasyOCR, locally |
| Speech | The phone's built-in voices | Windows voices |

## How it works

```
 camera photo
      │
      ▼
 everyday-object detector ──► every object in view, with a box around each
      │
      ├──► "closest" = the largest box that isn't a person
      │         │
      │         ▼  (only this crop leaves the device)
      │    /api/identify on Cloudflare
      │      ├─ LLaVA: a short description of the object
      │      └─ Moondream: label text (English, 繁體中文)
      │
      ▼
 "This is a cup. <description> I can also see: laptop, book."
      │
      ▼
 read aloud, highlighting each word, on the reader's chosen tint and spacing
```

The cloud's name wins, because it looks at the object closely. If the cloud step is
unavailable, both apps give the on-device name and a short built-in description, and when
the detector is less than 60% sure they say so: "This might be a cup."

**Two detectors together.** The everyday-object model knows 175 objects but makes more
mistakes on common ones (it once called a mouse seen from above a cell phone). YOLO26 knows
only 80 but is more reliable on those. Both run on every photo: when they find the same
object, YOLO26's name wins if the everyday model also thought it was one of YOLO26's types;
objects YOLO26 doesn't know (wallet, keys) keep the everyday model's name.

**Design choices for dyslexic readers**
- Six background tints (cream, yellow, blue, mint, peach, dark), because the most comfortable colour varies from person to person; text is dark grey on soft colours, never black on white.
- Wider letter, word and line spacing, left-aligned text, no all-caps; the Atkinson Hyperlegible typeface on the phone, Verdana by default on the desktop.
- The sentence being read is shaded and the current word highlighted, so readers can follow along.
- Every reading setting is remembered between visits.
- Mostly-Chinese text is read with a Chinese voice automatically when one is installed.

## Run the desktop app (Windows)

1. Install Python 3.10 or newer.
2. Open PowerShell in this folder and create a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

3. Start the app:

   ```powershell
   python app.py
   ```

The first start may take longer because YOLO26, the text reader, and their models may need to download model files. The app installs the CLIP dependency from a ZIP, so Git is not required. The everyday-object detector is the default; use the top-left menu to switch to YOLO26 or the YOLO-World backup, change the background colour, or adjust camera brightness. Allow camera access when Windows asks. After choosing a photo, select **Identify object** once the AI models are ready.

Reading settings (colour, font, size, spacing, voice, speed, volume) are saved to `settings.json` when you close the app.

## Phone website

The mobile website and its Cloudflare Pages deployment are in `phone-web`. See `phone-web/README.md` for deployment and binding setup.

## Desktop features

- Live camera preview and photo selection
- Three-line app menu with background colour, YOLO26 as the default detector, a YOLO-World backup option, and camera-image brightness control
- Names the closest object (the largest one in view, preferring something held in a hand) and lists every other object it can see
- Uses EasyOCR to read visible English and Traditional Chinese text in the detected object's crop; recognized text is added to the result and read aloud with the object explanation
- Sends the detected object crop to Cloudflare Workers AI for a more specific, free-form description and label-based product identification
- Object identification in a background worker, so model loading and analysis do not freeze the interface
- Plain-language explanations and repeatable Windows SAPI text-to-speech playback with sentence and current-word highlighting that follows speech
- Text settings (font, bold, size, letter spacing, line spacing) and voice settings (voice, speed, volume) side by side under the result
- Automatic speech toggle, repeat control, and confidence display
- Editable object descriptions in `phone-web/public/object_descriptions.json`, shared with the phone site
- Clear status messages if the camera, model, or speech engine is unavailable

## Change which objects it knows

The default detector is YOLOE, an open-vocabulary model: rather than being trained on a fixed set of objects, it looks for whatever is named in a list. That list is `vocabulary.txt` (175 everyday objects, including wallet, keys, pen, glasses, medicine bottle and toothpaste). To add or remove objects, edit the file and rebuild both apps' models:

```powershell
.venv\Scripts\python.exe build_detector.py
```

This writes `clearview-detector.pt` (desktop) and `phone-web/public/models/clearview-detector.onnx` plus `labels.json` (phone). Commit them and push to update the phone site. Short, common names work best; very similar names (mug / cup) can be confused with each other.

## Add or change an explanation

Open `phone-web/public/object_descriptions.json` and add a lowercase object name and a short explanation. Both apps read this one file (the phone site serves it), so a change shows up in both. For example:

```json
{
  "bottle": "It can hold drinks, such as water.",
  "remote": "It is used to control a device from a short distance."
}
```

Keep the file as valid JSON: use double quotes around names and text, and put a comma between entries. The names provide descriptions for recognized classes and become candidate prompts when the YOLO-World backup is selected. YOLO26 uses its pretrained COCO classes; adding a name does not train it. Names can include spaces, such as `"cell phone"` or `"dining table"`. Either detector may miss or misidentify an object, so test results with the actual objects and camera.

## Tests

```powershell
.venv\Scripts\python.exe -m pip install pytest
.venv\Scripts\python.exe -m pytest           # desktop logic
cd phone-web; node --test                    # phone detector and API checks
```

## Evaluation

`evaluation/` holds a script that scores detection accuracy on your own labelled photos, and a user-testing kit for sessions with dyslexic readers. See `evaluation/README.md`.

## Notes and limitations

- "Closest" means the largest object in the picture; a camera can't measure distance. A big object further away can win over a small one nearby.
- The everyday-object detector only names things in `vocabulary.txt`, and uses a higher confidence bar (40%) than YOLO26 (30%) because open-vocabulary models make more weak guesses. **YOLO26** (80 fixed object types, very reliable on those) and the **YOLO-World backup** (prompts from `phone-web/public/object_descriptions.json`) are in the top-left menu. Both models can miss or misidentify objects; when a hand/person is detected, the app analyzes a padded crop and favors overlapping non-wearable objects over clothing and glasses. Confidence is shown to help users judge results.
- OCR can provide clues from labels or packaging, but it does not change YOLO's confidence and may misread text. If OCR cannot initialize, object detection continues without it.
- Camera brightness changes the app's camera preview and object-identification image, not the laptop display.
- Chinese text is read with an installed Chinese Windows voice when one exists; install one from Windows Settings → Time & language → Speech if Chinese is read incorrectly.
- This is a student prototype, not a safety device. Do not rely on it to identify medicine, hazards, or other safety-critical items.
- YOLO detection and EasyOCR run locally. The detected object crop is sent to Cloudflare Workers AI for the optional detailed description and product identification; use the app only with photos you are comfortable sending to the cloud. Pretrained model files may be downloaded by Ultralytics and EasyOCR the first time they run.
- The default reading font is Verdana, with Arial and Trebuchet MS as alternatives. OpenDyslexic and Atkinson Hyperlegible are offered when installed on the computer. The best font and reading settings vary between people, so users can choose their preferences.

## Project files

- `app.py` — starts the desktop app; its code is in `clearview/`:
  - `config.py` file paths, detector names and thresholds · `deps.py` optional libraries
  - `palette.py` the six reading tints · `language.py` Chinese text and voices
  - `detection.py` box maths, the closest-object rule, merging the two detectors
  - `analysis.py`, `camera.py`, `speech.py` the background workers · `storage.py` settings and descriptions
  - `ui.py` the window
- `vocabulary.txt` and `build_detector.py` — the objects the detector looks for, and the script that builds it
- `phone-web/` — mobile website and Cloudflare Pages Function
- `phone-web/public/object_descriptions.json` — short explanations shown and spoken by both apps
- `tests/` — desktop tests; `phone-web/tests/` — phone tests
- `evaluation/` — accuracy script and user-testing kit
- `requirements.txt` — Python dependencies
