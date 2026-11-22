# ClearView Phone

The mobile ClearView website, designed for readers with dyslexia. It shares its detection model and design with the desktop app in the project root.

## What it does

- Uses the phone's rear camera or photo picker to capture one image.
- Provides a separate Text scanner screen from the three-line feature menu, with its own camera capture and photo picker.
- Scans full-page English and Traditional Chinese text locally in the browser, then lets users edit or select recognized text to copy or read aloud with the current word highlighted when the browser reports speech boundaries.
- Finds every object in the photo on the phone itself, with two detectors running in the browser through ONNX Runtime Web: ClearView's everyday-object model (`public/models/clearview-detector.onnx`, YOLOE built from the project's `vocabulary.txt`) and YOLO26 (`public/models/yolo26n.onnx`), which corrects it on the 80 objects YOLO26 knows well. The largest object that isn't a person is treated as the closest; the others are listed as "I can also see: …".
- Sends the closest object's crop to a Pages Function, which asks Cloudflare Workers AI's Moondream 3.1 model for a free-form description of it and to read visible label text (including Traditional Chinese) and infer a product from the readable label. If that fails, the on-device name is shown instead.
- Shows the generated item description, recognized label text, and any product identification based on that text, then reads the result aloud using the browser's built-in speech synthesis, with sentence and current-word highlighting when the browser reports speech boundaries.
- **Ruler view** on the Read a page screen: a reading ruler keeps your place one line (or 2–3 lines) at a time and fades the rest of the page. Move it by tapping a line, the Previous/Next line buttons, or the arrow keys. Read all starts from the ruler's line, and the ruler follows the voice while the sentence (highlighter yellow) and word (solid blue) are highlighted.
- Reading preferences offer six background tints, text size, letter spacing, speech speed, voice, and the reading ruler (off or 1–3 lines; other lines clear, faded or almost hidden); all are remembered on the device.
- Does not save photos. The closest object's crop is sent to Cloudflare for a description; the whole photo is sent when no object was found or the closest box is under 10% of the photo (usually a sign the detector missed the real object).

The website needs HTTPS for camera access and clipboard access, so use the deployed Cloudflare Pages URL on your phone. The photo picker remains available when camera access is denied or unavailable.

The separate text scanner uses Tesseract.js in the browser to recognize English and Traditional Chinese. Open it from the three-line menu; its camera and photo picker are separate from object scanning. Its OCR models are downloaded on first use and cached by the browser; the selected image is processed on-device and is not uploaded for text scanning. Object identification still sends the image to Cloudflare Workers AI.

## Deploy to Cloudflare Pages

1. Push this repository to a Git provider connected to Cloudflare, or use the Cloudflare Pages dashboard to create a project from this repository.
2. Set the Pages project root directory to `phone-web`.
3. Use `public` as the build output directory. There is no build command.
4. The Workers AI binding is configured as `ai.binding: "AI"` in `wrangler.jsonc`. Commit and push that configuration so Cloudflare deploys it with the Pages project.
5. Open the deployed `*.pages.dev` address on your phone and allow camera access. The phone and computer should be using the same public HTTPS site.

The Pages Function is `functions/api/identify.js`; its `/api/identify` endpoint uses Cloudflare Workers AI's Moondream 3.1 model for object identification and English/Traditional Chinese label reading (LLaVA was retired on 2026-11-20). OCR failures do not block object identification. Product identification is inferred from the recognized text and can still be wrong. The Wrangler configuration file is the source of truth for this Pages project's settings, including the Workers AI binding.

### Cost protection

Every call to `/api/identify` uses Workers AI quota, so the endpoint only answers ClearView itself: browser requests must come from this site, and other callers (the desktop app) must send an `X-ClearView-Client` header. That stops other websites and casual scripts, but a determined person could still copy the header. Cloudflare's Rate Limiting binding isn't available to Pages Functions, so as the real backstop:

1. In the Cloudflare dashboard, go to **Manage account → Notifications** and add a usage or billing alert for Workers AI.
2. If you add a custom domain to the site, also add a **Security → WAF → Rate limiting rule** for `POST /api/identify` (for example 20 requests per minute per IP).

The endpoint also limits image uploads to 4 MB and accepts only JPEG, PNG, and WebP.

## Local preview

Install Node.js, then from this directory run:

```sh
npx wrangler pages dev public
```

This serves the static site and Pages Function locally. For local scans, start Wrangler with `npx wrangler pages dev public --ai AI`; Workers AI usage may incur charges.

## Limitations

- Browser camera and speech features vary by phone and browser.
- Text recognition works best with a sharp, upright, evenly lit page; proofread OCR results. Selecting text works in the editable recognized-text area, and the browser reads the selected passage or all text. Text size and letter spacing apply to both the scanner text and object description; speech speed can be adjusted during playback, which resumes from the last word reported by the browser.
- Read-aloud switches voice for each run of Chinese and English writing, even mid-sentence, because an English voice silently skips Chinese characters. Chinese is read with a 繁體中文 voice when the device has one; if it has none, a message explains how to add one. Some online voices (such as Google's) don't report individual words, so highlighting then moves by phrase rather than word.
- Recognition is an AI estimate and can be wrong, especially for small, obscured, or unusual objects.
- Cloudflare Workers AI usage may be subject to account limits or charges.
- The on-device detector knows the 175 objects in `vocabulary.txt`; anything else can only be named by the cloud description of the closest object. See the main README to add objects.
- The two model files (about 21 MB together) download on first use, then the browser caches them.
- When the cloud can't name the object and the on-device detector is less than 60% sure, the result says "This might be …" and suggests another angle.

## Tests

From this folder, run `node --test` (Node.js 20 or newer).
