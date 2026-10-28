# ClearView

ClearView is a desktop prototype for an accessibility-focused camera assistant. It can identify common objects, explain their everyday purpose in short language, and read the explanation aloud.

## Run it on Windows

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
   python Appp.py
   ```

The first start may take longer because the object detector, text reader, and their models may need to download model files. The app installs the CLIP dependency from a ZIP, so Git is not required. The detector uses object names in `object_descriptions.json` as candidate labels. Allow camera access when Windows asks. After choosing a photo, select **Identify object** once the AI models are ready.

## Phone website

A separate mobile website and Cloudflare Pages deployment are in `phone-web`. It uses the phone browser's camera and speech synthesis, with object recognition through a Cloudflare Pages Function and Workers AI. See `phone-web/README.md` for deployment and binding setup. The Windows desktop app remains unchanged.

## What is included

- Live camera preview and photo selection
- Open-vocabulary object identification using names from `object_descriptions.json`
- Prefers a recognized held object over a person or hand detection, and retries on a padded person crop when an item is not detected in the full image
- Uses EasyOCR to read visible English and Traditional Chinese text in the detected object's crop; recognized text is added to the result and read aloud with the object explanation
- Object identification in a background worker, so model loading and analysis do not freeze the interface
- Plain-language explanations and repeatable Windows SAPI text-to-speech playback with sentence and current-word highlighting that follows speech
- Voice dropdown for choosing an installed Windows speech voice
- A two-card reading workspace with object explanations and read-aloud controls
- Font, text size, letter spacing, line spacing, speech speed, and volume controls beside the explanation
- Automatic speech toggle, repeat control, and confidence display
- Editable object descriptions in `object_descriptions.json`
- Clear status messages if the camera, model, or speech engine is unavailable

## Add or change an explanation

Open `object_descriptions.json` and add a lowercase object name and a short explanation. For example:

```json
{
  "bottle": "It can hold drinks, such as water.",
  "remote": "It is used to control a device from a short distance."
}
```

Keep the file as valid JSON: use double quotes around names and text, and put a comma between entries. The object names become candidate prompts for the open-vocabulary detector, so restart the app after editing the file. Names can include spaces, such as `"cell phone"` or `"dining table"`. The detector may still miss or misidentify an object; adding a name does not train the model, and results should be tested with the actual objects and camera.

## Notes and limitations

- The YOLO-World model can use the configured names as open-vocabulary detection prompts, but it will not identify every object reliably. Confidence is shown to help users judge results.
- OCR can provide clues from labels or packaging, but it does not change YOLO's confidence and may misread text. If OCR cannot initialize, object detection continues without it.
- Read-aloud pronunciation depends on the selected Windows voice supporting the recognized language. Install/select a Traditional Chinese voice in Windows for Chinese speech.
- This is a student prototype, not a safety device. Do not rely on it to identify medicine, hazards, or other safety-critical items.
- Camera frames and OCR are processed locally by this app. Pretrained model files may be downloaded by Ultralytics and EasyOCR the first time they run.
- The default reading font is Arial, with Verdana and Trebuchet MS as alternatives. OpenDyslexic is offered when installed on the computer. The best font and reading settings vary between people, so users can choose their preferences.

## Project files

- `Appp.py` — application, camera, detection, and speech workers
- `phone-web/` — separate mobile website and Cloudflare Pages Function
- `object_descriptions.json` — editable explanations shown and spoken by the app
- `requirements.txt` — Python dependencies
